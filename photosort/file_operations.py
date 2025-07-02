"""
Shared file operations and utilities for PhotoSorter and LivePhotoProcessor.
"""

import hashlib
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import JPG_EXTENSIONS, NUISANCE_EXTENSIONS, PROGRAM


class FileOperations:
    """Utility class for shared file operations."""

    def __init__(self, dry_run: bool, move_files: bool, mode: Optional[int],
                 gid: Optional[int]):
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = mode
        self.group_gid = gid
        self.logger = logging.getLogger(PROGRAM)
        self.sips_available = FileOperations.check_tool_availability("sips", "-v")

    @staticmethod
    def check_tool_availability(cmd: str, version_flag: str = "-h") -> bool:
        """Check availability of a command-line tool on this system."""
        try:
            subprocess.run([cmd, version_flag], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

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

        # For small files, also check content hash
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
        """Move file with validation."""
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
        """Create directory if needed and not in dry-run mode."""
        if not self.dry_run and not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

    def image_creation_date(self, image_path: Path) -> str:
        """Get creation time for any image using sips or file modification time."""
        if self.sips_available:
            try:
                result = subprocess.run(
                    ["sips", "-g", "creation", str(image_path)],
                    capture_output=True, text=True, check=True
                )

                # Parse sips output
                for line in result.stdout.split('\n'):
                    if 'creation:' in line:
                        date_str = line.split('creation: ')[1].strip()
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

            except (subprocess.CalledProcessError, Exception):
                pass

        # Fallback to file modification time for photos
        return datetime.fromtimestamp(image_path.stat().st_mtime)

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
        except Exception as e:
            self.logger.error(f"Failed to set group on {file_path}: {e}")

    def create_unique_error_path(self, error_dir: Path, file_path: Path) -> Path:
        """Generate unique error file path with counter if needed."""
        error_dest = error_dir / file_path.name
        counter = 1
        while error_dest.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            error_dest = error_dir / f"{stem}_{counter:03d}{suffix}"
            counter += 1
        return error_dest

    def move_to_error_directory(self, file_path: Path, error_dir: Path) -> None:
        """Move problematic file to error directory."""
        self.ensure_directory(error_dir)

        try:
            error_dest = self.create_unique_error_path(error_dir, file_path)
            if not self.dry_run:
                shutil.copy2(str(file_path), str(error_dest))
            self.logger.debug(f"Moved error file: {file_path} -> {error_dest}")
        except Exception as e:
            self.logger.error(f"Could not move error file {file_path}: {e}")

    def archive_original_video(self, original_path: Path, source_root: Path,
                               legacy_dir: Path, move_files: bool) -> bool:
        """Archive original video to legacy directory preserving relative path."""
        try:
            # Preserve relative path structure in legacy videos directory
            relative_path = original_path.relative_to(source_root)
            legacy_dest = legacy_dir / relative_path

            # Create parent directories if needed
            self.ensure_directory(legacy_dest.parent)

            if not self.dry_run:
                if move_files:
                    # MOVE mode: move original to legacy directory
                    original_path.rename(legacy_dest)
                else:
                    # COPY mode: copy original to legacy directory
                    shutil.copy2(str(original_path), str(legacy_dest))

            self.logger.info(f"Archived original video: {original_path} -> {legacy_dest}")
            return True
        except Exception as e:
            self.logger.warning(f"Could not archive original video {original_path}: {e}")
            return False

    def handle_conversion_cleanup(self, needs_conversion: bool, move_files: bool,
                                  original_path: Path, processing_path: Path,
                                  temp_converted_file: Optional[Path], source_root: Path,
                                  legacy_dir: Path) -> None:
        """Handle cleanup after video conversion based on mode."""
        if not needs_conversion or self.dry_run:
            return

        # Archive original video
        self.archive_original_video(original_path, source_root, legacy_dir, move_files)

        # Clean up temp converted file in COPY mode
        if not move_files and temp_converted_file and temp_converted_file.exists():
            try:
                temp_converted_file.unlink()
                self.logger.debug(f"Cleaned up temp converted file: {temp_converted_file}")
            except Exception as e:
                self.logger.warning(f"Could not clean up temp file {temp_converted_file}: {e}")

    def handle_duplicate_cleanup(self, processing_file: Path, original_file: Path,
                                 needs_conversion: bool, move_files: bool,
                                 temp_converted_file: Optional[Path]) -> None:
        """Handle cleanup when duplicate files are detected."""
        if self.dry_run:
            return

        if move_files:
            # MOVE mode: delete source files
            try:
                processing_file.unlink()
                if needs_conversion and original_file != processing_file and original_file.exists():
                    original_file.unlink()
                self.logger.debug(f"Deleted duplicate source file: {processing_file}")
            except Exception as e:
                self.logger.warning(f"Could not delete duplicate source file {processing_file}: {e}")
        else:
            # COPY mode: clean up temp converted file only
            if temp_converted_file and temp_converted_file.exists():
                try:
                    temp_converted_file.unlink()
                    self.logger.debug(f"Cleaned up temp converted file: {temp_converted_file}")
                except Exception as e:
                    self.logger.warning(f"Could not clean up temp file {temp_converted_file}: {e}")

    def cleanup_failed_conversion(self, original_file: Path, processing_file: Path,
                                  temp_converted_file: Optional[Path], error_dir: Path) -> None:
        """Clean up files when conversion fails."""
        if self.dry_run:
            return

        # Clean up temp file if conversion failed
        if temp_converted_file and temp_converted_file.exists():
            try:
                temp_converted_file.unlink()
            except Exception:
                pass

        # Move original to error directory
        self.move_to_error_directory(original_file, error_dir)

    def cleanup_failed_move(self, original_file: Path, processing_file: Path,
                            temp_converted_file: Optional[Path], needs_conversion: bool,
                            error_dir: Path) -> None:
        """Clean up files when move operation fails."""
        if self.dry_run:
            return

        # Move original to error directory
        self.move_to_error_directory(original_file, error_dir)

        # Clean up converted file if conversion happened but move failed
        if needs_conversion and processing_file != original_file and processing_file.exists():
            try:
                processing_file.unlink()
            except Exception:
                pass

        # Also clean up temp file in COPY mode
        if temp_converted_file and temp_converted_file.exists():
            try:
                temp_converted_file.unlink()
            except Exception:
                pass

    def cleanup_source_directory(self, source: Path, unsorted_path: Path) -> None:
        """Clean up source by pruning empty folders and moving unknown files."""
        if not any(source.iterdir()):
            return

        self.logger.info("Cleaning source folder...")

        # First, remove all nuisance files recursively
        nuisance_count = 0
        for file_path in source.rglob("*"):
            if file_path.is_file() and file_path.name.lower() in NUISANCE_EXTENSIONS:
                try:
                    file_path.unlink()
                    nuisance_count += 1
                except Exception as e:
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

    def update_file_stats(self, stats: dict, is_video: bool, file_size: int) -> None:
        """Update statistics for processed files."""
        if is_video:
            stats['videos'] += 1
        else:
            stats['photos'] += 1
        stats['total_size'] += file_size

