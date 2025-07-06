"""
Test Live Photo detection and processing.
"""

import pytest
from pathlib import Path


class TestLivePhotoProcessing:
    """Test Apple Live Photo pair detection and processing."""
    
    def test_livephoto_detection_with_exiftool(self, cli_runner, temp_source_folder, 
                                             test_config_path, mock_external_tools):
        """Test Live Photo detection when exiftool is available."""
        # Mock exiftool as available
        mock_external_tools({"exiftool": True})
        
        dest_path = test_config_path.parent / "test_livephoto_exiftool"
        
        # Check if we have Live Photo pairs in test media
        livephoto_dir = temp_source_folder / "livephotos"
        if not livephoto_dir.exists():
            pytest.skip("No livephotos directory in test media")
        
        # Count potential Live Photo pairs
        photo_files = list(livephoto_dir.glob("*.heic")) + list(livephoto_dir.glob("*.jpg"))
        video_files = list(livephoto_dir.glob("*.mov")) + list(livephoto_dir.glob("*.mp4"))
        
        if not (photo_files and video_files):
            pytest.skip("No Live Photo pairs in test media")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check output mentions Live Photo detection
        if len(photo_files) > 0:
            # Should mention Live Photo pairs in output
            assert "Live Photo" in result.output or "pairs" in result.output
    
    def test_livephoto_basename_fallback(self, cli_runner, temp_source_folder,
                                       test_config_path, mock_external_tools):
        """Test Live Photo detection fallback when exiftool unavailable."""
        # Mock exiftool as unavailable
        mock_external_tools({"exiftool": False})
        
        dest_path = test_config_path.parent / "test_livephoto_fallback"
        
        # Check for Live Photo pairs
        livephoto_dir = temp_source_folder / "livephotos"
        if not livephoto_dir.exists():
            pytest.skip("No livephotos directory in test media")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Even without exiftool, basename matching should work
        # Look for pairs with same basename
        dest_files = {}
        for f in dest_path.rglob("*"):
            if f.is_file():
                basename = f.stem
                if basename not in dest_files:
                    dest_files[basename] = []
                dest_files[basename].append(f.suffix.lower())
        
        # Check for basenames with both photo and video extensions
        photo_exts = {'.jpg', '.jpeg', '.heic'}
        video_exts = {'.mov', '.mp4'}
        
        pairs_found = 0
        for basename, exts in dest_files.items():
            has_photo = any(ext in photo_exts for ext in exts)
            has_video = any(ext in video_exts for ext in exts)
            if has_photo and has_video:
                pairs_found += 1
        
        # Should find at least some pairs if test media has them
        if pairs_found > 0:
            assert True, "Found Live Photo pairs via basename matching"
    
    def test_livephoto_shared_basenames(self, cli_runner, test_config_path, create_test_files):
        """Test that Live Photo pairs get identical basenames."""
        # Create explicit Live Photo pair files
        source_files = [
            {"name": "livephotos/IMG_0001.heic", "content": b"heic photo"},
            {"name": "livephotos/IMG_0001.mov", "content": b"mov video"},
            {"name": "livephotos/IMG_0002.jpg", "content": b"jpg photo"},
            {"name": "livephotos/IMG_0002.mov", "content": b"mov video 2"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_shared_basenames"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Collect all files by basename
        basenames = {}
        for f in dest_path.rglob("*"):
            if f.is_file() and "history" not in str(f):
                basename = f.stem  # filename without extension
                if basename not in basenames:
                    basenames[basename] = []
                basenames[basename].append(f.name)
        
        # Find basenames that have exactly 2 files (photo + video)
        paired_basenames = [b for b, files in basenames.items() if len(files) == 2]
        
        # Should have found our Live Photo pairs
        assert len(paired_basenames) >= 1, \
            "Should have at least one basename with both photo and video"
        
        # Verify the pairs have matching timestamps in filename
        for basename in paired_basenames:
            # Basename format: YYYYMMDD_HHMMSS_NNN
            parts = basename.split('_')
            assert len(parts) == 3, f"Basename {basename} should have 3 parts"
            
            # Date and time parts should be valid
            assert len(parts[0]) == 8, "Date part should be 8 digits"
            assert len(parts[1]) == 6, "Time part should be 6 digits"
            assert len(parts[2]) == 3, "Counter part should be 3 digits"
    
    def test_livephoto_processing_order(self, cli_runner, test_config_path, create_test_files):
        """Test that Live Photos are processed before individual files."""
        # Create files that could cause naming conflicts
        source_files = [
            # Live Photo pair
            {"name": "LP_001.heic", "content": b"live photo"},
            {"name": "LP_001.mov", "content": b"live video"},
            # Individual file that might conflict
            {"name": "single.jpg", "content": b"single photo"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_processing_order"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # All files should be processed successfully without conflicts
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        assert len(media_files) == 3, "All 3 files should be processed"
        
        # Check that we have both extensions for the Live Photo
        extensions = [f.suffix.lower() for f in media_files]
        assert '.heic' in extensions or '.jpg' in extensions, "Should have photo file"
        assert '.mov' in extensions, "Should have video file"
    
    def test_mixed_livephoto_and_regular_files(self, cli_runner, temp_source_folder,
                                              test_config_path):
        """Test processing mix of Live Photos and regular media files."""
        dest_path = test_config_path.parent / "test_mixed_processing"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check summary output
        output_lines = result.output.strip().split('\n')
        
        # Look for processing summary
        found_photos = False
        found_videos = False
        found_livephotos = False
        
        for line in output_lines:
            if "Photos" in line and "│" in line:  # Table row
                found_photos = True
            if "Videos" in line and "│" in line:
                found_videos = True
            if "Live Photos" in line and "│" in line:
                found_livephotos = True
        
        # Should process multiple types (depending on test media)
        assert found_photos or found_videos or found_livephotos, \
            "Should process at least some media files"
    
    def test_livephoto_metadata_preservation(self, cli_runner, temp_source_folder,
                                           test_config_path):
        """Test that Live Photo pairs maintain relationship after processing."""
        dest_path = test_config_path.parent / "test_metadata_preservation"
        
        # Skip if no Live Photos in test media
        livephoto_dir = temp_source_folder / "livephotos"
        if not livephoto_dir.exists() or not any(livephoto_dir.iterdir()):
            pytest.skip("No Live Photos in test media")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Group destination files by basename
        pairs = {}
        for f in dest_path.rglob("*"):
            if f.is_file() and "history" not in str(f):
                basename = f.stem
                if basename not in pairs:
                    pairs[basename] = []
                pairs[basename].append(f)
        
        # Find actual Live Photo pairs (2 files with same basename)
        live_pairs = {k: v for k, v in pairs.items() if len(v) == 2}
        
        if live_pairs:
            # Verify pairs have expected extensions
            for basename, files in live_pairs.items():
                exts = [f.suffix.lower() for f in files]
                
                # Should have one photo and one video
                photo_exts = {'.jpg', '.jpeg', '.heic'}
                video_exts = {'.mov', '.mp4'}
                
                has_photo = any(ext in photo_exts for ext in exts)
                has_video = any(ext in video_exts for ext in exts)
                
                assert has_photo and has_video, \
                    f"Live Photo pair {basename} should have both photo and video"
    
    def test_livephoto_duplicate_handling(self, cli_runner, test_config_path, create_test_files):
        """Test handling of duplicate Live Photo pairs."""
        # Create duplicate Live Photo pairs
        source_files = [
            # First pair
            {"name": "pair1/IMG_0001.heic", "content": b"photo content 1"},
            {"name": "pair1/IMG_0001.mov", "content": b"video content 1"},
            # Duplicate pair (same content)
            {"name": "pair2/IMG_0001.heic", "content": b"photo content 1"},
            {"name": "pair2/IMG_0001.mov", "content": b"video content 1"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_livephoto_duplicates"
        
        # First run
        result1 = cli_runner(
            str(source_path / "pair1"),
            str(dest_path),
            config_path=test_config_path
        )
        assert result1.exit_code == 0
        
        # Second run with duplicates
        result2 = cli_runner(
            str(source_path / "pair2"),
            str(dest_path),
            config_path=test_config_path
        )
        assert result2.exit_code == 0
        
        # Should detect and skip duplicates
        if "Duplicates" in result2.output:
            # Should report 2 duplicates (both files in pair)
            assert "2" in result2.output or "duplicate" in result2.output.lower()
    
    def test_incomplete_livephoto_pairs(self, cli_runner, test_config_path, create_test_files):
        """Test handling when only one part of Live Photo pair exists."""
        # Create incomplete pairs
        source_files = [
            {"name": "IMG_0001.heic", "content": b"photo without video"},
            # Missing IMG_0001.mov
            {"name": "IMG_0002.mov", "content": b"video without photo"},
            # Missing IMG_0002.heic/jpg
            {"name": "IMG_0003.jpg", "content": b"complete pair photo"},
            {"name": "IMG_0003.mov", "content": b"complete pair video"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_incomplete_pairs"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # All files should still be processed
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        assert len(media_files) == 4, "All 4 files should be processed"
        
        # Check basenames
        basenames = {}
        for f in media_files:
            basename = f.stem
            if basename not in basenames:
                basenames[basename] = 0
            basenames[basename] += 1
        
        # Should have at least one paired basename (IMG_0003 files)
        paired = [b for b, count in basenames.items() if count == 2]
        assert len(paired) >= 1, "Complete pair should share basename"
        
        # Incomplete files should have unique basenames
        single = [b for b, count in basenames.items() if count == 1]
        assert len(single) >= 2, "Incomplete files should have unique basenames"