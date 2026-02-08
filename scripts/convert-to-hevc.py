#!/usr/bin/env python3
"""Convert videos to x265/HEVC format using ffmpeg."""

import sys
import subprocess
from pathlib import Path


def convert_video(input_path: Path, output_path: Path) -> bool:
    """Convert the video using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-c:v", "libx265",          # H.265 video codec
        "-c:a", "aac",              # AAC audio codec
        "-preset", "medium",        # Encoding speed/quality balance
        "-movflags", "+faststart+use_metadata_tags",  # Streaming + Apple metadata
        "-map_metadata", "0:g",     # Global metadata only
        "-pix_fmt", "yuv420p",      # QuickTime/macOS compatibility
        "-crf", "23",               # Quality setting (lower = better quality)
        "-tag:v", "hvc1",           # Correct fourCC code for H.265/MP4
        "-y",                       # Overwrite output
        str(output_path)
    ]

    # Run conversion
    return subprocess.run(cmd, capture_output=True)


def main() -> int:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_path> <output_path>")
        return 1

    input_path = Path(str(sys.argv[1])).expanduser().resolve()
    output_path = Path(str(sys.argv[2])).expanduser().resolve()

    if not input_path.exists():
        print(f"Error: missing input file: {input_path}")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except IOError:
        print(f"Error: invalid output path: {output_path.parent}")
        return 1

    result = None
    try:
        result = convert_video(input_path, output_path)
        if result.returncode == 0:
            print(f"Conversion successful: {output_path}")
        else:
            print(f"Error: ffmpeg call failed:")
            print(result.stderr.decode("utf-8"))
    except Exception as e:
        print(f"Error: video conversion failed:\n{e}")

    return result.returncode if result else 1


if __name__ == "__main__":
    sys.exit(main())

