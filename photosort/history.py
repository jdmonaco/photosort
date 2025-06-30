"""
Import history management for photosort.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict
import logging


class HistoryManager:
    """Manages import history, logging, and auxiliary directory placement."""
    
    def __init__(self, dest_path: Path, dry_run: bool = False):
        self.dest_path = dest_path
        self.dry_run = dry_run
        self.photosort_dir = Path.home() / ".photosort"
        self.history_dir = self.photosort_dir / "history"
        self.imports_log = self.photosort_dir / "imports.log"
        
        # Create timestamped import folder name
        timestamp = datetime.now().strftime("%Y-%m-%d")
        dest_name = self._sanitize_dest_name(dest_path)
        self.import_folder_name = f"{timestamp}+{dest_name}"
        self.import_folder = self.history_dir / self.import_folder_name
        self.import_log = self.import_folder / "import.log"
        
        # Set up directories and logging if not dry run
        if not dry_run:
            self._setup_import_session()
    
    def _sanitize_dest_name(self, dest_path: Path) -> str:
        """Convert destination path to safe folder name."""
        # Use the last component of the path, sanitize for filesystem
        name = dest_path.name
        # Replace problematic characters with hyphens
        sanitized = re.sub(r'[^\w\-_]', '-', name)
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        return sanitized.strip('-')
    
    def _setup_import_session(self) -> None:
        """Create import folder and setup logging."""
        # Create directories
        self.import_folder.mkdir(parents=True, exist_ok=True)
        
        # Handle folder name collisions by adding suffix
        original_folder = self.import_folder
        counter = 2
        while self.import_folder.exists() and any(self.import_folder.iterdir()):
            self.import_folder_name = f"{original_folder.name}-{counter}"
            self.import_folder = self.history_dir / self.import_folder_name
            self.import_log = self.import_folder / "import.log"
            counter += 1
        
        # Create final import folder
        self.import_folder.mkdir(parents=True, exist_ok=True)
    
    def setup_import_logger(self, logger: logging.Logger) -> None:
        """Configure logger to write to import-specific log file."""
        if self.dry_run:
            return
            
        # Add file handler for import-specific logging
        file_handler = logging.FileHandler(self.import_log)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    
    def log_import_summary(self, source: Path, dest: Path, stats: Dict, success: bool) -> None:
        """Log import summary to global imports.log."""
        if self.dry_run:
            return
            
        # Ensure photosort directory exists
        self.photosort_dir.mkdir(exist_ok=True)
        
        # Format summary record
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if success else "PARTIAL"
        total_files = stats['photos'] + stats['videos'] + stats['metadata']
        size_mb = stats['total_size'] / (1024 * 1024)
        
        converted_info = ""
        if stats.get('converted_videos', 0) > 0:
            converted_info = f" | Converted: {stats['converted_videos']} videos"
        
        summary = (
            f"{timestamp} | {status} | "
            f"Source: {source} | Dest: {dest} | "
            f"Files: {total_files} ({stats['photos']} photos, {stats['videos']} videos, "
            f"{stats['metadata']} metadata) | "
            f"Size: {size_mb:.1f}MB | Duplicates: {stats['duplicates']} | "
            f"Errors: {stats['errors']}{converted_info} | History: {self.import_folder_name}\n"
        )
        
        # Append to imports log
        with open(self.imports_log, 'a', encoding='utf-8') as f:
            f.write(summary)