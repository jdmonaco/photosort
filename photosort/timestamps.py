"""Shared functions for parsing date-time strings."""

import json
import logging
import re
import subprocess
import zoneinfo
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from rich.logging import RichHandler

from .config import Config
from .constants import (exiftool_available, ffprobe_available, get_console, get_logger,
                        sips_available)


logger = get_logger()
config_tz = Config().get_timezone() or 'America/New_York'


def get_image_creation_date(image_path: Path) -> datetime:
    """Get creation date for any image using exiftool, sips, or file stat."""
    if exiftool_available:
        try:
            # Call exiftool to retrieve creation timestamps
            result = subprocess.run([
                "exiftool",
                "-q",
                "-json",
                "-d", "%Y-%m-%dT%H:%M:%S%3f%z",  # ISO 8601 compliant date-string
                "-CreateDate",
                "-CreationDate",
                "-CreationTime",
                "-SubSecCreateDate",
                "-ProfileDateTime",
                "-DateTimeOriginal",
                str(image_path)],
                capture_output=True, text=True, check=True
            )

            # Parse JSON output and process creation date tags in order
            try:
                exif_data = json.loads(result.stdout)[0]
                creation_date = canonical_EXIF_date(exif_data)
                if creation_date:
                    return creation_date
            except IndexError:
                pass

        except subprocess.CalledProcessError:
            pass

    if sips_available:
        try:
            # Call sips tool to retrieve creation timestamps
            result = subprocess.run(
                ["sips", "-g", "creation", str(image_path)],
                capture_output=True, text=True, check=True
            )

            # Parse sips output
            for line in result.stdout.split('\n'):
                if 'creation:' in line:
                    try:
                        date_str = line.split('creation: ')[1].strip()
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        break

        except subprocess.CalledProcessError:
            pass

    # Fallback to file modification time for photos
    return datetime.fromtimestamp(image_path.stat().st_mtime)


def canonical_EXIF_date(dates: Dict[str, str]) -> Optional[datetime]:
    """Parse EXIF image creation date with millisecond precision, if available."""
    # Parse original/creation date-time tags in priority order
    for date_field in ['SubSecCreateDate',
                       'CreationDate',
                       'CreateDate',
                       'CreationTime',
                       'CreateTime',
                       'ProfileDateTime',
                       'DateTimeOriginal']:
        if date_field not in dates:
            continue

        try:
            return parse_iso8601_datetime(dates[date_field])
        except ValueError:
            continue

    return None


def parse_iso8601_datetime(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO 8601 or EXIF date-time string with timezone awareness.

    Handles both ISO 8601 (2025-05-06T19:41:34-0400) and raw EXIF
    (2025:05:06 19:41:34.745-04:00) date formats.
    """
    # Pattern handles ISO 8601 (dash dates, T separator) and
    # raw EXIF format (colon dates, space separator)
    pattern = r'(\d{4}[-:]\d{2}[-:]\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?'
    match = re.match(pattern, timestamp_str)

    if not match:
        return None

    # Normalize colon-separated dates (EXIF format) to dash-separated
    date_part = match.group(1).replace(':', '-')
    time_part = match.group(2)
    fractional_part = match.group(3)
    timezone_part = match.group(4)

    # Create base datetime string
    datetime_str = f"{date_part} {time_part}"
    if fractional_part:
        milliseconds = fractional_part.ljust(3, '0')[:3]
        datetime_str += f".{milliseconds}"
        base_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")
    else:
        base_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

    # Handle timezone
    if timezone_part:
        if timezone_part == 'Z':
            # UTC timezone
            aware_dt = base_dt.replace(tzinfo=timezone.utc)
        else:
            # Parse offset like "-0400" or "+05:00"
            tz_str = timezone_part
            if ':' not in tz_str:
                # Convert "-0400" to "-04:00"
                tz_str = f"{tz_str[:-2]}:{tz_str[-2:]}"

            # Parse the offset
            sign = 1 if tz_str[0] == '+' else -1
            hours = int(tz_str[1:3])
            minutes = int(tz_str[4:6])
            offset_minutes = sign * (hours * 60 + minutes)

            tz_offset = timezone(timedelta(minutes=offset_minutes))
            aware_dt = base_dt.replace(tzinfo=tz_offset)
    else:
        # No timezone info, assume UTC
        aware_dt = base_dt.replace(tzinfo=timezone.utc)

    # Convert to configured default timezone
    dflt_tz = zoneinfo.ZoneInfo(config_tz)
    tz_dt = aware_dt.astimezone(dflt_tz)

    # Return as naive datetime in default timezone for consistency
    return tz_dt.replace(tzinfo=None)


def get_video_creation_date(file_path: Path) -> Optional[datetime]:
    """Extract creation date from video metadata with Apple QuickTime priority."""
    if not ffprobe_available:
        return None

    try:
        # Use ffprobe to get format metadata as JSON
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(file_path)
        ], capture_output=True, text=True, check=True)

        # Parse JSON output
        data = json.loads(result.stdout)
        tags = data.get("format", {}).get("tags", {})

        if not tags:
            logger.debug(f"No format metadata tags found for {file_path}")
            return None

        # Parse creation date timestamps, in priority order
        for date_key in ["com.apple.quicktime.creationdate", "creation_time"]:
            date_str = tags.get(date_key)
            if date_str:
                creation_date = parse_iso8601_datetime(date_str)
                if creation_date:
                    logger.debug(f"Video creation date: {file_path}[{date_key}] = {creation_date}")
                    return creation_date

        logger.debug(f"No creation date tag found for {file_path}")
        return None

    except subprocess.CalledProcessError as e:
        logger.debug(f"ffprobe failed for {file_path}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse ffprobe JSON output for {file_path}: {e}")
        return None
    except Exception as e:
        logger.debug(f"Error parsing video creation date for {file_path}: {e}")
        return None

