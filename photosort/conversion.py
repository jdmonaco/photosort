"""
Video conversion functionality using ffmpeg.
"""

import os
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from rich.progress import Progress, TaskID

from .constants import MODERN_VIDEO_CODECS


class VideoConverter:
    """Handles video format conversion using ffmpeg."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.logger = logging.getLogger("photosort.conversion")
        self._ffmpeg_available = self._check_ffmpeg_available()
        if not self._ffmpeg_available:
            self.logger.warning("ffmpeg unavailable: skipping legacy video conversion")

    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg and ffprobe are available."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_video_codec(self, video_path: Path) -> Optional[str]:
        """Extract video codec information using ffprobe."""
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
        if not self._ffmpeg_available:
            return False

        codec = self.get_video_codec(video_path)
        if codec is None:
            return False

        return codec not in MODERN_VIDEO_CODECS

    def convert_video(self, input_path: Path, output_path: Path,
                      progress: Optional[Progress] = None,
                      task: Optional[TaskID] = None) -> bool:
        """Convert video to H.265/MP4 format."""
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would convert {input_path} -> {output_path}")
            return True

        if not self._ffmpeg_available:
            return False

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

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
                "-crf", "23",               # Quality setting (lower = better quality)
                "-tag:v hvc1",              # Correct fourCC code for H.265/MP4
                "-y",                       # Overwrite output
                str(temp_path),
            ]

            if progress and task:
                progress.update(task, description=f"Converting: {input_path.name}")

            # Run conversion
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Verify the converted file exists and has content
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                raise FileNotFoundError("Conversion produced no output")

            # Move temp file to final location and restore original timestamps
            temp_path.rename(output_path)
            os.utime(output_path, (original_stat.st_atime, original_stat.st_mtime))

            self.logger.info(f" * {input_path} -> {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg conversion failed for {input_path}: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Conversion error for {input_path}: {e}")
            return False
        finally:
            # Clean up temp file if it still exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def get_conversion_info(
        self, input_path: Path, output_path: Path
    ) -> Dict[str, str]:
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
