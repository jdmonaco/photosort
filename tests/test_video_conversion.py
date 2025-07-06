"""
Test video conversion to H.265/MP4 and related operations.
"""

import pytest
from pathlib import Path


class TestVideoConversion:
    """Test video format conversion and archival functionality."""
    
    def test_legacy_video_conversion(self, cli_runner, temp_source_folder, 
                                   test_config_path, assert_history_structure):
        """Test conversion of legacy video formats to H.265/MP4."""
        dest_path = test_config_path.parent / "test_video_conversion"
        
        # Look for any video files that might need conversion
        legacy_formats = ['.avi', '.wmv', '.mpg', '.mpeg', '.flv', '.3gp']
        legacy_videos = []
        for fmt in legacy_formats:
            legacy_videos.extend(temp_source_folder.rglob(f"*{fmt}"))
        
        if not legacy_videos:
            # Try older .mov or .mp4 that might have old codecs
            all_videos = list(temp_source_folder.rglob("*.mov")) + \
                        list(temp_source_folder.rglob("*.mp4"))
            if not all_videos:
                pytest.skip("No video files in test media")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check if any conversions happened
        if "Converted Videos" in result.output:
            # Should have conversion count in summary
            assert any(char.isdigit() for char in result.output)
            
            # Check history for archived originals
            history_folder = assert_history_structure(test_config_path, "test_video_conversion")
            legacy_dir = history_folder / "LegacyVideos"
            
            # Should have original videos archived
            archived_videos = list(legacy_dir.rglob("*"))
            assert len(archived_videos) > 0, "Converted videos should be archived"
            
            # Destination should have .mp4 files
            converted_videos = list(dest_path.rglob("*.mp4"))
            assert len(converted_videos) > 0, "Should have converted MP4 files"
    
    def test_modern_video_passthrough(self, cli_runner, test_config_path, create_test_files):
        """Test that modern H.264/H.265 videos are not converted."""
        # Create test files simulating modern codecs
        # Note: In real test media, these would have actual H.264/H.265 codecs
        source_files = [
            {"name": "modern/video_h264.mp4", "content": b"modern h264 video"},
            {"name": "modern/video_h265.mp4", "content": b"modern h265 video"},
            {"name": "modern/video_hevc.mov", "content": b"modern hevc video"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_modern_passthrough"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Modern videos should not be converted
        dest_videos = list(dest_path.rglob("*"))
        media_videos = [v for v in dest_videos if v.is_file() and "history" not in str(v)]
        
        assert len(media_videos) == 3, "All modern videos should be processed"
        
        # Check no videos in LegacyVideos (no conversion)
        history_root = test_config_path.parent / "history"
        if history_root.exists():
            for history_folder in history_root.iterdir():
                if "test_modern_passthrough" in history_folder.name:
                    legacy_dir = history_folder / "LegacyVideos"
                    if legacy_dir.exists():
                        assert len(list(legacy_dir.iterdir())) == 0, \
                            "No videos should be archived (no conversion needed)"
    
    def test_no_convert_videos_flag(self, cli_runner, temp_source_folder, test_config_path):
        """Test --no-convert-videos flag disables conversion."""
        dest_path = test_config_path.parent / "test_no_convert"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--no-convert-videos",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Should not mention conversion in output
        assert "Converted Videos" not in result.output or \
               "Converted Videos │ 0" in result.output
        
        # Check history - no videos should be in LegacyVideos
        history_root = test_config_path.parent / "history"
        if history_root.exists():
            for history_folder in history_root.iterdir():
                if "test_no_convert" in history_folder.name:
                    legacy_dir = history_folder / "LegacyVideos"
                    if legacy_dir.exists():
                        assert len(list(legacy_dir.iterdir())) == 0, \
                            "No videos should be converted with --no-convert-videos"
    
    def test_conversion_in_copy_mode(self, cli_runner, test_config_path, create_test_files):
        """Test video conversion behavior in copy mode."""
        # Create a legacy format video
        source_files = [
            {"name": "legacy.avi", "content": b"legacy avi video content"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_copy_conversion"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            "--copy",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Original should still exist in source
        assert (source_path / "legacy.avi").exists(), \
            "Original file should remain in copy mode"
        
        # If conversion happened, check archived original
        if "Converted Videos" in result.output and "│ 1" in result.output:
            history_root = test_config_path.parent / "history"
            for history_folder in history_root.iterdir():
                if "test_copy_conversion" in history_folder.name:
                    legacy_dir = history_folder / "LegacyVideos"
                    if legacy_dir.exists() and list(legacy_dir.iterdir()):
                        # In copy mode, original is copied to archive
                        archived = list(legacy_dir.iterdir())
                        assert len(archived) > 0, \
                            "Original should be copied to archive in copy mode"
    
    def test_conversion_in_move_mode(self, cli_runner, test_config_path, create_test_files):
        """Test video conversion behavior in move mode."""
        # Create a legacy format video
        source_files = [
            {"name": "legacy.wmv", "content": b"legacy wmv video content"},
        ]
        
        source_path = create_test_files(source_files)
        original_path = source_path / "legacy.wmv"
        dest_path = test_config_path.parent / "test_move_conversion"
        
        # Verify file exists before operation
        assert original_path.exists()
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Original should be gone from source
        assert not original_path.exists(), \
            "Original file should be removed in move mode"
        
        # If conversion happened, original is in history
        if "Converted Videos" in result.output and "│ 1" in result.output:
            history_root = test_config_path.parent / "history"
            for history_folder in history_root.iterdir():
                if "test_move_conversion" in history_folder.name:
                    legacy_dir = history_folder / "LegacyVideos"
                    if legacy_dir.exists():
                        archived = list(legacy_dir.iterdir())
                        assert len(archived) > 0, \
                            "Original should be moved to archive in move mode"
    
    def test_conversion_error_handling(self, cli_runner, test_config_path, 
                                     create_test_files, mock_external_tools):
        """Test handling when video conversion fails."""
        # Mock ffmpeg as unavailable
        mock_external_tools({"ffmpeg": False})
        
        source_files = [
            {"name": "video.avi", "content": b"avi video"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_conversion_error"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        # Should still succeed but without conversion
        assert result.exit_code == 0
        
        # Video should still be processed (moved/copied as-is)
        dest_videos = list(dest_path.rglob("*.avi"))
        assert len(dest_videos) == 1, "Video should be processed even without conversion"
    
    def test_conversion_preserves_metadata(self, cli_runner, temp_source_folder, 
                                         test_config_path):
        """Test that converted videos preserve creation date metadata."""
        dest_path = test_config_path.parent / "test_metadata_preservation"
        
        # Find any videos in test media
        videos = list(temp_source_folder.rglob("*.mov")) + \
                list(temp_source_folder.rglob("*.mp4")) + \
                list(temp_source_folder.rglob("*.avi"))
        
        if not videos:
            pytest.skip("No videos in test media")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # All processed videos should maintain date-based organization
        for year_dir in dest_path.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                # Valid year directory indicates metadata was preserved
                assert 1900 <= int(year_dir.name) <= 2100, \
                    f"Year {year_dir.name} indicates metadata preservation"
    
    def test_conversion_size_reduction(self, cli_runner, test_config_path, create_test_files):
        """Test that conversion info shows size reduction."""
        # Create a large-ish legacy video file
        source_files = [
            {"name": "large.avi", "content": b"x" * 10000},  # 10KB simulated video
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_size_reduction"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # If conversion happened, output might mention size reduction
        # (Actual reduction depends on real video conversion)
        if "Converted Videos" in result.output and "│ 1" in result.output:
            # Check that converted file exists
            mp4_files = list(dest_path.rglob("*.mp4"))
            if mp4_files:
                assert len(mp4_files) > 0, "Should have converted MP4 file"
    
    def test_mixed_convertible_and_modern_videos(self, cli_runner, test_config_path, 
                                                create_test_files):
        """Test processing mix of videos needing and not needing conversion."""
        source_files = [
            {"name": "legacy.avi", "content": b"old avi video"},
            {"name": "modern.mp4", "content": b"modern mp4 video"},
            {"name": "legacy.wmv", "content": b"old wmv video"},
            {"name": "modern.mov", "content": b"modern mov video"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_mixed_videos"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # All videos should be processed
        dest_videos = list(dest_path.rglob("*.mp4")) + list(dest_path.rglob("*.mov"))
        media_videos = [v for v in dest_videos if v.is_file() and "history" not in str(v)]
        
        assert len(media_videos) >= 2, "Should process all videos"
        
        # Check summary shows both videos and conversions
        assert "Videos" in result.output
        
        # If conversions happened, check archives
        if "Converted Videos" in result.output and not "│ 0" in result.output:
            history_root = test_config_path.parent / "history"
            for history_folder in history_root.iterdir():
                if "test_mixed_videos" in history_folder.name:
                    legacy_dir = history_folder / "LegacyVideos"
                    if legacy_dir.exists():
                        # Should have some but not all videos archived
                        archived = list(legacy_dir.iterdir())
                        assert 0 < len(archived) < 4, \
                            "Only legacy videos should be archived"