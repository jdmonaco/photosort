"""
photosort - Organize photos and videos into year/month folder structure.

A modern Python tool for organizing unstructured photo and video collections
into a clean year/month directory structure based on file creation dates.

Created with the assistance of Claude Code. MIT License.
"""

__version__ = "2.1.2"
__copyright__ = "Copyright (c) 2025 Joe Monaco (joe@selfmotion.net)"


# Public API
from .cli import main
from .config import Config
from .conversion import VideoConverter, ConversionResult
from .core import PhotoSorter
from .file_operations import FileOperations
from .history import HistoryManager
from .livephoto import LivePhotoProcessor
from .progress import ProgressContext
from .stats import StatsManager

__all__ = [ "main", "Config", "VideoConverter", "ConversionResult", "PhotoSorter", "HistoryManager", "LivePhotoProcessor", "FileOperations", "ProgressContext", "StatsManager" ]

