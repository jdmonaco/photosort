"""
Import history management for photosort.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, TYPE_CHECKING

from .file_operations import FileOperations

if TYPE_CHECKING:
    from .stats import StatsManager


class HistoryManager:
    """Manages import history, logging, and auxiliary directory placement."""

    def __init__(self, dest_path: Path, root_dir: Path, file_ops: FileOperations):
        self.dest_path = dest_path
        self.file_ops = file_ops
        self.root_dir = root_dir
        self.history_dir = self.root_dir / "history"
        self.imports_audit_log = self.root_dir / "imports.log"

        # Set up directories for auxiliary files and logging
        self._setup_import_session()

    def _setup_import_session(self) -> None:
        """Create import folder and setup logging."""
        # Create timestamped import folder name
        timestamp = datetime.now().strftime("%Y-%m-%d")
        dest_name = self._sanitize_dest_name(self.dest_path)
        folder_name = f"{timestamp}+{dest_name}"

        # Create initial import folder and handle collisions with a counter
        folder = self.history_dir / folder_name
        counter = 1
        while folder.exists() and any(folder.iterdir()):
            folder_name = f"{folder_name}-{counter:02d}"
            folder = self.history_dir / folder_name
            counter += 1

        # Create final import folder
        self.file_ops.ensure_directory(folder)
        self.import_folder = folder
        self.import_folder_name = folder_name
        self.import_log = folder / "import.log"

    def _sanitize_dest_name(self, dest_path: Path) -> str:
        """Convert destination path to safe folder name."""
        name = dest_path.name
        sanitized = re.sub(r'[^\w\-_]', '-', name)
        sanitized = re.sub(r'-+', '-', sanitized)
        return sanitized.strip('-')

    def setup_import_logger(self, logger: logging.Logger) -> None:
        """Configure logger to write to import-specific log file."""
        if self.file_ops.dry_run:
            return

        # Add file handler for import-specific logging
        file_handler = logging.FileHandler(self.import_log)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Ensure logger level allows DEBUG messages to reach the file handler
        logger.setLevel(logging.DEBUG)

    def get_metadata_dir(self) -> Path:
        """Get path for metadata files in import history."""
        return self.import_folder / "Metadata"

    def get_unknown_files_dir(self) -> Path:
        """Get path for unknown files in import history."""
        return self.import_folder / "UnknownFiles"

    def get_unsorted_dir(self) -> Path:
        """Get path for problematic files in import history."""
        return self.import_folder / "Unsorted"

    def get_legacy_videos_dir(self) -> Path:
        """Get path for legacy video files in import history."""
        return self.import_folder / "LegacyVideos"

    def log_import_summary(self, source: Path, dest: Path, stats_manager: "StatsManager", success: bool) -> None:
        """Log import summary to global imports.log."""
        if self.file_ops.dry_run:
            return

        # Ensure config directory exists
        self.root_dir.mkdir(exist_ok=True)

        # Format summary record
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if success else "PARTIAL"
        total_files = stats_manager.get_total_files()
        size_mb = stats_manager.get_total_size_mb()

        converted_info = ""
        if stats_manager.get_converted_videos() > 0:
            converted_info = f" | Converted: {stats_manager.get_converted_videos()} videos"

        summary = (
            f"{timestamp} | {status} | "
            f"Source: {source} | Dest: {dest} | "
            f"Files: {total_files} ({stats_manager.get_photos()} photos, {stats_manager.get_videos()} videos, "
            f"{stats_manager.get_metadata()} metadata) | "
            f"Size: {size_mb:.1f}MB | Duplicates: {stats_manager.get_duplicates()} | "
            f"Unsorted: {stats_manager.get_unsorted()}{converted_info} | History: {self.import_folder_name}\n"
        )

        # Append to imports log
        with open(self.imports_audit_log, 'a', encoding='utf-8') as f:
            f.write(summary)

