"""
Comprehensive tests for the unified configuration system.

Tests verify:
1. Precedence order (CLI > env vars > config file > defaults)
2. All initialization contexts (CLI, MCP servers, direct)
3. Configuration merging behavior
4. Error handling and validation
5. Project detection and local config loading
6. Backward compatibility
"""

import json
import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch
import pytest

from chunkhound.core.config.config import Config, reset_config
from chunkhound.core.config.database_config import DatabaseConfig
from chunkhound.core.config.embedding_config import EmbeddingConfig
from chunkhound.core.config.mcp_config import MCPConfig
from chunkhound.core.config.indexing_config import IndexingConfig
from tests.config_test_base import ConfigTestBase


class TestUnifiedConfigPrecedence(ConfigTestBase):
    """Test configuration precedence order."""

    def test_default_values_only(self):
        """Test config with only default values."""
        config = self.create_isolated_config()

        # Should have default values
        assert config.debug is False
        assert config.database.provider == "duckdb"
        assert config.mcp.transport == "stdio"
        assert config.indexing.watch is False
        assert config.embedding is None  # No default embedding

    def test_config_file_overrides_defaults(self):
        """Test that config file overrides default values."""
        # Create config file
        self.create_config_file(
            debug=True,
            database={"provider": "lancedb"},
            mcp={"transport": "http", "port": 8080},
        )

        # Create args with config file
        args = self.create_mock_args(config=str(self.config_file))

        config = self.create_isolated_config(args=args)

        # Config file values should override defaults
        assert config.debug is True
        assert config.database.provider == "lancedb"
        assert config.mcp.transport == "http"
        assert config.mcp.port == 8080

        # Unspecified values should remain default
        assert config.indexing.watch is False

    def test_env_vars_override_config_file(self):
        """Test that environment variables override config file."""
        # Create config file
        self.create_config_file(
            debug=False,
            database={"provider": "duckdb", "path": "/file/path"},
            embedding={"provider": "openai", "model": "text-embedding-ada-002"},
        )

        # Set environment variables
        self.set_env_vars(
            DEBUG="true",
            DATABASE__PROVIDER="lancedb",
            EMBEDDING__MODEL="text-embedding-3-small",
        )

        # Create args with config file
        args = self.create_mock_args(config=str(self.config_file))

        config = self.create_isolated_config(args=args)

        # Env vars should override config file
        assert config.debug is True
        assert config.database.provider == "lancedb"
        assert config.embedding.model == "text-embedding-3-small"

        # Config file value not overridden by env should remain
        assert str(config.database.path) == "/file/path"
        assert config.embedding.provider == "openai"

    def test_cli_args_override_everything(self):
        """Test that CLI arguments have highest precedence."""
        # Create config file
        self.create_config_file(
            debug=False,
            database={"provider": "duckdb"},
            embedding={"provider": "openai", "batch_size": 100},
        )

        # Set environment variables
        self.set_env_vars(
            DEBUG="false", DATABASE__PROVIDER="lancedb", EMBEDDING__BATCH_SIZE="200"
        )

        # Create args with CLI overrides
        args = self.create_mock_args(
            config=str(self.config_file),
            debug=True,
            database_provider="duckdb",  # Override env var
            provider="openai",  # Override embedding provider
            embedding_batch_size=300,  # Override both config and env
        )

        config = self.create_isolated_config(args=args)

        # CLI args should override everything
        assert config.debug is True
        assert config.database.provider == "duckdb"
        assert config.embedding.provider == "openai"
        assert config.embedding.batch_size == 300

    def test_local_config_file_discovery(self):
        """Test automatic discovery of .chunkhound.json in project directory."""
        # Create local config
        self.create_local_config(
            database={"path": str(self.project_dir / "local.db")},
            indexing={"watch": True, "exclude": ["*.log"]},
        )

        # Create args pointing to project directory
        args = self.create_mock_args(path=str(self.project_dir))

        config = self.create_isolated_config(
            args=args, mock_project_root=self.project_dir
        )

        # Should load local config
        assert str(config.database.path) == str(self.project_dir / "local.db")
        assert config.indexing.watch is True
        assert "*.log" in config.indexing.exclude

    def test_explicit_config_and_local_config_merge(self):
        """Test config file merging behavior.

        NOTE: Current implementation loads configs in this order:
        1. Explicit config (--config)
        2. Local config (.chunkhound.json)
        3. Environment variables
        4. CLI arguments

        This means local config can override explicit config, which may be unexpected.
        This test documents the current behavior.
        """
        # Create local config with some values
        self.create_local_config(
            debug=True, database={"provider": "lancedb"}, indexing={"watch": True}
        )

        # Create explicit config
        self.create_config_file(
            debug=False,
            database={"provider": "duckdb"},
            mcp={"port": 8080},  # This will remain from explicit config
        )

        # Create args with explicit config
        args = self.create_mock_args(
            config=str(self.config_file), path=str(self.project_dir)
        )

        # Config loads both files with current merge order
        config = self.create_isolated_config(
            args=args, mock_project_root=self.project_dir
        )

        # Current behavior: local config overrides explicit config
        assert config.debug is True  # From local config (overrides explicit)
        assert (
            config.database.provider == "lancedb"
        )  # From local config (overrides explicit)
        assert config.indexing.watch is True  # From local config
        assert config.mcp.port == 8080  # From explicit config (not in local)


class TestConfigInitializationContexts(ConfigTestBase):
    """Test config initialization in different contexts."""

    def test_cli_command_context(self):
        """Test config initialization in CLI command context."""
        # Simulate CLI args from index command
        args = self.create_mock_args(
            command="index",
            path="/some/path",
            db=str(self.temp_dir / "cli.db"),
            provider="openai",
            model="text-embedding-3-large",
            watch=True,
            verbose=True,
        )

        config = self.create_isolated_config(args=args)

        assert str(config.database.path) == str(self.temp_dir / "cli.db")
        assert config.embedding.provider == "openai"
        assert config.embedding.model == "text-embedding-3-large"
        assert config.indexing.watch is True
        assert config.debug is True  # verbose maps to debug

    def test_mcp_stdio_server_context(self):
        """Test config initialization in MCP stdio server context."""
        # Set up environment as MCP launcher would
        self.set_env_vars(
            MCP_MODE="1",
            DATABASE__PATH=str(self.temp_dir / "mcp.db"),
            EMBEDDING__PROVIDER="openai",
            EMBEDDING__API_KEY="test-key",
        )

        # MCP servers now use args pattern
        args = self.create_mock_args(command="mcp", subcommand="stdio")

        config = self.create_isolated_config(args=args)

        assert str(config.database.path) == str(self.temp_dir / "mcp.db")
        assert config.embedding.provider == "openai"
        assert config.mcp.transport == "stdio"  # Default for stdio

    def test_mcp_http_server_context(self):
        """Test config initialization in MCP HTTP server context."""
        # Simulate HTTP server args
        args = self.create_mock_args(
            command="mcp",
            subcommand="http",
            port=5173,
            host="0.0.0.0",
            cors=True,
            http=True,  # This should trigger transport=http
        )

        # Set some env vars
        self.set_env_vars(DATABASE__PATH=str(self.temp_dir / "http.db"))

        config = self.create_isolated_config(args=args)

        assert config.mcp.transport == "http"  # Should be set by args processor
        assert config.mcp.port == 5173
        assert config.mcp.host == "0.0.0.0"
        assert config.mcp.cors is True
        assert str(config.database.path) == str(self.temp_dir / "http.db")

    def test_direct_instantiation_context(self):
        """Test direct config instantiation (for testing/special cases)."""
        # Direct kwargs override everything
        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = self.temp_dir
            config = Config(
                debug=True,
                database={"provider": "lancedb", "path": "/direct/path"},
                embedding={"provider": "tei", "base_url": "http://localhost:8080"},
            )

        assert config.debug is True
        assert config.database.provider == "lancedb"
        assert str(config.database.path) == "/direct/path"
        assert config.embedding.provider == "tei"
        assert config.embedding.base_url == "http://localhost:8080"

    def test_env_only_context(self):
        """Test config with only environment variables (no args)."""
        self.set_env_vars(
            DEBUG="true",
            DATABASE__PROVIDER="duckdb",
            EMBEDDING__PROVIDER="tei",
            EMBEDDING__BASE_URL="http://localhost:8080",
        )

        # No args provided
        config = self.create_isolated_config()

        assert config.debug is True
        assert config.database.provider == "duckdb"
        assert config.embedding.provider == "tei"
        assert config.embedding.base_url == "http://localhost:8080"


class TestConfigMergingBehavior(ConfigTestBase):
    """Test deep merging behavior of configuration."""

    def test_nested_config_merging(self):
        """Test that nested configurations merge properly."""
        # Create config file with partial nested config
        self.create_config_file(
            database={"provider": "lancedb", "lancedb_index_type": "IVF_PQ"},
            embedding={"provider": "openai", "model": "text-embedding-ada-002"},
        )

        # Set env vars that add to nested config
        self.set_env_vars(DATABASE__PATH="/env/path", EMBEDDING__API_KEY="env-key")

        # CLI args that further modify
        args = self.create_mock_args(
            config=str(self.config_file), embedding_batch_size=500
        )

        config = self.create_isolated_config(args=args)

        # All values should be merged
        assert config.database.provider == "lancedb"
        assert config.database.lancedb_index_type == "IVF_PQ"
        assert str(config.database.path) == "/env/path"
        assert config.embedding.provider == "openai"
        assert config.embedding.model == "text-embedding-ada-002"
        assert config.embedding.api_key.get_secret_value() == "env-key"
        assert config.embedding.batch_size == 500

    def test_array_config_replacement(self):
        """Test that array configurations are replaced, not merged."""
        # Create config with arrays
        self.create_config_file(
            indexing={"include": ["*.py", "*.js"], "exclude": ["test_*", "*.log"]}
        )

        # Env vars should replace arrays
        self.set_env_vars(INDEXING__EXCLUDE="*.tmp,*.cache")

        # CLI args should replace entirely
        args = self.create_mock_args(
            config=str(self.config_file), include=["*.ts", "*.tsx"]
        )

        config = self.create_isolated_config(args=args)

        # CLI args replace config file
        assert config.indexing.include == ["*.ts", "*.tsx"]
        # Env var replaces config file
        assert config.indexing.exclude == ["*.tmp", "*.cache"]


class TestConfigErrorHandling(ConfigTestBase):
    """Test configuration error handling."""

    def test_invalid_json_config_file(self):
        """Test handling of invalid JSON in config file."""
        config_file = self.temp_dir / "bad.json"
        with open(config_file, "w") as f:
            f.write("{ invalid json ]")

        args = Mock()
        args.config = str(config_file)
        args.path = None

        with pytest.raises(ValueError) as exc_info:
            Config(args=args)

        assert "Invalid JSON" in str(exc_info.value)
        assert str(config_file) in str(exc_info.value)

    def test_missing_config_file(self):
        """Test that missing config file doesn't raise error."""
        args = self.create_mock_args(config="/nonexistent/config.json")

        # Should not raise - just ignore missing file
        config = self.create_isolated_config(args=args)
        assert config is not None

    def test_invalid_env_var_values(self):
        """Test handling of invalid environment variable values."""
        # Set invalid integer value
        self.set_env_vars(MCP__PORT="not-a-number")

        # Should raise validation error
        with pytest.raises(Exception):
            self.create_isolated_config()

    def test_project_root_detection_fallback(self):
        """Test fallback when project root detection fails."""
        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = Path.cwd()

            config = Config()

            # Should still create valid config
            assert config.database.path is not None
            assert config.database.path.is_absolute()


class TestConfigValidation(ConfigTestBase):
    """Test configuration validation methods."""

    def test_validate_for_command(self):
        """Test command-specific validation."""
        # Create config missing embedding info
        config = self.create_isolated_config()

        # Index command can work without embeddings (--no-embeddings flag)
        errors = config.validate_for_command("index")
        assert len(errors) == 0

        # Search command works without embeddings (regex search)
        errors = config.validate_for_command("search")
        assert len(errors) == 0

        # Test that provider-specific validation works when embedding config exists
        import tempfile

        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = Path(tempfile.mkdtemp())
            config_with_invalid = Config(
                embedding={"provider": "openai-compatible"}  # missing base_url
            )
        errors = config_with_invalid.validate_for_command("index")
        assert len(errors) > 0
        assert any("base-url" in err.lower() for err in errors)

    def test_get_missing_config(self):
        """Test identification of missing config."""
        config = self.create_isolated_config()

        missing = config.get_missing_config()
        # Config without embedding should be complete (can work without embeddings)
        assert len(missing) == 0

        # Test with incomplete embedding config
        import tempfile
        from chunkhound.core.config.embedding_config import EmbeddingConfig

        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = Path(tempfile.mkdtemp())
            config_with_incomplete = Config(
                embedding={"provider": "openai"}
            )  # missing api_key

        missing = config_with_incomplete.get_missing_config()
        assert any("api_key" in item for item in missing)

        # Complete embedding config should have no missing items
        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = Path(tempfile.mkdtemp())
            config_complete = Config(
                embedding={"provider": "openai", "api_key": "test-key"}
            )

        missing = config_complete.get_missing_config()
        assert len(missing) == 0

    def test_is_fully_configured(self):
        """Test full configuration check."""
        config = self.create_isolated_config()
        assert not config.is_fully_configured()

        # Add embedding
        config.embedding = EmbeddingConfig(provider="openai", api_key="test-key")
        assert config.is_fully_configured()


class TestBackwardCompatibility(ConfigTestBase):
    """Test backward compatibility with old patterns."""

    def test_legacy_env_var_names(self):
        """Test that legacy environment variable names still work."""
        # Set legacy env vars
        self.set_env_vars(DB_PATH="/legacy/db/path")

        config = self.create_isolated_config()

        # Should still recognize legacy names
        assert str(config.database.path) == "/legacy/db/path"

    def test_global_config_singleton(self):
        """Test global config singleton pattern."""
        from chunkhound.core.config.config import get_config, set_config, reset_config

        # First call creates config
        config1 = get_config()
        assert config1 is not None

        # Second call returns same instance
        config2 = get_config()
        assert config2 is config1

        # Can set new config
        new_config = Config(debug=True)
        set_config(new_config)

        config3 = get_config()
        assert config3 is new_config
        assert config3.debug is True

        # Reset clears singleton
        reset_config()
        config4 = get_config()
        assert config4 is not config1
        assert config4 is not new_config


class TestRegressionPrevention(ConfigTestBase):
    """Tests specifically designed to prevent regressions."""

    def test_mcp_server_config_consistency(self):
        """Ensure MCP servers always use consistent config."""
        # Both servers should use same pattern
        stdio_args = self.create_mock_args(command="mcp", subcommand="stdio")
        http_args = self.create_mock_args(
            command="mcp", subcommand="http", port=5173, http=True
        )

        # Set same env
        self.set_env_vars(DATABASE__PATH=str(self.temp_dir / "mcp.db"))

        stdio_config = self.create_isolated_config(args=stdio_args)
        http_config = self.create_isolated_config(args=http_args)

        # Should have same database path
        assert stdio_config.database.path == http_config.database.path

        # Transport should differ based on args
        assert stdio_config.mcp.transport == "stdio"
        assert http_config.mcp.transport == "http"

    def test_cli_command_always_respects_local_config(self):
        """Ensure CLI commands always check for local .chunkhound.json."""
        # Create local config in temp_dir (not project_dir)
        self.create_config_file(
            path=self.temp_dir / ".chunkhound.json", database={"provider": "lancedb"}
        )

        # Simulate different CLI commands
        for command in ["index", "search", "run"]:
            args = self.create_mock_args(command=command, path=str(self.temp_dir))

            config = self.create_isolated_config(
                args=args, mock_project_root=self.temp_dir
            )

            # Should always load local config
            assert config.database.provider == "lancedb", (
                f"{command} didn't load local config"
            )

    def test_no_side_effects_on_import(self):
        """Ensure importing config module has no side effects."""
        # Import should not modify environment
        env_before = os.environ.copy()

        from chunkhound.core.config import config as config_module

        env_after = os.environ.copy()
        assert env_before == env_after

        # Import should not create any files in temp dir
        assert not (self.temp_dir / ".chunkhound.json").exists()
        assert not (self.temp_dir / ".chunkhound").exists()

    def test_config_file_env_var_discovery(self):
        """Test CHUNKHOUND_CONFIG_FILE environment variable."""
        # Create config file
        env_config = self.temp_dir / "env-config.json"
        self.create_config_file(path=env_config, debug=True)

        self.set_env_vars(CONFIG_FILE=str(env_config))

        config = self.create_isolated_config()

        # Should load config from env var
        assert config.debug is True

    def test_database_path_resolution(self):
        """Test database path resolution and defaults."""
        # No path specified
        config = self.create_isolated_config()

        # Should have default path in project root
        assert config.database.path is not None
        assert config.database.path.is_absolute()
        assert ".chunkhound" in str(config.database.path)
        assert "db" in str(config.database.path)

        # Relative path should be made absolute
        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = self.temp_dir
            config = Config(database={"path": "relative/path"})
            assert config.database.path.is_absolute()
