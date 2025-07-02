"""
photosort - Organize photos and videos into year/month folder structure.

A modern Python tool for organizing unstructured photo and video collections
into a clean year/month directory structure based on file creation dates.

Created with the assistance of Claude Code. MIT License.
"""

__version__ = "2.0.0"
__copyright__ = "Copyright (c) 2025 Joe Monaco (joe@selfmotion.net)"


# Public API
from .cli import main
from .config import Config
from .conversion import VideoConverter
from .core import PhotoSorter
from .file_operations import FileOperations
from .history import HistoryManager
from .livephoto import LivePhotoProcessor

__all__ = [ "main", "Config", "VideoConverter", "PhotoSorter", "HistoryManager", "LivePhotoProcessor", "FileOperations" ]

