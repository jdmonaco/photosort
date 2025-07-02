"""
Command-line interface for photosort.
"""

import argparse
import grp
import logging
import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from .config import Config
from .constants import PROGRAM
from .core import PhotoSorter


def parse_file_mode(mode_str: str) -> int:
    """Convert octal string (e.g., '644') to integer mode."""
    try:
        # Ensure it's a valid octal string (3-4 digits, 0-7 only)
        if not re.match(r'^[0-7]{3,4}$', mode_str):
            raise ValueError(f"Invalid mode format: {mode_str}")
        return int(mode_str, 8)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid file mode: {e}")


def parse_group(group_str: str) -> int:
    """Convert group name to GID with validation."""
    try:
        return grp.getgrnam(group_str).gr_gid
    except KeyError:
        raise argparse.ArgumentTypeError(f"Group '{group_str}' not found on system")


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


def create_parser(config: Config) -> argparse.ArgumentParser:
    """Create argument parser with dynamic defaults from config."""
    last_source = config.get_last_source()
    last_dest = config.get_last_dest()
    file_mode = config.get_file_mode()
    group = config.get_group()
    timezone = config.get_timezone()
    convert_videos = config.get_convert_videos()

    # Create help text that shows current defaults
    source_help = "Source directory containing photos to organize"
    dest_help = "Destination directory for organized photos"
    mode_help = "File permissions mode in octal format (e.g., 644, 664, 400)"
    group_help = "Group ownership for organized files (e.g., staff, users, wheel)"
    timezone_help = "Default timezone for creation time metadata if missing"
    video_help = "Disable automatic conversion of legacy video formats to H.265/MP4"
    version_help = f"Display the version number of {PROGRAM} and exit"

    if last_source:
        source_help += f" (default: {last_source})"
    if last_dest:
        dest_help += f" (default: {last_dest})"
    if file_mode:
        mode_help += f" (default: {file_mode})"
    else:
        mode_help += " (default: system umask)"
    if group:
        group_help += f" (default: {group})"
    else:
        group_help += " (default: user primary group)"
    if timezone:
        timezone_help += f" (default: {timezone})"
    else:
        timezone_help += " (default: America/New_York)"

    parser = argparse.ArgumentParser(
        description="Smart organizer for importing photos and videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {PROGRAM} ~/Downloads/Photos ~/Pictures/Organized
  {PROGRAM} --dry-run
  {PROGRAM} --source ~/Desktop/NewPhotos
        """
    )

    parser.add_argument(
        "source", nargs="?",
        help=source_help
    )
    parser.add_argument(
        "dest", nargs="?",
        help=dest_help
    )
    parser.add_argument(
        "--source", "-s", dest="source_override",
        help="Override source directory"
    )
    parser.add_argument(
        "--dest", "-d", dest="dest_override",
        help="Override destination directory"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview operations without making changes"
    )
    parser.add_argument(
        "--copy", "-c", action="store_true",
        help="Copy files instead of moving them"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--mode", "-m", type=str, metavar="MODE",
        help=mode_help
    )
    parser.add_argument(
        "--group", "-g", type=str, metavar="GROUP",
        help=group_help
    )
    parser.add_argument(
        "--timezone", "--tz", type=str, metavar="TIMEZONE",
        help=timezone_help
    )
    parser.add_argument(
        "--no-convert-videos", action="store_true",
        help=video_help
    )
    parser.add_argument(
        "--version", "-V", action="store_true",
        help=version_help
    )

    return parser


def main() -> int:
    """Main entry point."""
    config = Config()
    parser = create_parser(config)
    args = parser.parse_args()

    # Handle version option
    if args.version:
        from . import __version__, __copyright__
        if args.verbose:
            print(f"{PROGRAM} version {__version__} {__copyright__}")
            print(f"Imports: {config.program_root}")
            print(f"Config:  {config.config_path}")
            return 0
        print(__version__)
        return 0

    # Determine source and destination
    source_path = (args.source_override or args.source or
                   config.get_last_source())
    dest_path = (args.dest_override or args.dest or
                 config.get_last_dest())

    if not source_path or not dest_path:
        parser.error("Source and destination directories are required")

    source = Path(source_path).expanduser().resolve()
    dest = Path(dest_path).expanduser().resolve()

    # Validate paths
    if not source.exists():
        print(f"Error: Source directory does not exist: {source}")
        return 1

    if not source.is_dir():
        print(f"Error: Source is not a directory: {source}")
        return 1

    if source == dest or source in dest.parents or dest in source.parents:
        print("Error: Separate import/target folders are required:")
        print(f" - Source:      {source}")
        print(f" - Destination: {dest}")
        return 1

    # Update config with current paths
    config.update_paths(str(source), str(dest))

    # Handle file mode argument
    file_mode = None
    if args.mode:
        try:
            file_mode = parse_file_mode(args.mode)
            config.update_file_mode(args.mode)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}")
            return 1
    elif config.get_file_mode():
        try:
            file_mode = parse_file_mode(config.get_file_mode())
        except Exception:
            # If saved mode is invalid, use system default
            file_mode = None

    # Handle group argument
    group_gid = None
    if args.group:
        try:
            group_gid = parse_group(args.group)
            config.update_group(args.group)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}")
            return 1
    elif config.get_group():
        try:
            group_gid = parse_group(config.get_group())
        except Exception:
            # If saved group is invalid, use system default
            group_gid = None

    # Handle timezone setting
    timezone = args.timezone if hasattr(args, 'timezone') and args.timezone else config.get_timezone() or "America/New_York"
    if hasattr(args, 'timezone') and args.timezone:
        config.update_timezone(args.timezone)

    # Handle video conversion setting - invert since flag disables conversion
    convert_videos = not args.no_convert_videos

    # Set up logging level
    if args.verbose:
        logging.getLogger(PROGRAM).setLevel(logging.DEBUG)

    # Create sorter and process files
    sorter = PhotoSorter(
        source=source,
        dest=dest,
        root_dir=config.program_root,
        dry_run=args.dry_run,
        move_files=not args.copy,
        file_mode=file_mode,
        group_gid=group_gid,
        timezone=timezone,
        convert_videos=convert_videos
    )

    console = Console()

    if args.dry_run:
        console.print("[yellow]DRY RUN - No files will be moved[/yellow]")

    console.print(f"Source:      [blue]{source}[/blue]")
    console.print(f"Destination: [blue]{dest}[/blue]")

    # Find and process files
    media_files, metadata_files, livephoto_pairs = sorter.find_source_files()

    total_files = len(media_files) + (len(livephoto_pairs) * 2)
    if total_files == 0:
        console.print("[yellow]No media files found in source directory[/yellow]")
        return 0

    console.print(f"Found {len(media_files)} individual files and {len(livephoto_pairs)} Live Photo pairs to process")

    try:
        # Process Live Photo pairs first (to avoid filename collisions)
        if livephoto_pairs:
            console.print("Processing Live Photo pairs...")
            sorter.process_livephoto_pairs(livephoto_pairs)

        # Process remaining individual media files
        if media_files:
            console.print("Processing individual media files...")
            sorter.process_files(media_files)

        # Process metadata files after media files
        if metadata_files:
            console.print("Processing metadata files...")
            sorter.process_metadata_files(metadata_files)

        # If moving files (and not dry-run), clean up the source directory
        if not args.copy and not args.dry_run:
            sorter.file_ops.cleanup_source_directory(
                    source, sorter.history_manager.get_unknown_files_dir()
            )

        sorter.print_summary()

        # Apply group to directories if specified
        if group_gid is not None and not args.dry_run:
            group_name = config.get_group() or args.group
            set_directory_groups(dest, group_name, console)

        # Log import summary to global imports.log
        success = sorter.stats['errors'] == 0
        sorter.history_manager.log_import_summary(source, dest, sorter.stats, success)

        if success:
            console.print("\n[green]✓ Processing completed successfully![/green]")
            return 0
        else:
            console.print(f"\n[yellow]⚠ Processing completed with {sorter.stats['errors']} errors[/yellow]")
            return 1

    except KeyboardInterrupt:
        console.print("\n[red]Operation cancelled by user[/red]")
        return 1
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

