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

from rich.console import Console
from rich.progress import Progress

from .constants import JPG_EXTENSIONS, MOVIE_EXTENSIONS, PROGRAM, get_logger
from .conversion import ConversionResult
from .progress import ProgressContext


class LivePhotoProcessor:
    """Handles Apple Live Photo detection and processing."""

    def __init__(self, source: Path, dest: Path, dry_run: bool = False,
                 move_files: bool = True, file_mode: Optional[int] = None,
                 group_gid: Optional[int] = None, convert_videos: bool = True,
                 video_converter=None, history_manager=None, file_ops=None,
                 stats: Optional[Dict] = None):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = file_mode
        self.group_gid = group_gid
        self.convert_videos = convert_videos
        self.video_converter = video_converter
        self.history_manager = history_manager
        self.file_ops = file_ops
        self.unsorted_dir = self.history_manager.get_unsorted_dir()
        self.legacy_dir = self.history_manager.get_legacy_videos_dir()
        self.stats = stats or {}
        self.logger = get_logger()

    def detect_livephoto_pairs(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Detect LivePhoto pairs by matching Apple ContentIdentifier keys."""
        if self.file_ops.check_tool_availability("exiftool", "-ver"):
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
        non_livephoto_files = []

        img_ext = ('.heic', '.jpeg', '.jpg')
        mov_ext = ('.mov', '.mp4')
        lp_exts = img_ext + mov_ext

        # Get potential Live Photo files
        lp_candidates = [f for f in media_files if f.suffix.lower() in lp_exts]

        if not lp_candidates:
            return media_files, {}

        # Call exiftool for content id and dates for all possible file types
        result = subprocess.run([
            "exiftool",
            "-q",
            "-json",
            "-api", "QuickTimeUTC",
            "-Make",
            "-CreateDate",
            "-CreationDate",
            "-SubSecCreateDate",
            "-LivePhotoAuto",
            "-ContentIdentifier"] +
            [str(f) for f in lp_candidates],
            capture_output=True, text=True, check=True)

        # Parse JSON output
        exif_data = json.loads(result.stdout)

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
            for date_field in ['SubSecCreateDate', 'CreationDate', 'CreateDate']:
                if date_field in file_data:
                    dates[date_field] = file_data[date_field]

            if dates:
                content_map[content_id]['dates'].update(dates)

        # Process matched pairs
        for content_id, data in content_map.items():
            if data['image'] and data['video']:
                # Valid Live Photo pair found
                creation_date, milliseconds = self._parse_livephoto_date(data['dates'])
                if creation_date:
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
                    non_livephoto_files.extend([data['image'], data['video']])
            else:
                # Incomplete pair, add individual files
                if data['image']:
                    non_livephoto_files.append(data['image'])
                if data['video']:
                    non_livephoto_files.append(data['video'])

        # Add files that weren't part of any Live Photo processing
        livephoto_file_paths = set()
        for pair_data in livephoto_pairs.values():
            livephoto_file_paths.add(pair_data['image_file'])
            livephoto_file_paths.add(pair_data['video_file'])

        for file_path in media_files:
            if file_path not in livephoto_file_paths:
                non_livephoto_files.append(file_path)

        return non_livephoto_files, livephoto_pairs

    def _detect_by_basename_fallback(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Fallback Live Photo detection using filename basename matching."""
        basename_map = {}
        livephoto_pairs = {}
        non_livephoto_files = []

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
                non_livephoto_files.append(file_path)

        # Process potential pairs
        for basename, data in basename_map.items():
            if data['image'] and data['video']:
                # Valid pair found, use image file's creation date
                try:
                    creation_date = self.file_ops.image_creation_date(data['image'])
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
                    non_livephoto_files.extend([data['image'], data['video']])
            else:
                if data['image']:
                    non_livephoto_files.append(data['image'])
                if data['video']:
                    non_livephoto_files.append(data['video'])

        return non_livephoto_files, livephoto_pairs

    def _parse_livephoto_date(self, dates: Dict[str, str]) -> Tuple[Optional[datetime], int]:
        """Parse Live Photo creation date with millisecond precision."""
        # Priority: SubSecCreateDate > CreationDate > CreateDate
        for date_field in ['SubSecCreateDate', 'CreationDate', 'CreateDate']:
            if date_field in dates:
                date_str = dates[date_field]
                try:
                    if date_field == 'SubSecCreateDate':
                        # Parse with subsecond precision: "2024:12:25 14:30:22.045"
                        if '.' in date_str:
                            main_part, subsec_part = date_str.split('.')
                            dt = datetime.strptime(main_part, "%Y:%m:%d %H:%M:%S")
                            milliseconds = int(subsec_part[:3].ljust(3, '0'))
                            return dt, milliseconds
                        else:
                            # No subseconds available
                            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                            return dt, 0
                    else:
                        # Standard date format without subseconds
                        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        return dt, 0
                except ValueError:
                    continue

        return None, 0

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
            console = Console()
            with Progress(console=console) as progress:
                task = progress.add_task("Processing Live Photos...", total=len(livephoto_pairs) * 2)
                progress_ctx = ProgressContext(progress, task)
                self._process_pairs_with_progress(livephoto_pairs, progress_ctx)
        else:
            self._process_pairs_with_progress(livephoto_pairs, progress_ctx)

    def _process_pairs_with_progress(self, livephoto_pairs: Dict[str, Dict], progress_ctx) -> None:
        """Internal method to process pairs with a given progress context."""
        for pair_id, pair_data in livephoto_pairs.items():
            try:
                image_file = pair_data['image_file']
                video_file = pair_data['video_file']
                shared_basename = pair_data['shared_basename']
                creation_date = pair_data['creation_date']

                # Process image file with shared basename
                success_image = self._process_livephoto_file(
                    image_file, shared_basename, creation_date, progress_ctx
                )

                # Process video file with shared basename
                success_video = self._process_livephoto_file(
                    video_file, shared_basename, creation_date, progress_ctx
                )

                if success_image and success_video:
                    self.stats['livephoto_pairs'] += 1
                    self.logger.debug(f"Successfully processed Live Photo pair: {image_file.name} + {video_file.name}")
                else:
                    self.logger.error(f"Failed to process Live Photo pair: {image_file.name} + {video_file.name}")

            except Exception as e:
                self.logger.error(f"Error processing Live Photo pair {pair_id}: {e}")
                self.stats['unsorted'] += 2
                self.file_ops.archive_file(pair_data['image_file'], self.unsorted_dir, preserve_structure=False)
                self.file_ops.archive_file(pair_data['video_file'], self.unsorted_dir, preserve_structure=False)
                progress_ctx.advance(2)

    def _process_livephoto_file(self, file_path: Path, shared_basename: str,
                               creation_date: datetime, progress_ctx) -> bool:
        """Process a single Live Photo file with predetermined basename."""
        try:
            # Get file size before operations
            file_size = file_path.stat().st_size

            # Handle video conversion if needed
            conversion = self.video_converter.handle_video_conversion(
                file_path, self.convert_videos, progress_ctx, "photosort_lp"
            )
            if not conversion.success:
                self.stats['unsorted'] += 1
                self.file_ops.cleanup_failed_move(
                    conversion.source_file, conversion.processing_file,
                    conversion.temp_file, self.unsorted_dir
                )
                progress_ctx.advance()
                return False

            # Update stats for successful conversion
            if conversion.was_converted:
                self.stats['converted_videos'] += 1

            # Generate destination path using shared basename
            year = f"{creation_date.year:04d}"
            month = f"{creation_date.month:02d}"
            dest_dir = self.dest / year / month
            ext = conversion.processing_file.suffix.lower()
            ext = self.file_ops.normalize_jpg_extension(ext)
            dest_path = dest_dir / f"{shared_basename}{ext}"

            # Check for duplicates if the destination file already exists
            if dest_path.exists() and self.file_ops.is_duplicate(conversion.processing_file, dest_path):
                self.stats['duplicates'] += 1
                progress_ctx.update(f"Skipping duplicate Live Photo: {conversion.processing_file.name}")
                self.file_ops.handle_duplicate_cleanup(conversion.source_file, conversion.temp_file)
                progress_ctx.advance()
                return True

            # Move processed file to destination
            if self.file_ops.move_file_safely(conversion.processing_file, dest_path):
                # If we converted a video, handle cleanup based on mode
                if conversion.was_converted:
                    conversion.handle_conversion_cleanup(
                        self.file_ops, self.source, self.legacy_videos_dir
                    )

                is_video = file_path.suffix.lower() in MOVIE_EXTENSIONS
                self.file_ops.update_file_stats(self.stats, is_video, file_size)
                progress_ctx.update(f"Processed Live Photo: {file_path.name}")
                progress_ctx.advance()
                return True
            else:
                self.stats['unsorted'] += 1
                self.file_ops.cleanup_failed_move(
                    conversion.source_file, conversion.processing_file,
                    conversion.temp_file, self.unsorted_dir
                )
                progress_ctx.advance()
                return False

        except Exception as e:
            self.logger.error(f"Error processing Live Photo file {file_path}: {e}")
            self.stats['unsorted'] += 1
            self.file_ops.archive_file(file_path, self.unsorted_dir, preserve_structure=False)
            conversion.cleanup_temp()
            progress_ctx.advance()
            return False

