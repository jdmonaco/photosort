"""
Core photo sorting functionality.
"""

import hashlib
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, TaskID
from rich.table import Table

from .constants import (
    JPG_EXTENSIONS, METADATA_EXTENSIONS, MOVIE_EXTENSIONS,
    PHOTO_EXTENSIONS, VALID_EXTENSIONS
)
from .conversion import VideoConverter
from .history import HistoryManager


class PhotoSorter:
    """Main class for organizing photos and videos."""

    def __init__(self, source: Path, dest: Path, dry_run: bool = False,
                 move_files: bool = True, file_mode: Optional[int] = None,
                 group_gid: Optional[int] = None, convert_videos: bool = True):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = file_mode
        self.group_gid = group_gid
        self.convert_videos = convert_videos
        self.console = Console()
        self.stats = {
            'photos': 0, 'videos': 0, 'metadata': 0,
            'duplicates': 0, 'errors': 0, 'total_size': 0,
            'converted_videos': 0
        }

        # Setup history manager for import tracking and auxiliary directories
        self.history_manager = HistoryManager(dest, dry_run)

        # Setup video converter
        self.video_converter = VideoConverter(dry_run)

        # Setup logging with separate console and file levels
        console_handler = RichHandler(console=self.console, rich_tracebacks=True)
        console_handler.setLevel(logging.WARNING)  # Only WARNING and ERROR to console
        console_handler.setFormatter(logging.Formatter("%(message)s"))

        logging.basicConfig(
            level=logging.DEBUG,  # Allow all messages to reach handlers
            format="%(message)s",
            datefmt="[%X]",
            handlers=[console_handler]
        )
        self.logger = logging.getLogger("photosort")

        # Setup import-specific logging
        self.history_manager.setup_import_logger(self.logger)

        # Log the start of import session
        self.logger.info(f"Starting PhotoSorter session: {self.source} -> {self.dest}")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'MOVE' if self.move_files else 'COPY'}")

        # Set up directory paths - now using history manager
        self.error_dir = self.history_manager.get_unsorted_dir()
        self.metadata_dir = self.history_manager.get_metadata_dir()
        self.legacy_videos_dir = self.history_manager.get_legacy_videos_dir()

        # Create main destination directory
        if not self.dry_run:
            self.dest.mkdir(parents=True, exist_ok=True)

    def _ensure_error_dir(self) -> None:
        """Create error directory if needed and not in dry-run mode."""
        if not self.dry_run and not self.error_dir.exists():
            self.error_dir.mkdir(exist_ok=True)

    def _ensure_metadata_dir(self) -> None:
        """Create metadata directory if needed and not in dry-run mode."""
        if not self.dry_run and not self.metadata_dir.exists():
            self.metadata_dir.mkdir(exist_ok=True)

    def _ensure_legacy_videos_dir(self) -> None:
        """Create legacy videos directory if needed and not in dry-run mode."""
        if not self.dry_run and not self.legacy_videos_dir.exists():
            self.legacy_videos_dir.mkdir(exist_ok=True)

    def _apply_file_permissions(self, file_path: Path, mode: Optional[int]) -> None:
        """Apply file permissions if mode is specified."""
        if self.dry_run or mode is None:
            return

        try:
            os.chmod(file_path, mode)
        except Exception as e:
            self.logger.error(f"Failed to set permissions on {file_path}: {e}")

    def _apply_file_group(self, file_path: Path, gid: Optional[int]) -> None:
        """Apply file group ownership if gid is specified."""
        if self.dry_run or gid is None:
            return

        try:
            os.chown(file_path, -1, gid)  # -1 preserves current owner
        except Exception as e:
            self.logger.error(f"Failed to set group on {file_path}: {e}")

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
        timestamp = creation_date.strftime("%Y%m%d_%H%M%S")
        ext = file_path.suffix.lower()

        # Normalize JPG extensions
        if ext in JPG_EXTENSIONS:
            ext = ".jpg"

        # Create destination directory
        dest_dir = self.dest / year / month

        # Create the filename from the timestamp and a 2-digit counter
        counter = 0
        dest_file = dest_dir / f"{timestamp}_{counter:02d}{ext}"

        # Handle filename conflicts
        while dest_file.exists() and not self.is_duplicate(file_path, dest_file):
            dest_file = dest_dir / f"{timestamp}_{counter:02d}{ext}"
            counter += 1

        return dest_file

    def process_metadata_files(self, metadata_files: List[Path]) -> None:
        """Process metadata files by moving them to Metadata directory."""
        if not metadata_files:
            return

        self.logger.info(f"Processing {len(metadata_files)} metadata files")
        self._ensure_metadata_dir()
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

            # Apply file permissions if specified
            self._apply_file_permissions(dest, self.file_mode)

            # Apply file group ownership if specified
            self._apply_file_group(dest, self.group_gid)

            # Log the successful move
            self.logger.info(f" * {source} -> {dest}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to move {source} -> {dest}: {e}")
            return False

    def process_files(self, files: List[Path]) -> None:
        """Process all files with progress tracking."""
        self.logger.info(f"Starting to process {len(files)} files")
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

        # Check if this is a video that needs conversion
        is_video = file_path.suffix.lower() in MOVIE_EXTENSIONS
        needs_conversion = (
            is_video and
            self.convert_videos and
            self.video_converter.needs_conversion(file_path)
        )

        # Determine what file we'll actually process (original or converted)
        processing_file = file_path
        if needs_conversion:
            # Create converted filename with .mp4 extension
            converted_name = file_path.stem + ".mp4"
            converted_path = file_path.parent / converted_name

            # Convert the video
            progress.update(task, description=f"Converting: {file_path.name}")
            if self.video_converter.convert_video(file_path, converted_path, progress, task):
                processing_file = converted_path
                self.stats['converted_videos'] += 1
                self.logger.info(f"Successfully converted {file_path} -> {converted_path}")
            else:
                self.logger.error(f"Failed to convert video: {file_path}")
                self.stats['errors'] += 1
                if not self.dry_run:
                    self._move_to_error_dir(file_path)
                return

        # Generate destination path based on the processing file
        dest_path = self.get_destination_path(processing_file, creation_date)

        # Check for duplicates
        if dest_path.exists() and self.is_duplicate(processing_file, dest_path):
            self.stats['duplicates'] += 1
            progress.update(task, description=f"Skipping duplicate: {processing_file.name}")

            # Clean up files if we're moving
            if self.move_files and not self.dry_run:
                try:
                    processing_file.unlink()
                    if needs_conversion and file_path != processing_file:
                        # Also remove the original if it still exists
                        if file_path.exists():
                            file_path.unlink()
                    self.logger.debug(f"Deleted duplicate source file: {processing_file}")
                except Exception as e:
                    self.logger.warning(f"Could not delete duplicate source file {processing_file}: {e}")

            return

        # Move processed file to destination
        if self.move_file_safely(processing_file, dest_path):
            self.stats['total_size'] += file_size

            # If we converted a video, archive the original to legacy videos directory
            if needs_conversion and not self.dry_run:
                self._ensure_legacy_videos_dir()
                try:
                    # Preserve relative path structure in legacy videos directory
                    relative_path = file_path.relative_to(self.source)
                    legacy_dest = self.legacy_videos_dir / relative_path

                    # Create parent directories if needed
                    legacy_dest.parent.mkdir(parents=True, exist_ok=True)

                    # Move original to legacy directory
                    if self.move_files:
                        file_path.rename(legacy_dest)
                    else:
                        shutil.copy2(str(file_path), str(legacy_dest))

                    self.logger.info(f"Archived original video: {file_path} -> {legacy_dest}")
                except Exception as e:
                    self.logger.warning(f"Could not archive original video {file_path}: {e}")

            # Update stats
            if is_video:
                self.stats['videos'] += 1
            else:
                self.stats['photos'] += 1

            progress.update(task, description=f"Processed: {file_path.name}")
        else:
            self.stats['errors'] += 1
            if not self.dry_run:
                self._move_to_error_dir(file_path)
                # Clean up converted file if conversion happened but move failed
                if needs_conversion and processing_file != file_path and processing_file.exists():
                    try:
                        processing_file.unlink()
                    except Exception:
                        pass

    def _move_to_error_dir(self, file_path: Path) -> None:
        """Move problematic file to error directory."""
        self._ensure_error_dir()
        try:
            error_dest = self.error_dir / file_path.name
            counter = 1
            while error_dest.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                error_dest = self.error_dir / f"{stem}_{counter:03d}{suffix}"
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
        table.add_row("Videos Converted", str(self.stats['converted_videos']))
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
