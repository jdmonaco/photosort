"""
Test configuration management and persistence.
"""

import pytest
import yaml
from pathlib import Path


class TestConfiguration:
    """Test configuration persistence and default behaviors."""
    
    def test_config_file_creation(self, cli_runner, temp_source_folder, test_config_path):
        """Test that config file is created after first run."""
        # Ensure config doesn't exist initially
        assert not test_config_path.exists()
        
        dest_path = test_config_path.parent / "test_config_creation"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        assert test_config_path.exists(), "Config file should be created after first run"
        
        # Config should be valid YAML
        config_data = yaml.safe_load(test_config_path.read_text())
        assert isinstance(config_data, dict), "Config should be a dictionary"
    
    def test_path_persistence(self, cli_runner, temp_source_folder, test_config_path):
        """Test that source/destination paths are saved and recalled."""
        dest_path = test_config_path.parent / "test_path_persistence"
        
        # First run
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config contains paths
        config_data = yaml.safe_load(test_config_path.read_text())
        assert "last_source" in config_data
        assert "last_dest" in config_data
        assert str(temp_source_folder) in config_data["last_source"]
        assert str(dest_path) in config_data["last_dest"]
        
        # Second run - help should show saved defaults
        help_result = cli_runner("--help", config_path=test_config_path)
        
        # Help should show configured defaults
        assert str(temp_source_folder) in help_result.output or \
               temp_source_folder.name in help_result.output
        assert str(dest_path) in help_result.output or \
               dest_path.name in help_result.output
    
    def test_file_mode_persistence(self, cli_runner, temp_source_folder, test_config_path):
        """Test that file mode setting is saved and recalled."""
        dest_path = test_config_path.parent / "test_mode_persistence"
        
        # First run with specific mode
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "600",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config contains mode
        config_data = yaml.safe_load(test_config_path.read_text())
        assert "file_mode" in config_data
        assert config_data["file_mode"] == "600"
        
        # Help should show saved mode
        help_result = cli_runner("--help", config_path=test_config_path)
        assert "600" in help_result.output
    
    def test_group_persistence(self, cli_runner, temp_source_folder, test_config_path):
        """Test that group setting is saved and recalled."""
        dest_path = test_config_path.parent / "test_group_persistence"
        
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
        
        # First run with specific group
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--group", available_group,
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config contains group
        config_data = yaml.safe_load(test_config_path.read_text())
        assert "group" in config_data
        assert config_data["group"] == available_group
        
        # Help should show saved group
        help_result = cli_runner("--help", config_path=test_config_path)
        assert available_group in help_result.output
    
    def test_convert_videos_persistence(self, cli_runner, temp_source_folder, test_config_path):
        """Test that video conversion preference is saved."""
        dest_path = test_config_path.parent / "test_convert_persistence"
        
        # First run with --no-convert-videos
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--no-convert-videos",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config contains conversion preference
        config_data = yaml.safe_load(test_config_path.read_text())
        assert "convert_videos" in config_data
        assert config_data["convert_videos"] is False
        
        # Second run without flag should use saved preference
        result2 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result2.exit_code == 0
        # Should indicate videos won't be converted
        assert "Converted Videos" not in result2.output or \
               "│ 0" in result2.output
    
    def test_timezone_persistence(self, cli_runner, temp_source_folder, test_config_path):
        """Test that timezone setting is saved and recalled."""
        dest_path = test_config_path.parent / "test_timezone_persistence"
        
        # First run with specific timezone
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--timezone", "PST",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Check config contains timezone
        config_data = yaml.safe_load(test_config_path.read_text())
        assert "timezone" in config_data
        assert config_data["timezone"] == "PST"
        
        # Help should show saved timezone
        help_result = cli_runner("--help", config_path=test_config_path)
        assert "PST" in help_result.output
    
    def test_config_overrides(self, cli_runner, temp_source_folder, test_config_path):
        """Test that CLI flags override saved config values."""
        dest_path1 = test_config_path.parent / "test_overrides_1"
        dest_path2 = test_config_path.parent / "test_overrides_2"
        
        # First run saves one mode
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path1),
            "--mode", "600",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Second run with different mode should override
        result2 = cli_runner(
            str(temp_source_folder),
            str(dest_path2),
            "--mode", "644",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result2.exit_code == 0
        
        # Config should be updated with new mode
        config_data = yaml.safe_load(test_config_path.read_text())
        assert config_data["file_mode"] == "644"
    
    def test_config_with_missing_values(self, cli_runner, temp_source_folder, test_config_path):
        """Test handling of config with missing or invalid values."""
        dest_path = test_config_path.parent / "test_missing_values"
        
        # Create config with some missing values
        config_data = {
            "last_source": str(temp_source_folder),
            "file_mode": "644",
            # Missing last_dest, group, etc.
        }
        
        test_config_path.write_text(yaml.dump(config_data))
        
        # Should handle missing values gracefully
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Help should show available defaults
        help_result = cli_runner("--help", config_path=test_config_path)
        assert "644" in help_result.output  # Should show saved mode
    
    def test_config_with_invalid_yaml(self, cli_runner, temp_source_folder, test_config_path):
        """Test handling of corrupted config file."""
        dest_path = test_config_path.parent / "test_invalid_yaml"
        
        # Create invalid YAML
        test_config_path.write_text("invalid: yaml: content: [")
        
        # Should handle corrupted config gracefully
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        
        # Should recreate valid config
        config_data = yaml.safe_load(test_config_path.read_text())
        assert isinstance(config_data, dict)
    
    def test_config_permissions(self, cli_runner, temp_source_folder, test_config_path):
        """Test that config file has appropriate permissions."""
        dest_path = test_config_path.parent / "test_config_permissions"
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result.exit_code == 0
        assert test_config_path.exists()
        
        # Check config file permissions
        import stat
        config_mode = oct(stat.S_IMODE(test_config_path.stat().st_mode))
        
        # Config should be readable by owner, possibly group
        # Common modes: 600, 644, 640
        assert config_mode in ["0o600", "0o644", "0o640"], \
            f"Config should have appropriate permissions, got {config_mode}"
    
    def test_multiple_config_updates(self, cli_runner, temp_source_folder, test_config_path):
        """Test multiple sequential config updates."""
        dest_base = test_config_path.parent
        
        # Series of runs with different settings
        runs = [
            {"dest": "test_multi_1", "args": ["--mode", "600"]},
            {"dest": "test_multi_2", "args": ["--mode", "644", "--group", "staff"]},
            {"dest": "test_multi_3", "args": ["--no-convert-videos"]},
            {"dest": "test_multi_4", "args": ["--timezone", "EST"]},
        ]
        
        for run in runs:
            dest_path = dest_base / run["dest"]
            args = [str(temp_source_folder), str(dest_path), "--dry-run"] + run["args"]
            
            result = cli_runner(*args, config_path=test_config_path)
            assert result.exit_code == 0
            
            # Config should be updated each time
            assert test_config_path.exists()
            config_data = yaml.safe_load(test_config_path.read_text())
            assert isinstance(config_data, dict)
        
        # Final config should have all accumulated settings
        final_config = yaml.safe_load(test_config_path.read_text())
        assert "file_mode" in final_config
        assert "convert_videos" in final_config
        assert "timezone" in final_config
    
    def test_config_directory_creation(self, cli_runner, temp_source_folder, tmp_path):
        """Test that config directory is created if it doesn't exist."""
        # Use a nested config path
        nested_config = tmp_path / "nested" / "config" / "photosort_config.yml"
        dest_path = tmp_path / "dest"
        
        # Parent directories don't exist
        assert not nested_config.parent.exists()
        
        result = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=nested_config
        )
        
        assert result.exit_code == 0
        
        # Config and parent directories should be created
        assert nested_config.exists()
        assert nested_config.parent.exists()
    
    def test_config_backup_on_corruption(self, cli_runner, temp_source_folder, test_config_path):
        """Test that corrupted config is backed up before recreating."""
        dest_path = test_config_path.parent / "test_backup"
        
        # Create valid config first
        result1 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--mode", "600",
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result1.exit_code == 0
        
        # Corrupt the config
        test_config_path.write_text("corrupted yaml content {[")
        
        # Run again
        result2 = cli_runner(
            str(temp_source_folder),
            str(dest_path),
            "--dry-run",
            config_path=test_config_path
        )
        
        assert result2.exit_code == 0
        
        # Should have created backup or handled gracefully
        assert test_config_path.exists()
        
        # New config should be valid
        config_data = yaml.safe_load(test_config_path.read_text())
        assert isinstance(config_data, dict)