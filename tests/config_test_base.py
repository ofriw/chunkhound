"""
Unified base class for configuration testing with complete isolation.

This module provides a single, comprehensive testing infrastructure for all
config-related tests, consolidating the various isolation patterns that have
evolved across the test suite.
"""

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from chunkhound.core.config.config import Config, reset_config


class ConfigTestBase:
    """
    Unified base class for all config-related tests with complete isolation.

    Provides comprehensive isolation from:
    - Environment variables (CHUNKHOUND_*)
    - Local config files (.chunkhound.json)
    - Project root detection
    - Global config singleton state
    - File system state

    Usage:
        class TestMyConfig(ConfigTestBase):
            def test_something(self):
                config = self.create_isolated_config(
                    embedding={"provider": "openai", "api_key": "test"}
                )
                assert config.embedding.provider == "openai"
    """

    def setup_method(self):
        """Complete isolation setup."""
        # 1. Global config singleton reset
        reset_config()

        # 2. Environment variable isolation
        self.original_env = os.environ.copy()
        self._clear_chunkhound_env()

        # 3. Filesystem isolation
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()
        self.config_file = self.temp_dir / "config.json"
        self.local_config = self.project_dir / ".chunkhound.json"

    def teardown_method(self):
        """Complete cleanup."""
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)

        # Clean filesystem
        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Reset global state
        reset_config()

    def _clear_chunkhound_env(self):
        """Clear all CHUNKHOUND_* environment variables."""
        keys_to_remove = [
            key for key in os.environ.keys() if key.startswith("CHUNKHOUND_")
        ]
        for key in keys_to_remove:
            del os.environ[key]

    def create_isolated_config(self, args=None, mock_project_root=None, **kwargs):
        """
        Create completely isolated config instance.

        Args:
            args: Optional argparse.Namespace for CLI arguments
            mock_project_root: Directory to use as project root (defaults to temp_dir)
            **kwargs: Direct config overrides

        Returns:
            Config instance with complete isolation from environment
        """
        if mock_project_root is None:
            mock_project_root = self.temp_dir

        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = mock_project_root
            return Config(args=args, **kwargs)

    def create_mock_args(self, **kwargs):
        """
        Create comprehensive mock args object with proper attribute access.

        Args:
            **kwargs: Arguments to override

        Returns:
            argparse.Namespace with all CLI attributes set
        """
        args = argparse.Namespace()

        # Set defaults for all possible CLI arguments
        defaults = {
            "config": None,
            "path": None,
            "db": None,
            "database_provider": None,
            "database_lancedb_index_type": None,
            "provider": None,
            "model": None,
            "api_key": None,
            "base_url": None,
            "embedding_batch_size": None,
            "embedding_max_concurrent": None,
            "http": None,
            "port": None,
            "host": None,
            "cors": None,
            "batch_size": None,
            "max_concurrent": None,
            "cleanup": None,
            "indexing_ignore_gitignore": None,
            "include": None,
            "exclude": None,
            "debug": None,
            "verbose": None,
        }

        # Set defaults
        for key, value in defaults.items():
            setattr(args, key, kwargs.get(key, value))

        # Override with any additional kwargs
        for key, value in kwargs.items():
            setattr(args, key, value)

        return args

    def create_config_file(self, path=None, **config_data):
        """
        Helper for creating JSON config files.

        Args:
            path: Path to write config file (defaults to self.config_file)
            **config_data: Configuration data to write

        Returns:
            Path to created config file
        """
        if path is None:
            path = self.config_file

        with open(path, "w") as f:
            json.dump(config_data, f, indent=2)

        return path

    def create_local_config(self, **config_data):
        """
        Helper for creating .chunkhound.json files in project directory.

        Args:
            **config_data: Configuration data to write

        Returns:
            Path to created local config file
        """
        with open(self.local_config, "w") as f:
            json.dump(config_data, f, indent=2)

        return self.local_config

    def set_env_vars(self, **env_vars):
        """
        Helper for setting CHUNKHOUND_* environment variables.

        Args:
            **env_vars: Environment variables to set (without CHUNKHOUND_ prefix)
                       Use double underscores for nesting (DATABASE__PATH)
        """
        for key, value in env_vars.items():
            full_key = f"CHUNKHOUND_{key.upper()}"
            os.environ[full_key] = str(value)
