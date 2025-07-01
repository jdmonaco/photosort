"""
Live Photo processing functionality.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.progress import Progress, TaskID
from rich.console import Console

from .constants import JPG_EXTENSIONS, MOVIE_EXTENSIONS


class LivePhotoProcessor:
    """Handles Apple Live Photo detection and processing."""

    def __init__(self, source: Path, dest: Path, dry_run: bool = False,
                 move_files: bool = True, file_mode: Optional[int] = None,
                 group_gid: Optional[int] = None, timezone: str = "America/New_York",
                 convert_videos: bool = True, video_converter=None,
                 history_manager=None, get_creation_date_func=None,
                 move_file_safely_func=None, is_duplicate_func=None,
                 logger: Optional[logging.Logger] = None, stats: Optional[Dict] = None):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run
        self.move_files = move_files
        self.file_mode = file_mode
        self.group_gid = group_gid
        self.timezone = timezone
        self.convert_videos = convert_videos
        self.video_converter = video_converter
        self.history_manager = history_manager
        self.get_creation_date = get_creation_date_func
        self.move_file_safely = move_file_safely_func
        self.is_duplicate = is_duplicate_func
        self.logger = logger or logging.getLogger("photosort.livephoto")
        self.stats = stats or {}

        # Check for exiftool availability
        self._exiftool_available = self._is_tool_available("exiftool", "-ver")

    def _is_tool_available(self, cmd: str, vers: str = "-h") -> bool:
        """Check availability of a command-line tool on this system."""
        try:
            subprocess.run([cmd, vers], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def detect_livephoto_pairs(self, media_files: List[Path]) -> Tuple[List[Path], Dict[str, Dict]]:
        """Detect LivePhoto pairs by matching Apple ContentIdentifier keys."""
        if self._exiftool_available:
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
                    creation_date = self.get_creation_date(data['image'])
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
                    # Add as individual files
                    non_livephoto_files.extend([data['image'], data['video']])
            else:
                # Add incomplete pairs as individual files
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
                            # Extract milliseconds (first 3 digits of subseconds)
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
        # Use milliseconds as 3-digit counter (or 0 if no milliseconds)
        counter = milliseconds if milliseconds > 0 else 0
        return f"{timestamp}_{counter:03d}"

    def process_livephoto_pairs(self, livephoto_pairs: Dict[str, Dict]) -> None:
        """Process Live Photo pairs with shared basenames."""
        if not livephoto_pairs:
            return

        self.logger.info(f"Processing {len(livephoto_pairs)} Live Photo pairs")

        console = Console()
        with Progress(console=console) as progress:
            task = progress.add_task("Processing Live Photos...", total=len(livephoto_pairs) * 2)

            for pair_id, pair_data in livephoto_pairs.items():
                try:
                    image_file = pair_data['image_file']
                    video_file = pair_data['video_file']
                    shared_basename = pair_data['shared_basename']
                    creation_date = pair_data['creation_date']

                    # Process image file with shared basename
                    success_image = self._process_livephoto_file(
                        image_file, shared_basename, creation_date, progress, task
                    )

                    # Process video file with shared basename
                    success_video = self._process_livephoto_file(
                        video_file, shared_basename, creation_date, progress, task
                    )

                    if success_image and success_video:
                        self.stats['livephoto_pairs'] += 1
                        self.logger.debug(f"Successfully processed Live Photo pair: {image_file.name} + {video_file.name}")
                    else:
                        self.logger.error(f"Failed to process Live Photo pair: {image_file.name} + {video_file.name}")

                except Exception as e:
                    self.logger.error(f"Error processing Live Photo pair {pair_id}: {e}")
                    self.stats['errors'] += 2
                    if not self.dry_run:
                        self._move_to_error_dir(pair_data['image_file'])
                        self._move_to_error_dir(pair_data['video_file'])
                    progress.advance(task, 2)

    def _process_livephoto_file(self, file_path: Path, shared_basename: str,
                               creation_date: datetime, progress: Progress, task: TaskID) -> bool:
        """Process a single Live Photo file with predetermined basename."""
        try:
            # Get file size before operations
            file_size = file_path.stat().st_size

            # Check if this is a video that needs conversion
            is_video = file_path.suffix.lower() in MOVIE_EXTENSIONS
            needs_conversion = (
                is_video and
                self.convert_videos and
                self.video_converter.needs_conversion(file_path)
            )

            # Determine processing file (original or converted)
            processing_file = file_path
            temp_converted_file = None
            if needs_conversion:
                # In COPY mode, use temp directory to avoid polluting source
                if not self.move_files:
                    # Create temp file for conversion
                    temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4", prefix="photosort_lp_")
                    os.close(temp_fd)  # Close file descriptor, keep path
                    converted_path = Path(temp_path)
                    temp_converted_file = converted_path
                else:
                    # In MOVE mode, convert in source directory as before
                    converted_name = file_path.stem + ".mp4"
                    converted_path = file_path.parent / converted_name

                progress.update(task, description=f"Converting Live Photo: {file_path.name}")
                if self.video_converter.convert_video(file_path, converted_path, progress, task):
                    processing_file = converted_path
                    self.stats['converted_videos'] += 1
                    self.logger.info(f"Successfully converted Live Photo video {file_path} -> {converted_path}")
                else:
                    self.logger.error(f"Failed to convert Live Photo video: {file_path}")
                    self.stats['errors'] += 1
                    # Clean up temp file if conversion failed
                    if temp_converted_file and temp_converted_file.exists():
                        try:
                            temp_converted_file.unlink()
                        except Exception:
                            pass
                    if not self.dry_run:
                        self._move_to_error_dir(file_path)
                    progress.advance(task)
                    return False

            # Generate destination path using shared basename
            year = f"{creation_date.year:04d}"
            month = f"{creation_date.month:02d}"
            dest_dir = self.dest / year / month
            ext = processing_file.suffix.lower()

            # Normalize JPG extensions
            if ext in JPG_EXTENSIONS:
                ext = ".jpg"

            dest_path = dest_dir / f"{shared_basename}{ext}"

            # Check for duplicates using the external function
            if dest_path.exists() and self.is_duplicate(processing_file, dest_path):
                self.stats['duplicates'] += 1
                progress.update(task, description=f"Skipping duplicate Live Photo: {processing_file.name}")

                # Clean up files based on mode
                if not self.dry_run:
                    if self.move_files:
                        # MOVE mode: delete source files
                        try:
                            processing_file.unlink()
                            if needs_conversion and file_path != processing_file and file_path.exists():
                                file_path.unlink()
                            self.logger.debug(f"Deleted duplicate Live Photo file: {processing_file}")
                        except Exception as e:
                            self.logger.warning(f"Could not delete duplicate Live Photo file {processing_file}: {e}")
                    else:
                        # COPY mode: clean up temp converted file only
                        if temp_converted_file and temp_converted_file.exists():
                            try:
                                temp_converted_file.unlink()
                                self.logger.debug(f"Cleaned up temp Live Photo converted file: {temp_converted_file}")
                            except Exception as e:
                                self.logger.warning(f"Could not clean up temp Live Photo file {temp_converted_file}: {e}")

                progress.advance(task)
                return True

            # Move processed file to destination
            if self.move_file_safely(processing_file, dest_path):
                self.stats['total_size'] += file_size

                # Archive original video if converted and clean up based on mode
                if needs_conversion and not self.dry_run:
                    self._ensure_legacy_videos_dir()
                    try:
                        relative_path = file_path.relative_to(self.source)
                        legacy_dest = self.history_manager.get_legacy_videos_dir() / relative_path
                        legacy_dest.parent.mkdir(parents=True, exist_ok=True)

                        if self.move_files:
                            # MOVE mode: move original to legacy directory
                            file_path.rename(legacy_dest)
                        else:
                            # COPY mode: copy original to legacy directory
                            shutil.copy2(str(file_path), str(legacy_dest))

                        self.logger.info(f"Archived original Live Photo video: {file_path} -> {legacy_dest}")
                    except Exception as e:
                        self.logger.warning(f"Could not archive original Live Photo video {file_path}: {e}")

                    # Clean up temp converted file in COPY mode
                    if not self.move_files and temp_converted_file and temp_converted_file.exists():
                        try:
                            temp_converted_file.unlink()
                            self.logger.debug(f"Cleaned up temp Live Photo converted file: {temp_converted_file}")
                        except Exception as e:
                            self.logger.warning(f"Could not clean up temp Live Photo file {temp_converted_file}: {e}")

                # Update stats
                if is_video:
                    self.stats['videos'] += 1
                else:
                    self.stats['photos'] += 1

                progress.update(task, description=f"Processed Live Photo: {file_path.name}")
                progress.advance(task)
                return True
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
                    # Also clean up temp file in COPY mode
                    if temp_converted_file and temp_converted_file.exists():
                        try:
                            temp_converted_file.unlink()
                        except Exception:
                            pass
                progress.advance(task)
                return False

        except Exception as e:
            self.logger.error(f"Error processing Live Photo file {file_path}: {e}")
            self.stats['errors'] += 1
            if not self.dry_run:
                self._move_to_error_dir(file_path)
            # Clean up temp file if it exists
            if temp_converted_file and temp_converted_file.exists():
                try:
                    temp_converted_file.unlink()
                except Exception:
                    pass
            progress.advance(task)
            return False

    def _ensure_legacy_videos_dir(self) -> None:
        """Create legacy videos directory if needed and not in dry-run mode."""
        if not self.dry_run:
            legacy_dir = self.history_manager.get_legacy_videos_dir()
            if not legacy_dir.exists():
                legacy_dir.mkdir(exist_ok=True)

    def _move_to_error_dir(self, file_path: Path) -> None:
        """Move problematic file to error directory."""
        error_dir = self.history_manager.get_unsorted_dir()
        if not self.dry_run and not error_dir.exists():
            error_dir.mkdir(exist_ok=True)

        try:
            error_dest = error_dir / file_path.name
            counter = 1
            while error_dest.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                error_dest = error_dir / f"{stem}_{counter:03d}{suffix}"
                counter += 1

            shutil.copy2(str(file_path), str(error_dest))
        except Exception as e:
            self.logger.error(f"Could not move error file: {e}")
