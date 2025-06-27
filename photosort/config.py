"""
Configuration management for photosort.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Optional

import yaml


class Config:
    """Manages configuration file for storing user preferences."""

    def __init__(self, config_path: Optional[Path] = None):
        # Default config location: ~/.photosort/config.yml
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = Path.home() / ".photosort" / "config.yml"

        self.data = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger = logging.getLogger("photosort")
            logger.warning(f"Could not load config: {e}")
            return {}

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(self.data, f, default_flow_style=False)
        except Exception as e:
            logger = logging.getLogger("photosort")
            logger.error(f"Could not save config: {e}")

    def get_last_source(self) -> Optional[str]:
        """Get the last used source directory."""
        return self.data.get('last_source')

    def get_last_dest(self) -> Optional[str]:
        """Get the last used destination directory."""
        return self.data.get('last_dest')

    def get_file_mode(self) -> Optional[str]:
        """Get the saved file mode setting."""
        return self.data.get('file_mode')

    def get_group(self) -> Optional[str]:
        """Get the saved group setting."""
        return self.data.get('group')

    def update_paths(self, source: str, dest: str) -> None:
        """Update and save the last used paths."""
        self.data['last_source'] = source
        self.data['last_dest'] = dest
        self.save_config()

    def update_file_mode(self, mode: str) -> None:
        """Update and save the file mode setting."""
        self.data['file_mode'] = mode
        self.save_config()

    def update_group(self, group: str) -> None:
        """Update and save the group setting."""
        self.data['group'] = group
        self.save_config()
