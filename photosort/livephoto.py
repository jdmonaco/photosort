"""
Live Photo processing functionality.
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.progress import Progress

from .constants import (get_console, get_logger, exiftool_available, JPG_EXTENSIONS,
                        MOVIE_EXTENSIONS, PROGRAM)
from .conversion import ConversionResult
from .progress import ProgressContext
from .timestamps import canonical_EXIF_date, get_image_creation_date


class LivePhotoProcessor:
    """Handles Apple Live Photo detection and processing."""

    def __init__(self, source: Path, dest: Path, video_converter, history_manager,
                 file_ops, stats_manager):
        self.source = source
        self.dest = dest
        self.video_converter = video_converter
        self.history_manager = history_manager
        self.file_ops = file_ops
        self.stats_manager = stats_manager
        self.logger = get_logger()
        self.console = get_console()

        # Directory paths for file operations
        self.unsorted_dir = self.history_manager.get_unsorted_dir()
        self.legacy_dir = self.history_manager.get_legacy_videos_dir()

    def detect_livephoto_pairs(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Detect LivePhoto pairs by matching Apple ContentIdentifier keys."""
        if exiftool_available:
            try:
                return self._detect_by_content_identifier(media_files)
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                self.logger.debug(f"exiftool failed or JSON parse error: {e}")
                return self._detect_by_basename_fallback(media_files)
        else:
            return self._detect_by_basename_fallback(media_files)

    def _detect_by_content_identifier(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Primary Live Photo detection using Apple ContentIdentifier metadata."""
        content_map = {}
        livephoto_pairs = {}
        non_livephoto_files = set()  # Use set to prevent duplicate entries

        img_ext = ('.heic', '.jpeg', '.jpg')
        mov_ext = ('.mov', '.mp4')
        lp_exts = img_ext + mov_ext

        # Get potential Live Photo files
        lp_candidates = [f for f in media_files if f.suffix.lower() in lp_exts]

        if not lp_candidates:
            return media_files, {}

        # Call exiftool for content id and dates for all possible candidate files
        exif_data = []

        # Process files in batches to reduce subprocess overhead
        batch_size = 100  # Process 100 files at a time

        # Create progress bar for EXIF scanning
        with Progress(console=self.console) as progress:
            scan_task = progress.add_task(
                f"[cyan]Scanning {len(lp_candidates)} files for Live Photos...[/cyan]",
                total=len(lp_candidates)
            )

            # Process files in batches
            for i in range(0, len(lp_candidates), batch_size):
                batch = lp_candidates[i:i + batch_size]

                # Call exiftool with multiple files at once
                cmd = [
                    "exiftool",
                    "-q",
                    "-json",
                    "-d", "%Y-%m-%dT%H:%M:%S%3f%z",
                    "-api", "QuickTimeUTC",
                    "-ContentIdentifier",
                    "-LivePhotoAuto",
                    "-SubSecCreateDate",
                    "-CreationDate",
                    "-CreationTime",
                    "-CreateDate",
                ]
                # Add all files in batch to command
                cmd.extend(str(f) for f in batch)

                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                # Parse JSON output - will be a list of objects, one per file
                json_data = json.loads(result.stdout)
                if isinstance(json_data, list):
                    exif_data.extend(json_data)

                # Update progress for the batch
                progress.update(scan_task, advance=len(batch))

        # Group files by ContentIdentifier
        for file_data in exif_data:
            content_id = file_data.get('ContentIdentifier')
            if not content_id:
                continue

            if content_id not in content_map:
                content_map[content_id] = {'image': None, 'video': None, 'dates': {}}

            file_path = Path(file_data['SourceFile'])
            file_ext = file_path.suffix.lower()

            # Categorize as image or video
            if file_ext in img_ext:
                content_map[content_id]['image'] = file_path
            elif file_ext in mov_ext:
                content_map[content_id]['video'] = file_path

            # Store all available dates for this file
            dates = {}
            for date_field in ['SubSecCreateDate', 'CreationDate', 'CreationTime', 'CreateDate']:
                if date_field in file_data:
                    dates[date_field] = file_data[date_field]

            if dates:
                content_map[content_id]['dates'].update(dates)

        # Process matched pairs
        for content_id, data in content_map.items():
            if data['image'] and data['video']:
                # Valid Live Photo pair found
                creation_date = canonical_EXIF_date(data['dates'])
                if creation_date:
                    if creation_date.microsecond:
                        milliseconds = int(creation_date.microsecond / 1000)
                    else:
                        milliseconds = 0

                    shared_basename = self._generate_shared_basename(creation_date, milliseconds)

                    livephoto_pairs[content_id] = {
                        'image_file': data['image'],
                        'video_file': data['video'],
                        'shared_basename': shared_basename,
                        'creation_date': creation_date,
                        'milliseconds': milliseconds
                    }

                    self.logger.debug(f"Live Photo detected: {data['image'].name} + {data['video'].name}")
                else:
                    # No valid date found, treat as individual files
                    non_livephoto_files.update([data['image'], data['video']])

        # Add files that weren't part of any Live Photo processing
        livephoto_file_paths = set()
        for pair_data in livephoto_pairs.values():
            livephoto_file_paths.add(pair_data['image_file'])
            livephoto_file_paths.add(pair_data['video_file'])

        for file_path in media_files:
            if file_path not in livephoto_file_paths:
                non_livephoto_files.add(file_path)

        return sorted(non_livephoto_files), livephoto_pairs

    def _detect_by_basename_fallback(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Fallback Live Photo detection using filename basename matching."""
        basename_map = {}
        livephoto_pairs = {}
        non_livephoto_files = set()  # Use set to prevent duplicate entries

        img_ext = ('.heic', '.jpeg', '.jpg')
        mov_ext = ('.mov', '.mp4')

        # Group by filename stem (e.g., IMG_1234)
        for file_path in media_files:
            ext = file_path.suffix.lower()
            if ext in img_ext or ext in mov_ext:
                basename = file_path.stem
                if basename not in basename_map:
                    basename_map[basename] = {'image': None, 'video': None}

                if ext in img_ext:
                    basename_map[basename]['image'] = file_path
                elif ext in mov_ext:
                    basename_map[basename]['video'] = file_path
            else:
                non_livephoto_files.add(file_path)

        # Process potential pairs
        for basename, data in basename_map.items():
            if data['image'] and data['video']:
                # Valid pair found, use image file's creation date
                try:
                    creation_date = get_image_creation_date(data['image'])
                    shared_basename = self._generate_shared_basename(creation_date, 0)

                    livephoto_pairs[basename] = {
                        'image_file': data['image'],
                        'video_file': data['video'],
                        'shared_basename': shared_basename,
                        'creation_date': creation_date,
                        'milliseconds': 0
                    }

                    self.logger.debug(f"Live Photo pair detected (basename): {data['image'].name} + {data['video'].name}")
                except Exception as e:
                    self.logger.debug(f"Failed to get creation date for {data['image']}: {e}")
                    non_livephoto_files.update([data['image'], data['video']])
            else:
                if data['image']:
                    non_livephoto_files.add(data['image'])
                if data['video']:
                    non_livephoto_files.add(data['video'])

        return sorted(non_livephoto_files), livephoto_pairs

    def _generate_shared_basename(self, creation_date: datetime, milliseconds: int) -> str:
        """Generate shared basename for Live Photo pair using milliseconds for counter."""
        timestamp = creation_date.strftime("%Y%m%d_%H%M%S")
        counter = milliseconds if milliseconds > 0 else 0
        return f"{timestamp}_{counter:03d}"

    def process_livephoto_pairs(self, livephoto_pairs: Dict[str, Dict], progress_ctx=None) -> None:
        """Process Live Photo pairs with shared basenames."""
        if not livephoto_pairs:
            return

        self.logger.info(f"Processing {len(livephoto_pairs)} Live Photo pairs")

        # If no progress context provided, create our own
        if progress_ctx is None:
            with Progress(console=self.console) as progress:
                task = progress.add_task("Processing Live Photos...", total=len(livephoto_pairs) * 2)
                progress_ctx = ProgressContext(progress, task)
                self._process_pairs_with_progress(livephoto_pairs, progress_ctx)
        else:
            self._process_pairs_with_progress(livephoto_pairs, progress_ctx)

    def _resolve_basename_collision(self, shared_basename: str, creation_date,
                                      image_file: Path, video_file: Path) -> str:
        """Check for destination collisions and adjust shared basename if needed."""
        year = f"{creation_date.year:04d}"
        month = f"{creation_date.month:02d}"
        dest_dir = self.dest / year / month

        img_ext = self.file_ops.normalize_jpg_extension(image_file.suffix.lower())
        vid_ext = video_file.suffix.lower()

        img_dest = dest_dir / f"{shared_basename}{img_ext}"
        vid_dest = dest_dir / f"{shared_basename}{vid_ext}"

        collision_suffix = 0
        while img_dest.exists() or vid_dest.exists():
            # If existing image is a duplicate of our source, the pair is a dupe
            if img_dest.exists() and self.file_ops.is_duplicate(image_file, img_dest):
                break
            collision_suffix += 1
            adjusted = f"{shared_basename}_{collision_suffix:02d}"
            img_dest = dest_dir / f"{adjusted}{img_ext}"
            vid_dest = dest_dir / f"{adjusted}{vid_ext}"

        if collision_suffix > 0:
            adjusted_basename = f"{shared_basename}_{collision_suffix:02d}"
            self.logger.info(f"LP basename collision resolved: {shared_basename} -> {adjusted_basename}")
            return adjusted_basename

        return shared_basename

    def _process_pairs_with_progress(self, livephoto_pairs: Dict[str, Dict], progress_ctx) -> None:
        """Internal method to process pairs with a given progress context."""
        # Sort pairs by image filename for deterministic processing order
        sorted_pairs = sorted(livephoto_pairs.items(), key=lambda x: str(x[1]['image_file']))
        for pair_id, pair_data in sorted_pairs:
            try:
                image_file = pair_data['image_file']
                video_file = pair_data['video_file']
                shared_basename = pair_data['shared_basename']
                creation_date = pair_data['creation_date']

                # Capture file sizes before processing (files may be moved)
                image_size = image_file.stat().st_size
                video_size = video_file.stat().st_size

                # Resolve basename collisions at destination
                shared_basename = self._resolve_basename_collision(
                    shared_basename, creation_date, image_file, video_file
                )

                # Process image file with shared basename
                success_image = self._process_livephoto_file(
                    image_file, shared_basename, creation_date, progress_ctx
                )

                # Process video file with shared basename
                success_video = self._process_livephoto_file(
                    video_file, shared_basename, creation_date, progress_ctx
                )

                lp_size = image_size + video_size

                if success_image and success_video:
                    self.stats_manager.increment_livephoto_pairs()
                    self.stats_manager.add_file_size(lp_size)
                    self.logger.debug(f"Successfully processed Live Photo pair: {image_file.name} + {video_file.name}")
                else:
                    self.logger.error(f"Failed to process Live Photo pair: {image_file.name} + {video_file.name}")
                    if success_image:
                        self.stats_manager.record_successful_file(image_file, image_size)
                    if success_video:
                        self.stats_manager.record_successful_file(video_file, video_size)

            except Exception as e:
                self.logger.error(f"Error processing Live Photo pair {pair_id}: {e}")
                for which in ['image_file', 'video_file']:
                    if self.file_ops.archive_file(pair_data[which], self.unsorted_dir):
                        self.stats_manager.increment_unsorted()

            progress_ctx.advance(2)

    def _process_livephoto_file(self, file_path: Path, shared_basename: str,
                                creation_date: datetime, progress_ctx: ProgressContext) -> bool:
        """Process a single Live Photo file with predetermined basename."""
        # Handle video conversion if needed
        conversion = self.video_converter.handle_video_conversion(file_path, progress_ctx, "photosort_lp")
        if conversion.was_converted:
            if conversion.success:
                self.stats_manager.increment_converted_videos()
            else:
                # Fall back to the original source video file
                self.logger.warning(f"Processing original Live Photo video file: {conversion.source_file}")
                conversion.processing_file = conversion.source_file

        # Generate destination path using shared basename
        year = f"{creation_date.year:04d}"
        month = f"{creation_date.month:02d}"
        dest_dir = self.dest / year / month
        ext = conversion.processing_file.suffix.lower()
        ext = self.file_ops.normalize_jpg_extension(ext)
        dest_path = dest_dir / f"{shared_basename}{ext}"

        # Check for duplicate file at destination path
        if self.file_ops.is_duplicate(conversion.processing_file, dest_path):
            self.stats_manager.increment_duplicates()
            progress_ctx.update(f"Skipping duplicate Live Photo: {conversion.processing_file.name}")
            self.file_ops.delete_safely(conversion.source_file, conversion.temp_file)
            return True

        # Move processed file to destination
        if self.file_ops.move_file_safely(conversion.processing_file, dest_path):
            # If we converted a video, handle cleanup based on mode
            if conversion.was_converted:
                self.file_ops.archive_file(conversion.source_file, self.legacy_dir,
                                           preserve_structure=True)
                self.file_ops.delete_safely(conversion.temp_file)

            # Update progress and return
            progress_ctx.update(f"Processed Live Photo: {file_path.name}")
            return True
        else:
            if self.file_ops.archive_file(file_path, self.unsorted_dir):
                self.stats_manager.increment_unsorted()
            self.file_ops.delete_safely(conversion.temp_file)
            return False

