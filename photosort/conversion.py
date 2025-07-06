"""
Video conversion functionality using ffmpeg.
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .constants import MODERN_VIDEO_CODECS, MOVIE_EXTENSIONS, PROGRAM, get_logger
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
    
    def cleanup_temp(self) -> None:
        """Clean up temporary file if it exists."""
        if self.temp_file and self.temp_file.exists():
            try:
                self.temp_file.unlink()
            except Exception:
                pass
    
    def handle_conversion_cleanup(self, file_ops: FileOperations, source_root: Path, 
                                  legacy_dir: Path) -> None:
        """Handle cleanup after video conversion, archiving originals and removing temp files."""
        if not self.was_converted:
            return
        
        # Archive original video
        file_ops.archive_file(self.source_file, legacy_dir, preserve_structure=True, source_root=source_root)
        
        # Clean up temp converted video file
        self.cleanup_temp()


class VideoConverter:
    """Handles video format conversion using ffmpeg."""

    def __init__(self, file_ops: FileOperations, convert_videos: bool = True):
        self.file_ops = file_ops
        self.convert_videos = convert_videos
        self.logger = get_logger("photosort.conversion")
        self.ffmpeg_available = file_ops.check_tool_availability("ffmpeg", "-version")
        self.ffprobe_available = file_ops.check_tool_availability("ffprobe", "-version")
        if not self.ffmpeg_available:
            self.logger.warning("ffmpeg unavailable: skipping legacy video conversion")

    def get_video_codec(self, video_path: Path) -> Optional[str]:
        """Extract video codec information using ffprobe."""
        if self.ffprobe_available:
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

    def needs_conversion(self, video_path: Path) -> bool:
        """Check if video needs conversion to modern format."""
        codec = self.get_video_codec(video_path)
        if codec is None:
            return False

        return codec not in MODERN_VIDEO_CODECS

    def convert_video(self, input_path: Path, output_path: Path,
                      progress_ctx: Optional[ProgressContext] = None) -> bool:
        """Convert video to HEVC/H.265 format in a MP4 container."""
        if self.file_ops.dry_run:
            self.logger.info(f"DRY RUN: Would convert {input_path} -> {output_path}")
            return True

        if not self.ffmpeg_available:
            return False

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
                "-movflags", "+faststart",  # Optimize for streaming
                "-map_metadata", "0:g",     # Global metadata only
                "-metadata:s:v", "encoder=libx265",
                "-metadata:s:a", "encoder=aac",
                "-pix_fmt", "yuv420p",      # QuickTime/macOS compatibility
                "-crf", "28",               # Quality setting (lower = better quality)
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

            # Move temp file to final location and restore original timestamps
            temp_path.rename(output_path)
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
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def get_conversion_info(self, input_path: Path, output_path: Path) -> Dict[str, str]:
        """Get information about the conversion that will be performed."""
        original_codec = self.get_video_codec(input_path) or "unknown"
        original_size = input_path.stat().st_size

        info = {
            "original_codec": original_codec,
            "target_codec": "h265",
            "original_size": f"{original_size / (1024*1024):.1f} MB",
            "container": "mp4",
        }

        if output_path.exists():
            converted_size = output_path.stat().st_size
            info["converted_size"] = f"{converted_size / (1024*1024):.1f} MB"
            info["size_reduction"] = (
                f"{((original_size - converted_size) / original_size * 100):.1f}%"
            )

        return info

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
        if not (is_video and self.convert_videos and self.needs_conversion(file_path)):
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
            return ConversionResult(
                source_file=file_path,
                processing_file=converted_path,
                temp_file=converted_path,
                was_converted=True,
                success=True
            )
        else:
            self.logger.error(f"Failed to convert video: {file_path}")
            return ConversionResult(
                source_file=file_path,
                processing_file=file_path,
                temp_file=converted_path,
                was_converted=True,
                success=False
            )

