"""
Test file organization: date-based structure, naming, duplicates, and bursts.
"""

import pytest
from datetime import datetime
from pathlib import Path


class TestFileOrganization:
    """Test file organization and naming conventions."""
    
    def test_date_based_organization(self, cli_runner, temp_source_folder, 
                                   test_config_path, assert_file_structure):
        """Test files are organized into YYYY/MM structure."""
        dest_path = test_config_path.parent / "test_date_organization"
        
        # Run photosort
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check that year/month directories were created
        # We expect at least one year directory
        year_dirs = [d for d in dest_path.iterdir() if d.is_dir() and d.name.isdigit()]
        assert len(year_dirs) > 0, "Should have at least one year directory"
        
        # Check month directories within year
        for year_dir in year_dirs:
            month_dirs = [d for d in year_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            assert len(month_dirs) > 0, f"Year {year_dir.name} should have month directories"
            
            # Verify month names are valid (01-12)
            for month_dir in month_dirs:
                month_num = int(month_dir.name)
                assert 1 <= month_num <= 12, f"Invalid month number: {month_num}"
    
    def test_filename_format(self, cli_runner, temp_source_folder, test_config_path):
        """Test output filename format: YYYYMMDD_HHMMSS_NNN.ext"""
        dest_path = test_config_path.parent / "test_filename_format"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check all output files match expected format
        # Allows optional _NN collision suffix for Live Photo pairs
        pattern = r'^\d{8}_\d{6}_\d{3}(_\d{2})?\.\w+$'
        import re
        
        for file_path in dest_path.rglob("*"):
            if file_path.is_file():
                filename = file_path.name
                # Skip if it's in history subdirectory
                if "history" in str(file_path):
                    continue
                    
                assert re.match(pattern, filename), \
                    f"Filename '{filename}' doesn't match expected format"
                
                # Verify date components are valid
                date_part = filename[:8]
                time_part = filename[9:15]
                
                # Parse and validate date
                year = int(date_part[:4])
                month = int(date_part[4:6])
                day = int(date_part[6:8])
                
                assert 1900 <= year <= 2100, f"Invalid year: {year}"
                assert 1 <= month <= 12, f"Invalid month: {month}"
                assert 1 <= day <= 31, f"Invalid day: {day}"
                
                # Parse and validate time
                hour = int(time_part[:2])
                minute = int(time_part[2:4])
                second = int(time_part[4:6])
                
                assert 0 <= hour <= 23, f"Invalid hour: {hour}"
                assert 0 <= minute <= 59, f"Invalid minute: {minute}"
                assert 0 <= second <= 59, f"Invalid second: {second}"
    
    def test_duplicate_detection(self, cli_runner, test_config_path, create_test_files):
        """Test that duplicate files are detected and skipped."""
        # Create source with duplicate files
        source_files = [
            {"name": "photos/image1.jpg", "content": b"unique photo content 1"},
            {"name": "photos/image2.jpg", "content": b"unique photo content 2"},
            {"name": "photos/duplicate1.jpg", "content": b"duplicate content"},
            {"name": "photos/duplicate2.jpg", "content": b"duplicate content"},  # Same content
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_duplicates"
        
        # First run - process all files
        result1 = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check summary for duplicates
        if "Duplicates Skipped" in result1.output:
            # One of the duplicates should have been skipped
            assert "1" in result1.output or "duplicate" in result1.output.lower()
        
        # Count files in destination
        dest_files = list(dest_path.rglob("*.jpg"))
        # Should have 3 files (2 unique + 1 of the duplicates)
        assert len(dest_files) == 3, "Should have 3 files after skipping duplicate"
    
    def test_burst_sequence_counter(self, cli_runner, test_config_path, create_test_files):
        """Test sequential counter for same-timestamp files (bursts)."""
        # Create files with same timestamp
        same_time = datetime(2024, 1, 15, 10, 30, 45)
        
        source_files = [
            {"name": "burst/photo1.jpg", "content": b"burst photo 1", "mtime": same_time},
            {"name": "burst/photo2.jpg", "content": b"burst photo 2", "mtime": same_time},
            {"name": "burst/photo3.jpg", "content": b"burst photo 3", "mtime": same_time},
            {"name": "other/photo4.jpg", "content": b"different time"},  # Different time
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_burst"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check burst photos have sequential counters
        burst_files = []
        expected_base = "20240115_103045"
        
        for file_path in dest_path.rglob("*.jpg"):
            if expected_base in file_path.name:
                burst_files.append(file_path.name)
        
        # Should have 3 burst files with counters 000, 001, 002
        assert len(burst_files) == 3, f"Expected 3 burst files, found {len(burst_files)}"
        
        burst_files.sort()
        expected_names = [
            f"{expected_base}_000.jpg",
            f"{expected_base}_001.jpg",
            f"{expected_base}_002.jpg"
        ]
        
        for expected, actual in zip(expected_names, burst_files):
            assert expected in actual, f"Expected {expected} in burst sequence"
    
    def test_metadata_file_handling(self, cli_runner, temp_source_folder, 
                                  test_config_path, assert_history_structure):
        """Test that metadata files are moved to history."""
        dest_path = test_config_path.parent / "test_metadata"
        
        # Count metadata files in source
        metadata_extensions = ['.aae', '.xml', '.json', '.ini']
        metadata_files = []
        for ext in metadata_extensions:
            metadata_files.extend(temp_source_folder.rglob(f"*{ext}"))
        
        initial_metadata_count = len(metadata_files)
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        if initial_metadata_count > 0:
            # Check history structure
            history_folder = assert_history_structure(test_config_path, "test_metadata")
            
            # Verify metadata files are in history
            metadata_dir = history_folder / "Metadata"
            history_metadata = list(metadata_dir.rglob("*"))
            assert len(history_metadata) > 0, "Metadata files should be in history"
            
            # Verify no metadata files in destination
            for ext in metadata_extensions:
                dest_metadata = list(dest_path.rglob(f"*{ext}"))
                assert len(dest_metadata) == 0, \
                    f"No {ext} files should be in destination"
    
    def test_extension_normalization(self, cli_runner, test_config_path, create_test_files):
        """Test that file extensions are normalized (e.g., .JPEG -> .jpg)."""
        source_files = [
            {"name": "photos/image1.JPEG", "content": b"jpeg photo"},
            {"name": "photos/image2.JPG", "content": b"jpg photo"},
            {"name": "photos/image3.jpeg", "content": b"jpeg lowercase"},
            {"name": "photos/image4.JPE", "content": b"jpe photo"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_extensions"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # All JPEG variants should be normalized to .jpg
        jpg_files = list(dest_path.rglob("*.jpg"))
        assert len(jpg_files) == 4, "All JPEG variants should be normalized to .jpg"
        
        # Should be no files with original extensions
        for ext in [".JPEG", ".JPG", ".jpeg", ".JPE"]:
            assert len(list(dest_path.rglob(f"*{ext}"))) == 0, \
                f"No files with {ext} extension should exist"
    
    def test_source_cleanup(self, cli_runner, test_config_path, create_test_files):
        """Test source directory cleanup after move operation."""
        # Create source with nested directories and misc files
        source_files = [
            {"name": "photos/subfolder/image1.jpg", "content": b"photo 1"},
            {"name": "photos/subfolder/image2.jpg", "content": b"photo 2"},
            {"name": "videos/video1.mp4", "content": b"video 1"},
            {"name": ".DS_Store", "content": b"nuisance file"},
            {"name": "photos/.DS_Store", "content": b"nuisance file 2"},
            {"name": "readme.txt", "content": "Unknown file type"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_cleanup"
        
        # Add empty directory
        empty_dir = source_path / "empty_folder"
        empty_dir.mkdir()
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check source directory state after move
        # - Media files should be gone
        assert len(list(source_path.rglob("*.jpg"))) == 0, "JPG files should be moved"
        assert len(list(source_path.rglob("*.mp4"))) == 0, "MP4 files should be moved"
        
        # - .DS_Store files should be removed
        assert len(list(source_path.rglob(".DS_Store"))) == 0, ".DS_Store should be removed"
        
        # - Empty directories should be removed
        assert not empty_dir.exists(), "Empty directories should be removed"
        assert not (source_path / "photos" / "subfolder").exists(), \
            "Empty subdirectories should be removed"
        
        # - Unknown files should be moved to history
        assert not (source_path / "readme.txt").exists(), \
            "Unknown files should be moved to history"
    
    def test_mixed_media_organization(self, cli_runner, temp_source_folder, test_config_path):
        """Test that photos and videos are organized together by date."""
        dest_path = test_config_path.parent / "test_mixed_media"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check that photos and videos can coexist in same date folders
        for year_dir in dest_path.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                for month_dir in year_dir.iterdir():
                    if month_dir.is_dir():
                        files = list(month_dir.iterdir())
                        extensions = [f.suffix.lower() for f in files if f.is_file()]
                        
                        # Check for mixed media types
                        has_photos = any(ext in ['.jpg', '.heic', '.png'] for ext in extensions)
                        has_videos = any(ext in ['.mp4', '.mov', '.avi'] for ext in extensions)
                        
                        # It's valid to have both or either
                        assert has_photos or has_videos, \
                            f"Directory {month_dir} should contain media files"