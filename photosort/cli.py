"""
Command-line interface for photosort.
"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console

from .config import Config
from .core import PhotoSorter
from .permissions import parse_file_mode, parse_group, set_directory_groups
from .utils import cleanup_source_directory


def create_parser(config: Config) -> argparse.ArgumentParser:
    """Create argument parser with dynamic defaults from config."""
    last_source = config.get_last_source()
    last_dest = config.get_last_dest()
    file_mode = config.get_file_mode()
    group = config.get_group()

    # Create help text that shows current defaults
    source_help = "Source directory containing photos to organize"
    dest_help = "Destination directory for organized photos"
    mode_help = "File permissions mode in octal format (e.g., 644, 664, 400)"
    group_help = "Group ownership for organized files (e.g., staff, users, wheel)"

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

    parser = argparse.ArgumentParser(
        description="Organize photos and videos into year/month folder structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  photosort ~/Downloads/Photos ~/Pictures/Organized
  photosort --dry-run
  photosort --source ~/Desktop/NewPhotos
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

    return parser


def main() -> int:
    """Main entry point."""
    config = Config()
    parser = create_parser(config)
    args = parser.parse_args()

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

    # Set up logging level
    if args.verbose:
        logging.getLogger("photosort").setLevel(logging.DEBUG)

    # Create sorter and process files
    sorter = PhotoSorter(
        source=source,
        dest=dest,
        dry_run=args.dry_run,
        move_files=not args.copy,
        file_mode=file_mode,
        group_gid=group_gid
    )

    console = Console()

    if args.dry_run:
        console.print("[yellow]DRY RUN - No files will be moved[/yellow]")

    console.print(f"Source: [blue]{source}[/blue]")
    console.print(f"Destination: [blue]{dest}[/blue]")

    # Find and process files
    media_files, metadata_files = sorter.find_source_files()

    if not media_files and not metadata_files:
        console.print("[yellow]No media or metadata files found in source directory[/yellow]")
        return 0

    total_files = len(media_files) + len(metadata_files)
    console.print(f"Found {len(media_files)} media files and {len(metadata_files)} metadata files to process")

    try:
        # Process metadata files first
        if metadata_files:
            console.print("Processing metadata files...")
            sorter.process_metadata_files(metadata_files)

        # Process media files
        if media_files:
            console.print("Processing media files...")
            sorter.process_files(media_files)

        # If moving files (and not dry-run), clean up the source directory
        if not args.copy and not args.dry_run:
            cleanup_source_directory(source, sorter.history_manager, console)

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