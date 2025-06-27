#!/usr/bin/env python3

"""
photosort - Organize photos and videos into year/month folder structure.

A modern Python tool for organizing unstructured photo and video collections
into a clean year/month directory structure based on file creation dates.

Created with the assistance of Claude Code on 2025-06-24.
"""

import argparse
import grp
import hashlib
import logging
import os
import re
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
NUISANCE_EXTENSIONS = (
    ".ds_store", ".thumbs.db", ".desktop.ini", "thumbs.db"
)
VALID_EXTENSIONS = PHOTO_EXTENSIONS + MOVIE_EXTENSIONS

# TODO: Future enhancement - Add ffmpeg video conversion for legacy formats
# Goal: Convert old formats (mpg, 3gp, etc.) to modern mp4/h264


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
        
        summary = (
            f"{timestamp} | {status} | "
            f"Source: {source} | Dest: {dest} | "
            f"Files: {total_files} ({stats['photos']} photos, {stats['videos']} videos, "
            f"{stats['metadata']} metadata) | "
            f"Size: {size_mb:.1f}MB | Duplicates: {stats['duplicates']} | "
            f"Errors: {stats['errors']} | History: {self.import_folder_name}\n"
        )
        
        # Append to imports log
        with open(self.imports_log, 'a', encoding='utf-8') as f:
            f.write(summary)


class Config:
    """Manages configuration file for storing user preferences."""

    def __init__(self, config_path: Optional[Path] = None):
        # New location: ~/.photosort/config.yml
        if config_path:
            self.config_path = config_path
        else:
            new_config = Path.home() / ".photosort" / "config.yml"
            old_config = Path.home() / ".config" / "photosort" / "photosort.yml"
            
            # Check if old config exists and new doesn't - migrate it
            if old_config.exists() and not new_config.exists():
                self._migrate_config(old_config, new_config)
            
            self.config_path = new_config
            
        self.data = self._load_config()
    
    def _migrate_config(self, old_path: Path, new_path: Path) -> None:
        """Migrate config from old location to new location."""
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_path, new_path)
            # Use a logger instance instead of root logger
            logger = logging.getLogger("photosort")
            logger.info(f"Migrated config from {old_path} to {new_path}")
        except Exception as e:
            logger = logging.getLogger("photosort")
            logger.warning(f"Could not migrate config: {e}")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger = logging.getLogger("photosort")
            logger.warning(f"Could not load config: {e}")
            return {}

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.data, f, default_flow_style=False)
        except Exception as e:
            logger = logging.getLogger("photosort")
            logger.error(f"Could not save config: {e}")

    def get_last_source(self) -> Optional[str]:
        """Get the last used source directory."""
        return self.data.get('last_source')

    def get_last_dest(self) -> Optional[str]:
        """Get the last used destination directory."""
        return self.data.get('last_dest')

    def get_file_mode(self) -> Optional[str]:
        """Get the saved file mode setting."""
        return self.data.get('file_mode')

    def get_group(self) -> Optional[str]:
        """Get the saved group setting."""
        return self.data.get('group')

    def update_paths(self, source: str, dest: str) -> None:
        """Update and save the last used paths."""
        self.data['last_source'] = source
        self.data['last_dest'] = dest
        self.save_config()

    def update_file_mode(self, mode: str) -> None:
        """Update and save the file mode setting."""
        self.data['file_mode'] = mode
        self.save_config()

    def update_group(self, group: str) -> None:
        """Update and save the group setting."""
        self.data['group'] = group
        self.save_config()


class PhotoSorter:
    """Main class for organizing photos and videos."""

    def __init__(self, source: Path, dest: Path, dry_run: bool = False,
                 move_files: bool = True, file_mode: Optional[int] = None,
                 group_gid: Optional[int] = None):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = file_mode
        self.group_gid = group_gid
        self.console = Console()
        self.stats = {
            'photos': 0, 'videos': 0, 'metadata': 0,
            'duplicates': 0, 'errors': 0, 'total_size': 0
        }

        # Setup history manager for import tracking and auxiliary directories
        self.history_manager = HistoryManager(dest, dry_run)

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
        timestamp = creation_date.strftime("%Y-%m-%d_%H-%M-%S")
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

        # Generate destination path
        dest_path = self.get_destination_path(file_path, creation_date)

        # Check for duplicates
        if dest_path.exists() and self.is_duplicate(file_path, dest_path):
            self.stats['duplicates'] += 1
            progress.update(task, description=f"Skipping duplicate: {file_path.name}")
            
            # Delete the duplicate source file if we're moving files
            if self.move_files and not self.dry_run:
                try:
                    file_path.unlink()
                    self.logger.debug(f"Deleted duplicate source file: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Could not delete duplicate source file {file_path}: {e}")
            
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
        self._ensure_error_dir()
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


def cleanup_source_directory(source: Path, history_manager: HistoryManager, console: Console) -> None:
    """Clean up source directory by removing empty folders and moving unknown files."""
    if not any(source.iterdir()):
        return
    
    console.print("Cleaning source folder...")
    
    # First, remove all nuisance files recursively
    nuisance_count = 0
    for file_path in source.rglob("*"):
        if file_path.is_file() and file_path.name.lower() in NUISANCE_EXTENSIONS:
            try:
                file_path.unlink()
                nuisance_count += 1
            except Exception as e:
                console.print(f"[yellow]Warning: Could not remove {file_path}: {e}[/yellow]")
    
    if nuisance_count > 0:
        console.print(f"Removed {nuisance_count} nuisance files (.DS_Store, etc.)")
    
    # Recursively prune empty subfolders from the source tree
    for thisdir, subdirs, _ in os.walk(source, topdown=False):
        for thissubdir in subdirs:
            try:
                os.rmdir(Path(thisdir) / thissubdir)
            except OSError:
                pass

    # Move remaining unknown files to history folder
    unknowns = list(source.glob("*"))
    if unknowns:
        console.print(f"Moving {len(unknowns)} unknown files...")
        unkpath = history_manager.get_unknown_files_dir()
        unkpath.mkdir(parents=True, exist_ok=True)
        for remaining in unknowns:
            shutil.move(remaining, unkpath / remaining.name)


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
