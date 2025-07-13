"""
Core photo sorting functionality.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table

from .constants import (get_console, get_logger, JPG_EXTENSIONS, METADATA_EXTENSIONS,
                        MOVIE_EXTENSIONS, PHOTO_EXTENSIONS, PROGRAM, VALID_EXTENSIONS)
from .conversion import VideoConverter, ConversionResult
from .file_operations import FileOperations
from .history import HistoryManager
from .livephoto import LivePhotoProcessor
from .progress import ProgressContext
from .stats import StatsManager
from .timestamps import get_image_creation_date, get_video_creation_date


class PhotoSorter:
    """Main class for organizing photos and videos."""

    def __init__(self, source: Path, dest: Path, root_dir: Optional[Path],
                 dry_run: bool = False, move_files: bool = True,
                 file_mode: Optional[int] = None, group_gid: Optional[int] = None,
                 timezone: str = "America/New_York", convert_videos: bool = True):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = file_mode
        self.group_gid = group_gid
        self.timezone = timezone
        self.convert_videos = convert_videos
        self.root_dir = root_dir or Path.home() / f".{PROGRAM}"
        self.stats_manager = StatsManager()

        # Setup logging with separate console and file levels
        self.console = get_console()
        console_handler = RichHandler(console=self.console, rich_tracebacks=True)
        console_handler.setLevel(logging.WARNING)  # Only WARNING and ERROR to console
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.basicConfig(
            level=logging.DEBUG,  # Allow all messages to reach handlers
            format="%(message)s",
            datefmt="[%X]",
            handlers=[console_handler]
        )
        self.logger = get_logger()

        # Initialize file operations utility
        self.file_ops = FileOperations(dry_run=dry_run, source=self.source,
                   move_files=move_files, mode=self.file_mode, gid=self.group_gid)

        # Setup history manager for import tracking and auxiliary directories
        self.history_manager = HistoryManager(dest_path=dest, root_dir=self.root_dir,
                                              file_ops=self.file_ops)
        self.history_manager.setup_import_logger(self.logger)

        # Setup video converter
        self.video_converter = VideoConverter(file_ops=self.file_ops, convert_videos=convert_videos)

        # Log the start of import session
        self.logger.info(f"Starting import session: {self.source} -> {self.dest}")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'MOVE' if self.move_files else 'COPY'}")

        # Retrieve directory paths from history manager
        self.unsorted_dir = self.history_manager.get_unsorted_dir()
        self.metadata_dir = self.history_manager.get_metadata_dir()
        self.legacy_dir = self.history_manager.get_legacy_videos_dir()

        # Initialize Live Photo processor with dependencies
        self.live_photo_processor = LivePhotoProcessor(
            source=source, dest=dest, video_converter=self.video_converter,
            history_manager=self.history_manager, file_ops=self.file_ops,
            stats_manager=self.stats_manager
        )

    def get_creation_date(self, file_path: Path) -> datetime:
        """Extract creation date from file metadata."""
        # Handle video files with ffprobe
        if file_path.suffix.lower() in MOVIE_EXTENSIONS:
            video_date = get_video_creation_date(file_path)
            if video_date:
                return video_date

        # Handle all other photo files
        return get_image_creation_date(file_path)

    def find_source_files(self) -> Tuple[List[Path], List[Path], Dict[str, Dict]]:
        """Find all files in source directory, separated by media files, metadata files, and Live Photo pairs."""
        media_files = []
        metadata_files = []

        # Media and metadata sorting
        for file_path in self.source.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in VALID_EXTENSIONS:
                    media_files.append(file_path)
                elif ext in METADATA_EXTENSIONS:
                    metadata_files.append(file_path)

        # Live Photo detection and sorting
        media_files, livephoto_pairs = self.live_photo_processor.detect_livephoto_pairs(media_files)

        if livephoto_pairs:
            self.logger.info(f"Detected {len(livephoto_pairs)} Live Photo pairs")

        return sorted(media_files), sorted(metadata_files), livephoto_pairs

    def get_destination_path(self, file_path: Path, creation_date: datetime) -> Tuple[Path, bool]:
        """Generate destination path and dupe check. Returns (dest_path, is_dupe)."""
        year = f"{creation_date.year:04d}"
        month = f"{creation_date.month:02d}"

        # Create destination path and filename from timestamp and counter
        counter = 0
        timestamp = creation_date.strftime("%Y%m%d_%H%M%S")
        ext = file_path.suffix.lower()
        ext = self.file_ops.normalize_jpg_extension(ext)
        dest_dir = self.dest / year / month
        dest_file = dest_dir / f"{timestamp}_{counter:03d}{ext}"

        # Handle filename conflicts (due to photo bursts) and report duplicates
        while dest_file.exists():
            if self.file_ops.is_duplicate(file_path, dest_file):
                return dest_file, True

            dest_file = dest_dir / f"{timestamp}_{counter:03d}{ext}"
            counter += 1

        return dest_file, False

    def process_metadata_files(self, metadata_files: List[Path],
                               progress_ctx: Optional[ProgressContext] = None) -> None:
        """Process metadata files by moving them to history Metadata directory."""
        if not metadata_files:
            return

        self.logger.info(f"Processing {len(metadata_files)} metadata files")
        self.file_ops.ensure_directory(self.metadata_dir)
        for file_path in metadata_files:
            try:
                # Preserve relative path structure in Metadata directory
                relative_path = file_path.relative_to(self.source)
                dest_path = self.metadata_dir / relative_path

                if self.file_ops.move_file_safely(file_path, dest_path):
                    self.stats_manager.increment_metadata()
                else:
                    self.stats_manager.increment_unsorted()
                    if not self.dry_run:
                        self.file_ops.archive_file(file_path, self.unsorted_dir, preserve_structure=False)

            except Exception as e:
                self.logger.error(f"Error processing metadata file {file_path}: {e}")
                self.stats_manager.increment_unsorted()
                if not self.dry_run:
                    self.file_ops.archive_file(file_path, self.unsorted_dir, preserve_structure=False)

            # Advance progress if context provided
            if progress_ctx:
                progress_ctx.advance()

    def process_livephoto_pairs(self, livephoto_pairs: Dict[str, Dict],
                                progress_ctx: Optional[ProgressContext] = None) -> None:
        """Process Live Photo pairs with shared basenames."""
        self.live_photo_processor.process_livephoto_pairs(livephoto_pairs, progress_ctx)

    def process_files(self, files: List[Path], progress_ctx: Optional[ProgressContext] = None) -> None:
        """Process all files with progress tracking."""
        self.logger.info(f"Starting to process {len(files)} files")

        # If no progress context provided, create our own
        if progress_ctx is None:
            with Progress(console=self.console) as progress:
                task = progress.add_task("Processing files...", total=len(files))
                progress_ctx = ProgressContext(progress, task)
                self._process_files_with_progress(files, progress_ctx)
        else:
            self._process_files_with_progress(files, progress_ctx)

    def _process_files_with_progress(self, files: List[Path], progress_ctx: ProgressContext) -> None:
        """Internal method to process files with a given progress context."""
        for file_path in files:
            try:
                self._process_single_file(file_path, progress_ctx)
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
                self.stats_manager.increment_unsorted()
                if not self.dry_run:
                    self.file_ops.archive_file(file_path, self.unsorted_dir, preserve_structure=False)

            progress_ctx.advance()

    def _process_single_file(self, file_path: Path, progress_ctx: ProgressContext) -> None:
        """Process a single media file."""
        # Check if file still exists before processing
        if not file_path.exists():
            self.logger.debug(f"Skipping {file_path} - file no longer exists (already processed)")
            return

        # Get file size before any operations
        file_size = file_path.stat().st_size

        # Get creation date
        creation_date = self.get_creation_date(file_path)

        # Handle video conversion if needed
        conversion = self.video_converter.handle_video_conversion(file_path, progress_ctx)
        if conversion.was_converted:
            if conversion.success:
                self.stats_manager.increment_converted_videos()
            else:
                # Fall back to the original source video file
                self.logger.warning(f"Processing original video file: {conversion.source_file}")
                conversion.processing_file = conversion.source_file

        # Generate destination path based on the processing file
        dest_path, is_dupe = self.get_destination_path(conversion.processing_file, creation_date)

        # Gracefully cleanup if duplicates found
        if is_dupe:
            self.stats_manager.increment_duplicates()
            progress_ctx.update(f"Skipping duplicate: {conversion.processing_file.name}")
            self.file_ops.delete_safely(conversion.source_file, conversion.temp_file)
            return

        # Move processed file to destination
        if self.file_ops.move_file_safely(conversion.processing_file, dest_path):
            # If we converted a video, handle cleanup based on mode
            if conversion.was_converted:
                self.file_ops.archive_file(conversion.source_file, self.legacy_dir,
                                           preserve_structure=True)
                self.file_ops.delete_safely(conversion.temp_file)

            # Update stats and progress
            self.stats_manager.record_successful_file(file_path, file_size)
            progress_ctx.update(f"Processed: {file_path.name}")
        else:
            if self.file_ops.archive_file(conversion.source_file, self.unsorted_dir):
                self.stats_manager.increment_unsorted()
            self.file_ops.delete_safely(conversion.temp_file)

    def print_summary(self) -> None:
        """Print processing summary."""
        table = Table(title="Processing Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="green")

        table.add_row("Photos", str(self.stats_manager.get_photos()))
        table.add_row("Videos", str(self.stats_manager.get_videos()))
        table.add_row("Live Photos", str(self.stats_manager.get_livephoto_pairs()))
        table.add_row("Metadata Files", str(self.stats_manager.get_metadata()))
        table.add_row("Videos Converted", str(self.stats_manager.get_converted_videos()))
        table.add_row("Duplicates Skipped", str(self.stats_manager.get_duplicates()))
        table.add_row("Unsorted", str(self.stats_manager.get_unsorted()))

        # Format total size
        size_mb = self.stats_manager.get_total_size_mb()
        if size_mb > 1024:
            size_str = f"{size_mb/1024:.1f} GB"
        else:
            size_str = f"{size_mb:.1f} MB"
        table.add_row("Total Size", size_str)

        # Print summary table
        self.console.print(table)

        if self.stats_manager.has_errors():
            self.console.print(f"\n[red]Unsorted files moved to: {self.unsorted_dir}[/red]")

