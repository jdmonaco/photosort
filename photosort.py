#!/usr/bin/env python3

"""
photosort - Organize photos and videos into year/month folder structure.

A modern Python tool for organizing unstructured photo and video collections
into a clean year/month directory structure based on file creation dates.

Created with the assistance of Claude Code on 2025-06-24.
"""

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, TaskID
from rich.table import Table

# File extension constants
JPG_EXTENSIONS = (".jpg", ".jpeg", ".jpe")
RAW_EXTENSIONS = (
    ".3fr", ".3pr", ".arw", ".ce1", ".ce2", ".cib", ".cmt", ".cr2", ".craw",
    ".crw", ".dc2", ".dcr", ".dng", ".erf", ".exf", ".fff", ".fpx", ".gray",
    ".grey", ".gry", ".heic", ".iiq", ".kc2", ".kdc", ".mdc", ".mef", ".mfw",
    ".mos", ".mrw", ".ndd", ".nef", ".nop", ".nrw", ".nwb", ".orf", ".pcd",
    ".pef", ".png", ".ptx", ".ra2", ".raf", ".raw", ".rw2", ".rwl", ".rwz",
    ".sd0", ".sd1", ".sr2", ".srf", ".srw", ".st4", ".st5", ".st6", ".st7",
    ".st8", ".stx", ".x3f", ".ycbcra",
)
PHOTO_EXTENSIONS = JPG_EXTENSIONS + RAW_EXTENSIONS
MOVIE_EXTENSIONS = (
    ".3g2", ".3gp", ".asf", ".asx", ".avi", ".flv", ".m4v", ".mov", ".mp4",
    ".mpg", ".rm", ".srt", ".swf", ".vob", ".wmv", ".aepx", ".ale", ".avp",
    ".avs", ".bdm", ".bik", ".bin", ".bsf", ".camproj", ".cpi", ".dash",
    ".divx", ".dmsm", ".dream", ".dvdmedia", ".dvr-ms", ".dzm", ".dzp",
    ".edl", ".f4v", ".fbr", ".fcproject", ".hdmov", ".imovieproj", ".ism",
    ".ismv", ".m2p", ".mkv", ".mod", ".moi", ".mpeg", ".mts", ".mxf", ".ogv",
    ".otrkey", ".pds", ".prproj", ".psh", ".r3d", ".rcproject", ".rmvb",
    ".scm", ".smil", ".snagproj", ".sqz", ".stx", ".swi", ".tix", ".trp",
    ".ts", ".veg", ".vf", ".vro", ".webm", ".wlmp", ".wtv", ".xvid", ".yuv",
)
METADATA_EXTENSIONS = (
    ".aae", ".dat", ".ini", ".cfg", ".xml", ".plist", ".json", ".txt", ".log",
    ".info", ".meta", ".properties", ".conf", ".config", ".xmp"
)
VALID_EXTENSIONS = PHOTO_EXTENSIONS + MOVIE_EXTENSIONS

# TODO: Future enhancement - Add ffmpeg video conversion for legacy formats
# Goal: Convert old formats (mpg, 3gp, etc.) to modern mp4/h264


class Config:
    """Manages configuration file for storing user preferences."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = (config_path or
                Path.home() / ".config" / "photosort" / "photosort.yml")
        self.data = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.warning(f"Could not load config: {e}")
            return {}

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.data, f, default_flow_style=False)
        except Exception as e:
            logging.error(f"Could not save config: {e}")

    def get_last_source(self) -> Optional[str]:
        """Get the last used source directory."""
        return self.data.get('last_source')

    def get_last_dest(self) -> Optional[str]:
        """Get the last used destination directory."""
        return self.data.get('last_dest')

    def update_paths(self, source: str, dest: str) -> None:
        """Update and save the last used paths."""
        self.data['last_source'] = source
        self.data['last_dest'] = dest
        self.save_config()


class PhotoSorter:
    """Main class for organizing photos and videos."""

    def __init__(self, source: Path, dest: Path, dry_run: bool = False,
                 move_files: bool = True):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.console = Console()
        self.stats = {
            'photos': 0, 'videos': 0, 'metadata': 0,
            'duplicates': 0, 'errors': 0, 'total_size': 0
        }

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self.console, rich_tracebacks=True)]
        )
        self.logger = logging.getLogger("photosort")

        # Create necessary directories
        if not self.dry_run:
            self.dest.mkdir(parents=True, exist_ok=True)
            self.error_dir = self.dest / "Unsorted"
            self.error_dir.mkdir(exist_ok=True)
            self.metadata_dir = self.dest / "Metadata"
            self.metadata_dir.mkdir(exist_ok=True)

    def get_creation_date(self, file_path: Path) -> datetime:
        """Extract creation date from file metadata."""
        try:
            if file_path.suffix.lower() in MOVIE_EXTENSIONS:
                raise TypeError("Movie file - use filesystem date")

            # Use macOS sips command for photo metadata
            result = subprocess.run(
                ["sips", "-g", "creation", str(file_path)],
                capture_output=True, text=True, check=True
            )

            # Parse sips output
            for line in result.stdout.split('\n'):
                if 'creation:' in line:
                    date_str = line.split('creation: ')[1].strip()
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

            raise ValueError("No creation date found in sips output")

        except (subprocess.CalledProcessError, ValueError, TypeError):
            # Fallback to file modification time
            return datetime.fromtimestamp(file_path.stat().st_mtime)

    def find_source_files(self) -> Tuple[List[Path], List[Path]]:
        """Find all files in source directory, separated by type."""
        media_files = []
        metadata_files = []

        for file_path in self.source.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in VALID_EXTENSIONS:
                    media_files.append(file_path)
                elif ext in METADATA_EXTENSIONS:
                    metadata_files.append(file_path)

        return sorted(media_files), sorted(metadata_files)

    def is_duplicate(self, source_file: Path, dest_file: Path) -> bool:
        """Check if files are duplicates based on size and optionally content."""
        if not dest_file.exists():
            return False

        # Quick size check
        if source_file.stat().st_size != dest_file.stat().st_size:
            return False

        # For small files, also check content hash
        if source_file.stat().st_size < 10 * 1024 * 1024:  # 10MB threshold
            return self._files_have_same_hash(source_file, dest_file)

        return True  # Assume duplicate if same size for large files

    def _files_have_same_hash(self, file1: Path, file2: Path) -> bool:
        """Compare files using SHA-256 hash."""
        try:
            hash1 = hashlib.sha256()
            hash2 = hashlib.sha256()

            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                while True:
                    chunk1 = f1.read(8192)
                    chunk2 = f2.read(8192)
                    if not chunk1 and not chunk2:
                        break
                    hash1.update(chunk1)
                    hash2.update(chunk2)

            return hash1.hexdigest() == hash2.hexdigest()
        except Exception:
            return False

    def get_destination_path(self, file_path: Path, creation_date: datetime) -> Path:
        """Generate destination path for a file."""
        year = f"{creation_date.year:04d}"
        month = f"{creation_date.month:02d}"

        # Format filename with timestamp
        timestamp = creation_date.strftime("%Y-%m-%d %H-%M-%S")
        ext = file_path.suffix.lower()

        # Normalize JPG extensions
        if ext in JPG_EXTENSIONS:
            ext = ".jpg"

        # Create destination directory
        dest_dir = self.dest / year / month

        # Handle filename conflicts
        base_name = timestamp
        dest_file = dest_dir / f"{base_name}{ext}"
        suffix = 'a'

        while dest_file.exists() and not self.is_duplicate(file_path, dest_file):
            dest_file = dest_dir / f"{base_name}{suffix}{ext}"
            suffix = chr(ord(suffix) + 1)

        return dest_file

    def process_metadata_files(self, metadata_files: List[Path]) -> None:
        """Process metadata files by moving them to Metadata directory."""
        if not metadata_files:
            return

        for file_path in metadata_files:
            try:
                # Preserve relative path structure in Metadata directory
                relative_path = file_path.relative_to(self.source)
                dest_path = self.metadata_dir / relative_path

                if self.move_file_safely(file_path, dest_path):
                    self.stats['metadata'] += 1
                else:
                    self.stats['errors'] += 1
                    if not self.dry_run:
                        self._move_to_error_dir(file_path)

            except Exception as e:
                self.logger.error(f"Error processing metadata file {file_path}: {e}")
                self.stats['errors'] += 1
                if not self.dry_run:
                    self._move_to_error_dir(file_path)

    def move_file_safely(self, source: Path, dest: Path) -> bool:
        """Move file with validation."""
        if self.dry_run:
            return True

        try:
            # Create destination directory
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            if self.move_files:
                shutil.move(str(source), str(dest))
            else:
                shutil.copy2(str(source), str(dest))

            # Verify the operation
            if not dest.exists():
                raise FileNotFoundError(f"File not found after move: {dest}")

            if self.move_files and source.exists():
                raise FileExistsError(f"Source file still exists after move: {source}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to move {source} -> {dest}: {e}")
            return False

    def process_files(self, files: List[Path]) -> None:
        """Process all files with progress tracking."""
        with Progress(console=self.console) as progress:
            task = progress.add_task("Processing files...", total=len(files))

            for file_path in files:
                try:
                    self._process_single_file(file_path, progress, task)
                except Exception as e:
                    self.logger.error(f"Error processing {file_path}: {e}")
                    self.stats['errors'] += 1
                    if not self.dry_run:
                        self._move_to_error_dir(file_path)

                progress.advance(task)

    def _process_single_file(self, file_path: Path, progress: Progress, task: TaskID) -> None:
        """Process a single media file."""
        # Get file size before any operations
        file_size = file_path.stat().st_size

        # Get creation date
        creation_date = self.get_creation_date(file_path)

        # Generate destination path
        dest_path = self.get_destination_path(file_path, creation_date)

        # Check for duplicates
        if dest_path.exists() and self.is_duplicate(file_path, dest_path):
            self.stats['duplicates'] += 1
            progress.update(task, description=f"Skipping duplicate: {file_path.name}")
            return

        # Move main file
        if self.move_file_safely(file_path, dest_path):
            self.stats['total_size'] += file_size

            # Update stats
            if file_path.suffix.lower() in MOVIE_EXTENSIONS:
                self.stats['videos'] += 1
            else:
                self.stats['photos'] += 1

            progress.update(task, description=f"Processed: {file_path.name}")
        else:
            self.stats['errors'] += 1
            if not self.dry_run:
                self._move_to_error_dir(file_path)

    def _move_to_error_dir(self, file_path: Path) -> None:
        """Move problematic file to error directory."""
        try:
            error_dest = self.error_dir / file_path.name
            counter = 1
            while error_dest.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                error_dest = self.error_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            shutil.copy2(str(file_path), str(error_dest))
        except Exception as e:
            self.logger.error(f"Could not move error file: {e}")

    def print_summary(self) -> None:
        """Print processing summary."""
        table = Table(title="Processing Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="green")

        table.add_row("Photos", str(self.stats['photos']))
        table.add_row("Videos", str(self.stats['videos']))
        table.add_row("Metadata Files", str(self.stats['metadata']))
        table.add_row("Duplicates Skipped", str(self.stats['duplicates']))
        table.add_row("Errors", str(self.stats['errors']))

        # Format total size
        size_mb = self.stats['total_size'] / (1024 * 1024)
        if size_mb > 1024:
            size_str = f"{size_mb/1024:.1f} GB"
        else:
            size_str = f"{size_mb:.1f} MB"
        table.add_row("Total Size", size_str)

        self.console.print(table)

        if self.stats['errors'] > 0:
            self.console.print(f"\n[red]Problematic files moved to: {self.error_dir}[/red]")


def cleanup_source_directory(source: Path, dest: Path, console: Console) -> None:
    """Clean up source directory by removing empty folders and moving unknown files."""
    if not any(source.iterdir()):
        return
    
    # Recursively prune empty subfolders from the source tree
    console.print("Cleaning source folder...")
    for thisdir, subdirs, _ in os.walk(source, topdown=False):
        for thissubdir in subdirs:
            try:
                os.rmdir(Path(thisdir) / thissubdir)
            except OSError:
                pass

    # Move remaining unknown files
    unknowns = list(source.glob("*"))
    if unknowns:
        console.print("Moving unknown files...")
        unkpath = dest / "UnknownFiles"
        unkpath.mkdir(exist_ok=True)
        for remaining in unknowns:
            shutil.move(remaining, unkpath / remaining.name)


def create_parser(config: Config) -> argparse.ArgumentParser:
    """Create argument parser with dynamic defaults from config."""
    last_source = config.get_last_source()
    last_dest = config.get_last_dest()

    # Create help text that shows current defaults
    source_help = "Source directory containing photos to organize"
    dest_help = "Destination directory for organized photos"

    if last_source:
        source_help += f" (default: {last_source})"
    if last_dest:
        dest_help += f" (default: {last_dest})"

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

    # Set up logging level
    if args.verbose:
        logging.getLogger("photosort").setLevel(logging.DEBUG)

    # Create sorter and process files
    sorter = PhotoSorter(
        source=source,
        dest=dest,
        dry_run=args.dry_run,
        move_files=not args.copy
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

        # If moving files, clean up the source directory
        if not args.copy:
            cleanup_source_directory(source, dest, console)

        sorter.print_summary()

        if sorter.stats['errors'] == 0:
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
