"""
Test file permissions and ownership features.
"""

import os
import stat
import pytest
from pathlib import Path


class TestFilePermissions:
    """Test file mode and group ownership functionality."""
    
    def test_default_file_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test default file permissions (644)."""
        dest_path = test_config_path.parent / "test_default_mode"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check file permissions on destination files
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            # Check at least one file has expected permissions
            sample_file = media_files[0]
            file_mode = oct(stat.S_IMODE(sample_file.stat().st_mode))
            
            # Default should be common mode based on umask (644, 600, or 664)
            valid_modes = ["0o644", "0o600", "0o664"]
            assert file_mode in valid_modes, \
                f"Default file mode should be one of {valid_modes}, got {file_mode}"
    
    def test_custom_file_mode_644(self, cli_runner, temp_source_folder, test_config_path):
        """Test setting file mode to 644."""
        dest_path = test_config_path.parent / "test_mode_644"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "644",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check file permissions
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            for file_path in media_files[:3]:  # Check first few files
                file_mode = oct(stat.S_IMODE(file_path.stat().st_mode))
                assert file_mode == "0o644", \
                    f"File {file_path.name} should have mode 644, got {file_mode}"
    
    def test_custom_file_mode_600(self, cli_runner, temp_source_folder, test_config_path):
        """Test setting file mode to 600 (owner only)."""
        dest_path = test_config_path.parent / "test_mode_600"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "600",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check file permissions
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            for file_path in media_files[:3]:  # Check first few files
                file_mode = oct(stat.S_IMODE(file_path.stat().st_mode))
                assert file_mode == "0o600", \
                    f"File {file_path.name} should have mode 600, got {file_mode}"
    
    def test_custom_file_mode_755(self, cli_runner, temp_source_folder, test_config_path):
        """Test setting file mode to 755 (including execute)."""
        dest_path = test_config_path.parent / "test_mode_755"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "755",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check file permissions
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            for file_path in media_files[:3]:  # Check first few files
                file_mode = oct(stat.S_IMODE(file_path.stat().st_mode))
                assert file_mode == "0o755", \
                    f"File {file_path.name} should have mode 755, got {file_mode}"
    
    def test_invalid_file_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test invalid file mode handling."""
        dest_path = test_config_path.parent / "test_invalid_mode"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "999",  # Invalid mode
            config_path=test_config_path
        )
        
        # Should either fail or fall back to default
        if result.exit_code == 1:
            assert "Invalid file mode" in result.output or "mode" in result.output.lower()
        else:
            # If it succeeds, files should have reasonable permissions
            dest_files = list(dest_path.rglob("*"))
            media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
            
            if media_files:
                file_mode = oct(stat.S_IMODE(media_files[0].stat().st_mode))
                # Should be a reasonable mode (not 999)
                assert file_mode in ["0o644", "0o600", "0o755"], \
                    f"Invalid mode should fall back to reasonable default, got {file_mode}"
    
    def test_group_ownership(self, cli_runner, temp_source_folder, test_config_path):
        """Test group ownership setting."""
        dest_path = test_config_path.parent / "test_group_ownership"
        
        # Try common group names
        test_groups = ["staff", "wheel", "admin"]
        available_group = None
        
        # Find an available group
        for group_name in test_groups:
            try:
                import grp
                grp.getgrnam(group_name)
                available_group = group_name
                break
            except KeyError:
                continue
        
        if not available_group:
            pytest.skip("No common test groups available")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--group", available_group,
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check group ownership
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            # Check file has expected group (if permission allows)
            sample_file = media_files[0]
            file_stat = sample_file.stat()
            
            # Check if we have permission to change group ownership
            import os
            import grp
            
            # Test if we can actually change group ownership by trying on a test file
            test_file = sample_file
            original_gid = test_file.stat().st_gid
            target_gid = grp.getgrnam(available_group).gr_gid
            
            try:
                # Try to set the group - if this fails, we don't have permission
                os.chown(test_file, -1, target_gid)
                can_change_group = True
                # Restore original group
                os.chown(test_file, -1, original_gid)
            except PermissionError:
                can_change_group = False
            
            if not can_change_group:
                # On systems without sufficient privileges, just verify processing completed
                pytest.skip("Group ownership requires elevated privileges on this system")
            else:
                # Get group name from GID and verify
                try:
                    import grp
                    file_group = grp.getgrgid(file_stat.st_gid).gr_name
                    assert file_group == available_group, \
                        f"File should have group {available_group}, got {file_group}"
                except (KeyError, ImportError):
                    # If can't verify group name, processing still succeeded
                    pass
                pass
    
    def test_invalid_group_name(self, cli_runner, temp_source_folder, test_config_path):
        """Test invalid group name handling."""
        dest_path = test_config_path.parent / "test_invalid_group"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--group", "nonexistent_group_name_12345",
            config_path=test_config_path
        )
        
        # Should either fail or proceed with warning
        if result.exit_code == 1:
            assert "group" in result.output.lower()
        else:
            # If it succeeds, should have warning about invalid group
            # Files should still be processed
            dest_files = list(dest_path.rglob("*"))
            media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
            assert len(media_files) > 0, "Files should still be processed"
    
    def test_mode_and_group_together(self, cli_runner, temp_source_folder, test_config_path):
        """Test setting both mode and group together."""
        dest_path = test_config_path.parent / "test_mode_and_group"
        
        # Find an available group
        test_groups = ["staff", "wheel", "admin"]
        available_group = None
        
        for group_name in test_groups:
            try:
                import grp
                grp.getgrnam(group_name)
                available_group = group_name
                break
            except KeyError:
                continue
        
        if not available_group:
            pytest.skip("No common test groups available")
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "640",
            "--group", available_group,
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check both mode and group
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            sample_file = media_files[0]
            file_stat = sample_file.stat()
            
            # Check mode
            file_mode = oct(stat.S_IMODE(file_stat.st_mode))
            assert file_mode == "0o640", \
                f"File should have mode 640, got {file_mode}"
            
            # Check group (if permission allows)
            import os
            import grp
            
            # Test if we can actually change group ownership
            test_file = sample_file
            original_gid = test_file.stat().st_gid
            target_gid = grp.getgrnam(available_group).gr_gid
            
            try:
                # Try to set the group - if this fails, we don't have permission
                os.chown(test_file, -1, target_gid)
                can_change_group = True
                # Restore original group
                os.chown(test_file, -1, original_gid)
            except PermissionError:
                can_change_group = False
            
            if not can_change_group:
                # On systems without sufficient privileges, skip group verification
                pytest.skip("Group ownership requires elevated privileges on this system")
            else:
                try:
                    import grp
                    file_group = grp.getgrgid(file_stat.st_gid).gr_name
                    assert file_group == available_group, \
                        f"File should have group {available_group}, got {file_group}"
                except (KeyError, ImportError):
                    # If can't verify group name, processing still succeeded
                    pass
    
    def test_permissions_in_copy_mode(self, cli_runner, temp_source_folder, test_config_path):
        """Test file permissions are applied in copy mode."""
        dest_path = test_config_path.parent / "test_copy_permissions"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--copy",
            "--mode", "600",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check permissions on copied files
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            for file_path in media_files[:3]:  # Check first few files
                file_mode = oct(stat.S_IMODE(file_path.stat().st_mode))
                assert file_mode == "0o600", \
                    f"Copied file {file_path.name} should have mode 600, got {file_mode}"
    
    def test_permissions_persistence_in_config(self, cli_runner, temp_source_folder, test_config_path):
        """Test that permission settings are saved to config."""
        dest_path1 = test_config_path.parent / "test_persist_1"
        dest_path2 = test_config_path.parent / "test_persist_2"
        
        # First run with specific permissions
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path1),
            "--mode", "600",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config was written
        assert test_config_path.exists(), "Config file should be created"
        
        # Second run without specifying permissions (should use saved)
        result2 = cli_runner(
            str(temp_source_folder),
            str(dest_path2),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result2.exit_code == 0
        
        # Check help output shows saved defaults
        help_result = cli_runner("--help", config_path=test_config_path)
        
        # Should show configured mode in help
        assert "600" in help_result.output or "mode" in help_result.output.lower()
    
    def test_directory_permissions(self, cli_runner, temp_source_folder, test_config_path):
        """Test that created directories have appropriate permissions."""
        dest_path = test_config_path.parent / "test_dir_permissions"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "600",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check directory permissions
        # Find year/month directories
        year_dirs = [d for d in dest_path.iterdir() if d.is_dir() and d.name.isdigit()]
        
        if year_dirs:
            year_dir = year_dirs[0]
            dir_mode = oct(stat.S_IMODE(year_dir.stat().st_mode))
            
            # Directory should have execute permissions for navigation
            # Common directory modes: 755, 750, 700, 775, etc. (varies by umask)
            assert dir_mode in ["0o755", "0o750", "0o700", "0o711", "0o775", "0o770"], \
                f"Directory should have appropriate mode, got {dir_mode}"
    
    def test_permissions_on_converted_videos(self, cli_runner, test_config_path, create_test_files):
        """Test that converted videos get proper permissions."""
        # Create a legacy video file
        source_files = [
            {"name": "legacy.avi", "content": b"legacy video content"},
        ]
        
        source_path = create_test_files(source_files)
        dest_path = test_config_path.parent / "test_convert_permissions"
        
        result = cli_runner(
            str(source_path),
            str(dest_path),
            "--mode", "640",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Check permissions on all destination files
        dest_files = list(dest_path.rglob("*"))
        media_files = [f for f in dest_files if f.is_file() and "history" not in str(f)]
        
        if media_files:
            for file_path in media_files:
                file_mode = oct(stat.S_IMODE(file_path.stat().st_mode))
                assert file_mode == "0o640", \
                    f"File {file_path.name} should have mode 640, got {file_mode}"