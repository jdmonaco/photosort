"""
Video conversion functionality using ffmpeg.
"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .constants import (get_logger, ffmpeg_available, ffprobe_available,
                        MODERN_VIDEO_CODECS, MOVIE_EXTENSIONS, PROGRAM)
from .file_operations import FileOperations
from .progress import ProgressContext


@dataclass
class ConversionResult:
    """Result of video conversion operation."""
    source_file: Path
    processing_file: Path  # File to actually process (original or converted)
    temp_file: Optional[Path] = None  # Temp file to clean up
    was_converted: bool = False
    success: bool = True


class VideoConverter:
    """Handles video format conversion using ffmpeg."""

    def __init__(self, file_ops: FileOperations, convert_videos: bool = True):
        self.file_ops = file_ops
        self.convert_videos = convert_videos
        self.logger = get_logger("photosort.conversion")
        if not ffmpeg_available:
            self.logger.warning("ffmpeg unavailable: skipping legacy video conversion")

    def get_video_codec(self, video_path: Path) -> Optional[str]:
        """Extract video codec information using ffprobe."""
        if ffprobe_available:
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_streams",
                        "-select_streams", "v:0",
                        str(video_path),
                    ],
                    capture_output=True, text=True, check=True,
                )

                data = json.loads(result.stdout)
                if data.get("streams"):
                    codec = data["streams"][0].get("codec_name", "").lower()
                    return codec
            except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
                self.logger.warning(f"Could not determine codec for {video_path}")

        return None

    def _needs_conversion(self, video_path: Path) -> bool:
        """Check if video needs conversion to modern format."""
        codec = self.get_video_codec(video_path)
        if codec is None:
            return False

        return codec not in MODERN_VIDEO_CODECS

    def get_content_identifier(self, video_path: Path) -> Optional[str]:
        """Extract Apple ContentIdentifer tag using ffprobe."""
        if ffprobe_available:
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_entries", "format_tags",
                        str(video_path),
                    ],
                    capture_output=True, text=True, check=True,
                )

                data = json.loads(result.stdout)
                if data.get("format", {}).get("tags", {}):
                    content_id = data["format"]["tags"]["com.apple.quicktime.content.identifier"]
                    self.logger.debug(f"Found {video_path.name}:ContentIdentifier = {content_id}")
                    return content_id
            except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
                pass

        return None

    def _content_id_preserved(self, orig_file: Path, conv_file: Path) -> bool:
        """Verify that ContentIdentifier metadata was preserved."""
        orig_id = self.get_content_identifier(orig_file)
        conv_id = self.get_content_identifier(conv_file)

        if orig_id:
            if conv_id and orig_id == conv_id:
                return True
            else:
                self.logger.warning(f"Conversion did not preserve ContentIdentifier for {orig_file}")
        else:
            return True  # nothing to preserve

        return False

    def convert_video(self, input_path: Path, output_path: Path,
                      progress_ctx: Optional[ProgressContext] = None) -> bool:
        """Convert video to HEVC/H.265 format in a MP4 container."""
        if not ffmpeg_available:
            return False

        if self.file_ops.dry_run:
            self.logger.info(f"DRY RUN: Would convert {input_path} -> {output_path}")
            return True

        # Create output directory
        self.file_ops.ensure_directory(output_path.parent)

        # Save file stat to restore on the output path
        original_stat = input_path.stat()

        # Use temporary file to avoid partial writes
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Build ffmpeg command for H.265/MP4 conversion
            cmd = [
                "ffmpeg", "-i", str(input_path),
                "-c:v", "libx265",          # H.265 video codec
                "-c:a", "aac",              # AAC audio codec
                "-ac", "2",                 # Stereo audio
                "-ar", "48000",             # 48kHz sample rate
                "-preset", "medium",        # Encoding speed/quality balance
                "-movflags", "+faststart+use_metadata_tags",  # Streaming + Apple metadata
                "-map_metadata", "0:g",     # Preserve global metadata
                "-metadata:s:v", "encoder=libx265",
                "-metadata:s:a", "encoder=aac",
                "-pix_fmt", "yuv420p",      # QuickTime/macOS compatibility
                "-crf", "26",               # Quality setting (lower = better quality)
                "-tag:v", "hvc1",           # Correct fourCC code for H.265/MP4
                "-y",                       # Overwrite output
                str(temp_path),
            ]

            if progress_ctx:
                progress_ctx.update(f"Converting: {input_path.name}")

            # Run conversion
            result = subprocess.run(cmd, capture_output=True, check=True)

            # Verify the converted file exists and has content
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                raise FileNotFoundError("Conversion produced no output")

            # Verify that Apple ContentIdentifier tags were preserved
            if not self._content_id_preserved(input_path, temp_path):
                raise ValueError("Apple ContentIdentifier tag not preserved")

            # Move temp file to final location and restore original timestamps
            shutil.move(str(temp_path), str(output_path))
            os.utime(output_path, (original_stat.st_atime, original_stat.st_mtime))

            self.logger.info(f"{input_path} -> {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg conversion failed for {input_path}: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Conversion error for {input_path}: {e}")
            return False
        finally:
            self.file_ops.delete_safely(temp_path)

    def handle_video_conversion(self, file_path: Path,
                                progress_ctx: Optional[ProgressContext] = None,
                                prefix: str = PROGRAM) -> ConversionResult:
        """Handle video conversion if needed, return result object.

        Args:
            file_path: Path to the file to potentially convert
            progress_ctx: Optional progress context for updates
            prefix: Prefix for temp file names

        Returns:
            ConversionResult with conversion details
        """

        # Check if conversion needed
        is_video = file_path.suffix.lower() in MOVIE_EXTENSIONS
        if not (is_video and self.convert_videos and self._needs_conversion(file_path)):
            return ConversionResult(source_file=file_path, processing_file=file_path)

        # Create temp file and convert
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4", prefix=f"{prefix}_")
        os.close(temp_fd)
        converted_path = Path(temp_path)

        if progress_ctx:
            progress_ctx.update(f"Converting: {file_path.name}")

        success = self.convert_video(file_path, converted_path, progress_ctx)

        if success:
            self.logger.info(f"Successfully converted {file_path} -> {converted_path}")
        else:
            self.logger.error(f"Failed to convert video: {file_path}")

        return ConversionResult(
            source_file=file_path,
            processing_file=converted_path if success else file_path,
            temp_file=converted_path,
            was_converted=True,
            success=success
        )

