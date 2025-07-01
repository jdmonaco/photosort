"""
photosort - Organize photos and videos into year/month folder structure.

A modern Python tool for organizing unstructured photo and video collections
into a clean year/month directory structure based on file creation dates.

Created with the assistance of Claude Code on 2025-06-24.
"""

__version__ = "2.0.0"

# Public API
from .cli import main
from .config import Config
from .conversion import VideoConverter
from .core import PhotoSorter
from .history import HistoryManager
from .livephoto import LivePhotoProcessor

__all__ = ["main", "Config", "VideoConverter", "PhotoSorter", "HistoryManager", "LivePhotoProcessor"]