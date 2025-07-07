"""
Test basic photosort operations: move, copy, dry-run, and validation.
"""

import pytest
from pathlib import Path


class TestBasicOperations:
    """Test fundamental photosort operations."""
    
    def test_move_mode(self, cli_runner, temp_source_folder, test_config_path, 
                       assert_file_structure, assert_history_structure):
        """Test default move mode operation."""
        dest_name = "test_move_mode_dest"
        dest_path = test_config_path.parent / dest_name
        
        # Count source files before operation
        source_media_files = list(temp_source_folder.rglob("*.jpg")) + \
                            list(temp_source_folder.rglob("*.mp4")) + \
                            list(temp_source_folder.rglob("*.mov"))
        initial_count = len(source_media_files)
        
        # Run photosort in move mode (default)
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        # Verify success
        assert result.exit_code == 0
        assert "Processing completed successfully" in result.output
        
        # Verify files were moved (source should be empty of media files)
        remaining_media = list(temp_source_folder.rglob("*.jpg")) + \
                         list(temp_source_folder.rglob("*.mp4")) + \
                         list(temp_source_folder.rglob("*.mov"))
        assert len(remaining_media) == 0, "Source should be empty after move"
        
        # Verify destination has files
        dest_media = list(dest_path.rglob("*.jpg")) + \
                    list(dest_path.rglob("*.mp4")) + \
                    list(dest_path.rglob("*.mov"))
        assert len(dest_media) > 0, "Destination should have files"
        
        # Verify history folder created
        assert_history_structure(test_config_path, dest_name)
    
    def test_copy_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test copy mode operation."""
        dest_name = "test_copy_mode_dest"
        dest_path = test_config_path.parent / dest_name
        
        # Count source files
        source_photos = list(temp_source_folder.rglob("*.jpg"))
        initial_count = len(source_photos)
        
        # Run photosort in copy mode
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--copy",
            config_path=test_config_path
        )
        
        # Verify success
        assert result.exit_code == 0
        assert "Processing completed successfully" in result.output
        
        # Verify files still exist in source
        remaining_photos = list(temp_source_folder.rglob("*.jpg"))
        assert len(remaining_photos) == initial_count, \
            "Source files should remain in copy mode"
        
        # Verify files copied to destination
        dest_photos = list(dest_path.rglob("*.jpg"))
        assert len(dest_photos) > 0, "Files should be copied to destination"
    
    def test_dry_run_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test dry-run mode doesn't modify files."""
        dest_name = "test_dry_run_dest"
        dest_path = test_config_path.parent / dest_name
        
        # Get initial file state
        source_files_before = set(f.relative_to(temp_source_folder) 
                                 for f in temp_source_folder.rglob("*") if f.is_file())
        
        # Run photosort in dry-run mode
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        # Verify output indicates dry run
        assert "Processing Mode: DRY RUN" in result.output
        assert result.exit_code == 0
        
        # Verify no files were moved
        source_files_after = set(f.relative_to(temp_source_folder) 
                                for f in temp_source_folder.rglob("*") if f.is_file())
        assert source_files_before == source_files_after, \
            "Source files should not change in dry-run mode"
        
        # Verify destination wasn't created
        assert not dest_path.exists(), "Destination should not be created in dry-run"
    
    def test_source_validation(self, cli_runner, test_config_path):
        """Test source directory validation."""
        # Test non-existent source
        result = cli_runner(
            "/path/that/does/not/exist",
            "/tmp/dest",
            config_path=test_config_path
        )
        
        assert result.exit_code == 1
        assert "Source directory does not exist" in result.output
        
        # Test file as source (not directory)
        temp_file = test_config_path.parent / "not_a_directory.txt"
        temp_file.write_text("test")
        
        result = cli_runner(
            str(temp_file),
            "/tmp/dest",
            config_path=test_config_path
        )
        
        assert result.exit_code == 1
        assert "Source is not a directory" in result.output
    
    def test_source_dest_validation(self, cli_runner, temp_source_folder, test_config_path):
        """Test source/destination path validation."""
        # Test same source and destination
        result = cli_runner(
            str(temp_source_folder),
            str(temp_source_folder),
            config_path=test_config_path
        )
        
        assert result.exit_code == 1
        assert "Identical or overlapping source/dest folders" in result.output
        
        # Test destination inside source
        nested_dest = temp_source_folder / "organized"
        result = cli_runner(
            str(temp_source_folder),
            str(nested_dest),
            config_path=test_config_path
        )
        
        assert result.exit_code == 1
        assert "Identical or overlapping source/dest folders" in result.output
        
        # Test source inside destination
        parent_dest = temp_source_folder.parent
        result = cli_runner(
            str(temp_source_folder),
            str(parent_dest),
            config_path=test_config_path
        )
        
        assert result.exit_code == 1
        assert "Identical or overlapping source/dest folders" in result.output
    
    def test_empty_source_directory(self, cli_runner, tmp_path, test_config_path):
        """Test handling of empty source directory."""
        empty_source = tmp_path / "empty_source"
        empty_source.mkdir()
        dest_path = tmp_path / "dest"
        
        result = cli_runner(
            str(empty_source),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        assert "No media files found in source directory" in result.output
    
    def test_verbose_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test verbose logging mode."""
        dest_path = test_config_path.parent / "test_verbose_dest"
        
        # Run with verbose flag
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--verbose",
            "--dry-run",  # Use dry-run to avoid file operations
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        # Verbose mode should show more detailed output
        # (specific assertions depend on what verbose logging includes)
    
    def test_mixed_flags(self, cli_runner, temp_source_folder, test_config_path):
        """Test combination of flags."""
        dest_path = test_config_path.parent / "test_mixed_dest"
        
        # Test copy + dry-run
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--copy",
            "--dry-run",
            "--verbose",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        
        # Verify no actual operations occurred
        assert not dest_path.exists()
    
    def test_source_dest_args_vs_flags(self, cli_runner, temp_source_folder, test_config_path):
        """Test positional args vs --source/--dest flags."""
        dest1 = test_config_path.parent / "dest1"
        dest2 = test_config_path.parent / "dest2"
        
        # Test with positional arguments
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest1),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        assert "dest1" in result1.output
        
        # Test with flags
        result2 = cli_runner(
            "--source", str(temp_source_folder),
            "--dest", str(dest2),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result2.exit_code == 0
        assert "dest2" in result2.output
        
        # Test flags override positional
        result3 = cli_runner(
            str(temp_source_folder),
            str(dest1),
            "--dest", str(dest2),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result3.exit_code == 0
        assert "dest2" in result3.output  # Flag should override positional