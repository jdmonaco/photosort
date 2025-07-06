"""
Statistics tracking and management for photo sorting operations.
"""

from typing import Dict
from pathlib import Path

from .constants import MOVIE_EXTENSIONS


class StatsManager:
    """Encapsulates statistics tracking for photo sorting operations."""
    
    def __init__(self):
        self._stats = {
            'photos': 0,
            'videos': 0,
            'metadata': 0,
            'duplicates': 0,
            'unsorted': 0,
            'total_size': 0,
            'converted_videos': 0,
            'livephoto_pairs': 0
        }
    
    def increment_photos(self) -> None:
        """Increment photo count when a photo file is successfully processed."""
        self._stats['photos'] += 1
    
    def increment_videos(self) -> None:
        """Increment video count when a video file is successfully processed."""
        self._stats['videos'] += 1
    
    def increment_metadata(self) -> None:
        """Increment metadata count when a metadata file is successfully processed."""
        self._stats['metadata'] += 1
    
    def increment_duplicates(self) -> None:
        """Increment duplicate count when a duplicate file is detected and handled."""
        self._stats['duplicates'] += 1
    
    def increment_unsorted(self, count: int = 1) -> None:
        """Increment unsorted count when file(s) fail processing and are archived."""
        self._stats['unsorted'] += count
    
    def increment_converted_videos(self) -> None:
        """Increment converted video count when a video conversion succeeds."""
        self._stats['converted_videos'] += 1
    
    def increment_livephoto_pairs(self) -> None:
        """Increment Live Photo pair count when a pair is successfully processed."""
        self._stats['livephoto_pairs'] += 1
    
    def add_file_size(self, size: int) -> None:
        """Add file size to total when a file is successfully processed."""
        self._stats['total_size'] += size
    
    def record_successful_file(self, file_path: Path, file_size: int) -> None:
        """Record a successfully processed file, updating both count and size.
        
        Replaces FileOperations.update_file_stats() method.
        """
        is_video = file_path.suffix.lower() in MOVIE_EXTENSIONS
        if is_video:
            self.increment_videos()
        else:
            self.increment_photos()
        self.add_file_size(file_size)
    
    def get_stats(self) -> Dict[str, int]:
        """Get a copy of current statistics."""
        return self._stats.copy()
    
    def get_total_files(self) -> int:
        """Get total count of successfully processed files."""
        return self._stats['photos'] + self._stats['videos'] + self._stats['metadata']
    
    def get_total_size_mb(self) -> float:
        """Get total size in megabytes."""
        return self._stats['total_size'] / (1024 * 1024)
    
    def has_errors(self) -> bool:
        """Check if any files were unsorted (had processing errors)."""
        return self._stats['unsorted'] > 0
    
    # Individual stat getters for reporting
    def get_photos(self) -> int:
        return self._stats['photos']
    
    def get_videos(self) -> int:
        return self._stats['videos']
    
    def get_metadata(self) -> int:
        return self._stats['metadata']
    
    def get_duplicates(self) -> int:
        return self._stats['duplicates']
    
    def get_unsorted(self) -> int:
        return self._stats['unsorted']
    
    def get_converted_videos(self) -> int:
        return self._stats['converted_videos']
    
    def get_livephoto_pairs(self) -> int:
        return self._stats['livephoto_pairs']
    
    def get_total_size(self) -> int:
        return self._stats['total_size']