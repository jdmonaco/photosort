"""
Shared file operations and utilities for photo and video organization.
"""

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .constants import (get_logger, exiftool_available, sips_available, JPG_EXTENSIONS,
                        NUISANCE_EXTENSIONS, PROGRAM)


class FileOperations:
    """Utility class for file operations, duplicate detection, permissions, and cleanup."""

    def __init__(self, dry_run: bool, source: Path, move_files: bool, mode: Optional[int],
                 gid: Optional[int]):
        self.dry_run = dry_run
        self.source = source
        self.move_files = move_files
        self.file_mode = mode
        self.group_gid = gid
        self.logger = get_logger()

    @staticmethod
    def normalize_jpg_extension(ext: str) -> str:
        """Normalize JPG extensions to .jpg."""
        if ext.lower() in JPG_EXTENSIONS:
            return ".jpg"
        return ext.lower()

    @staticmethod
    def is_duplicate(source_file: Path, dest_file: Path,
                     hash_size: Optional[int] = 10) -> bool:
        """Check if files are duplicates based on size and content."""
        if not dest_file.exists():
            return False

        # Quick size check
        if source_file.stat().st_size != dest_file.stat().st_size:
            return False

        # For same-sized files, also check content hash (up to hash_size limit)
        return FileOperations.same_size_same_hash(source_file, dest_file, hash_size)

    @staticmethod
    def same_size_same_hash(file1: Path, file2: Path,
                             check_limit: Optional[int]) -> bool:
        """Compare SHA-256 hashes of same-sized files up to optional limit (in MB)."""
        size_limit = check_limit * 1024 * 1024 if check_limit else None
        bytes_processed = 0

        try:
            hash1 = hashlib.sha256()
            hash2 = hashlib.sha256()

            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                while True:
                    chunk1 = f1.read(8192)
                    chunk2 = f2.read(8192)

                    # Both should end together since same size
                    if not chunk1:
                        break

                    # Check size limit before hashing
                    if size_limit and bytes_processed + len(chunk1) > size_limit:
                        break

                    hash1.update(chunk1)
                    hash2.update(chunk2)
                    bytes_processed += len(chunk1)  # Same as len(chunk2)

            return hash1.hexdigest() == hash2.hexdigest()
        except Exception:
            return False

    def move_file_safely(self, source: Path, dest: Path) -> bool:
        """Move or copy file with validation, permissions, and dry-run support."""
        if self.dry_run:
            return True

        try:
            # Create destination directory
            self.ensure_directory(dest.parent)

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
            self.apply_file_permissions(dest)

            # Apply file group ownership if specified
            self.apply_file_group(dest)

            # Log the successful move
            self.logger.info(f"{source} -> {dest}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to move {source} -> {dest}: {e}")
            return False

    def ensure_directory(self, directory: Path) -> None:
        """Create directory and parents if needed, with dry-run support."""
        if not self.dry_run and not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

    def apply_file_permissions(self, file_path: Path) -> None:
        """Apply file permissions if mode is specified."""
        if self.dry_run or self.file_mode is None:
            return

        try:
            os.chmod(file_path, self.file_mode)
        except Exception as e:
            self.logger.error(f"Failed to set permissions on {file_path}: {e}")

    def apply_file_group(self, file_path: Path) -> None:
        """Apply file group ownership if gid is specified."""
        if self.dry_run or self.group_gid is None:
            return

        try:
            os.chown(file_path, -1, self.group_gid)  # -1 preserves current owner
        except PermissionError as e:
            # Permission errors are common on systems without elevated privileges
            self.logger.debug(f"Permission denied setting group on {file_path}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to set group on {file_path}: {e}")

    def create_unique_path(self, dest_dir: Path, file_path: Path) -> Path:
        """Generate unique file path with counter if needed."""
        stem = file_path.stem
        suffix = file_path.suffix
        dest_path = dest_dir / file_path.name
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter:03d}{suffix}"
            counter += 1
        return dest_path

    def delete_safely(self, *files_to_delete: Optional[Path]) -> bool:
        """Unlink the file path(s) provided. Return all(success)."""
        if self.dry_run:
            return True

        success = True
        for file_to_delete in files_to_delete:
            if file_to_delete and file_to_delete.exists():
                # Never delete files in the source tree in COPY mode
                if not self.move_files:
                    if self.source in file_to_delete.parents:
                        continue

                try:
                    file_to_delete.unlink()
                except Exception:
                    success = False

        return success

    def archive_file(self, file_path: Path, archive_dir: Path,
                     preserve_structure: bool = True, source_root: Optional[Path] = None) -> bool:
        """Archive a source file to specified directory with optional path preservation."""
        if self.dry_run:
            return True

        # Gracefully return silently if file to be archived does not exist
        if not file_path.exists():
            return False

        try:
            if preserve_structure and source_root:
                # Preserve relative path structure
                relative_path = file_path.relative_to(source_root)
                dest_path = archive_dir / relative_path
            else:
                # Simple move to archive directory with unique naming
                dest_path = self.create_unique_path(archive_dir, file_path)

            self.ensure_directory(dest_path.parent)

            if self.move_files:
                shutil.move(str(file_path), str(dest_path))
            else:
                shutil.copy2(str(file_path), str(dest_path))

            self.logger.info(f"Archived: {file_path} -> {dest_path}")
            return True
        except Exception as e:
            self.logger.warning(f"Could not archive {file_path}: {e}")
            return False

    def cleanup_source_directory(self, source: Path, unsorted_path: Path) -> None:
        """Clean up source directory in MOVE mode by removing nuisance files,
        pruning empty folders, and archiving unknown files."""
        if self.dry_run or not self.move_files or not any(source.iterdir()):
            return

        self.logger.info("Cleaning source folder...")

        # First, remove all nuisance files recursively
        nuisance_count = 0
        for file_path in source.rglob("*"):
            if file_path.is_file() and file_path.name.lower() in NUISANCE_EXTENSIONS:
                if self.delete_safely(file_path):
                    nuisance_count += 1
                else:
                    self.logger.warning(f"[yellow]Warning: Could not remove {file_path}: {e}[/yellow]")

        if nuisance_count > 0:
            self.logger.info(f"Removed {nuisance_count} nuisance files (.DS_Store, etc.)")

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
            self.logger.info(f"Moving {len(unknowns)} unknown files...")
            self.ensure_directory(unsorted_path)
            for remaining in unknowns:
                shutil.move(remaining, unsorted_path / remaining.name)

