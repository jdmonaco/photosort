"""
File permissions and group ownership utilities for photosort.
"""

import argparse
import grp
import os
import re
import subprocess
from pathlib import Path

from rich.console import Console


def parse_file_mode(mode_str: str) -> int:
    """Convert octal string (e.g., '644') to integer mode."""
    try:
        # Ensure it's a valid octal string (3-4 digits, 0-7 only)
        if not re.match(r'^[0-7]{3,4}$', mode_str):
            raise ValueError(f"Invalid mode format: {mode_str}")
        return int(mode_str, 8)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid file mode: {e}")


def get_system_default_mode() -> int:
    """Get system default file mode based on umask."""
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask  # Apply umask to base file permissions


def parse_group(group_str: str) -> int:
    """Convert group name to GID with validation."""
    try:
        return grp.getgrnam(group_str).gr_gid
    except KeyError:
        raise argparse.ArgumentTypeError(f"Group '{group_str}' not found on system")


def get_system_default_group() -> int:
    """Get user's primary group GID."""
    return os.getgid()


def set_directory_groups(dest_path: Path, group_name: str, console: Console) -> None:
    """Set group ownership on all directories in destination path."""
    try:
        result = subprocess.run(
            ["find", str(dest_path), "-type", "d", "-exec", "chgrp", group_name, "{}", "+"],
            capture_output=True, text=True, check=True
        )
        console.print(f"Applied group '{group_name}' to destination directories")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Warning: Could not set group on directories: {e}[/yellow]")