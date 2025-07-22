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
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch
import pytest
import argparse

from chunkhound.core.config.config import Config, reset_config
from chunkhound.core.config.database_config import DatabaseConfig
from chunkhound.core.config.embedding_config import EmbeddingConfig
from chunkhound.core.config.mcp_config import MCPConfig
from chunkhound.core.config.indexing_config import IndexingConfig


class ConfigTestBase:
    """Base class for config tests with proper isolation."""
    
    def create_mock_args(self, **kwargs):
        """Create mock args object with proper attribute access."""
        args = argparse.Namespace()
        # Set defaults for all possible args
        defaults = {
            'config': None,
            'path': None,
            'db': None,
            'database_provider': None,
            'database_lancedb_index_type': None,
            'provider': None,
            'model': None,
            'api_key': None,
            'base_url': None,
            'embedding_batch_size': None,
            'embedding_max_concurrent': None,
            'http': None,
            'port': None,
            'host': None,
            'cors': None,
            'watch': None,
            'debounce_ms': None,
            'batch_size': None,
            'max_concurrent': None,
            'periodic': None,
            'periodic_interval_minutes': None,
            'periodic_full_reindex': None,
            'cleanup': None,
            'indexing_ignore_gitignore': None,
            'include': None,
            'exclude': None,
            'debug': None,
            'verbose': None,
        }
        # Update with provided values
        for key, value in defaults.items():
            setattr(args, key, kwargs.get(key, value))
        # Override with any additional kwargs
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args
    
    def create_isolated_config(self, args=None, mock_project_root=None):
        """Create config with proper isolation from environment."""
        if mock_project_root is None:
            mock_project_root = getattr(self, 'temp_dir', Path(tempfile.mkdtemp()))
        
        with patch("chunkhound.utils.project_detection.find_project_root") as mock_find:
            mock_find.return_value = mock_project_root
            return Config(args=args)


class TestUnifiedConfigPrecedence(ConfigTestBase):
    """Test configuration precedence order."""
    
    def setup_method(self):
        """Reset environment and create temp directories."""
        reset_config()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()
        self.config_file = self.temp_dir / "config.json"
        self.local_config = self.project_dir / ".chunkhound.json"
        
        # Store original env vars
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_config()
    
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
        config_data = {
            "debug": True,
            "database": {"provider": "lancedb"},
            "mcp": {"transport": "http", "port": 8080}
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
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
        config_data = {
            "debug": False,
            "database": {"provider": "duckdb", "path": "/file/path"},
            "embedding": {"provider": "openai", "model": "text-embedding-ada-002"}
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
        # Set environment variables
        os.environ["CHUNKHOUND_DEBUG"] = "true"
        os.environ["CHUNKHOUND_DATABASE__PROVIDER"] = "lancedb"
        os.environ["CHUNKHOUND_EMBEDDING__MODEL"] = "text-embedding-3-small"
        
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
        config_data = {
            "debug": False,
            "database": {"provider": "duckdb"},
            "embedding": {"provider": "openai", "batch_size": 100}
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
        # Set environment variables
        os.environ["CHUNKHOUND_DEBUG"] = "false"
        os.environ["CHUNKHOUND_DATABASE__PROVIDER"] = "lancedb"
        os.environ["CHUNKHOUND_EMBEDDING__BATCH_SIZE"] = "200"
        
        # Create args with CLI overrides
        args = self.create_mock_args(
            config=str(self.config_file),
            debug=True,
            database_provider="duckdb",  # Override env var
            provider="openai",  # Override embedding provider
            embedding_batch_size=300  # Override both config and env
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
        local_config_data = {
            "database": {"path": str(self.project_dir / "local.db")},
            "indexing": {"watch": True, "exclude": ["*.log"]}
        }
        with open(self.local_config, "w") as f:
            json.dump(local_config_data, f)
        
        # Create args pointing to project directory
        args = self.create_mock_args(path=str(self.project_dir))
        
        config = self.create_isolated_config(args=args, mock_project_root=self.project_dir)
        
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
        local_config_data = {
            "debug": True, 
            "database": {"provider": "lancedb"},
            "indexing": {"watch": True}
        }
        with open(self.local_config, "w") as f:
            json.dump(local_config_data, f)
        
        # Create explicit config
        explicit_config_data = {
            "debug": False,
            "database": {"provider": "duckdb"},
            "mcp": {"port": 8080}  # This will remain from explicit config
        }
        with open(self.config_file, "w") as f:
            json.dump(explicit_config_data, f)
        
        # Create args with explicit config
        args = self.create_mock_args(
            config=str(self.config_file),
            path=str(self.project_dir)
        )
        
        # Config loads both files with current merge order
        config = self.create_isolated_config(args=args, mock_project_root=self.project_dir)
        
        # Current behavior: local config overrides explicit config
        assert config.debug is True  # From local config (overrides explicit)
        assert config.database.provider == "lancedb"  # From local config (overrides explicit)
        assert config.indexing.watch is True  # From local config
        assert config.mcp.port == 8080  # From explicit config (not in local)


class TestConfigInitializationContexts(ConfigTestBase):
    """Test config initialization in different contexts."""
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_config()
    
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
            verbose=True
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
        os.environ["CHUNKHOUND_MCP_MODE"] = "1"
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "mcp.db")
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "test-key"
        
        # MCP servers now use args pattern
        args = self.create_mock_args(
            command="mcp",
            subcommand="stdio"
        )
        
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
            http=True  # This should trigger transport=http
        )
        
        # Set some env vars
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "http.db")
        
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
                embedding={"provider": "tei", "base_url": "http://localhost:8080"}
            )
        
        assert config.debug is True
        assert config.database.provider == "lancedb"
        assert str(config.database.path) == "/direct/path"
        assert config.embedding.provider == "tei"
        assert config.embedding.base_url == "http://localhost:8080"
    
    def test_env_only_context(self):
        """Test config with only environment variables (no args)."""
        os.environ["CHUNKHOUND_DEBUG"] = "true"
        os.environ["CHUNKHOUND_DATABASE__PROVIDER"] = "duckdb"
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "tei"
        os.environ["CHUNKHOUND_EMBEDDING__BASE_URL"] = "http://localhost:8080"
        
        # No args provided
        config = self.create_isolated_config()
        
        assert config.debug is True
        assert config.database.provider == "duckdb"
        assert config.embedding.provider == "tei"
        assert config.embedding.base_url == "http://localhost:8080"


class TestConfigMergingBehavior(ConfigTestBase):
    """Test deep merging behavior of configuration."""
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "config.json"
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_config()
    
    def test_nested_config_merging(self):
        """Test that nested configurations merge properly."""
        # Create config file with partial nested config
        config_data = {
            "database": {
                "provider": "lancedb",
                "lancedb_index_type": "IVF_PQ"
            },
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-ada-002"
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
        # Set env vars that add to nested config
        os.environ["CHUNKHOUND_DATABASE__PATH"] = "/env/path"
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "env-key"
        
        # CLI args that further modify
        args = self.create_mock_args(
            config=str(self.config_file),
            embedding_batch_size=500
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
        config_data = {
            "indexing": {
                "include": ["*.py", "*.js"],
                "exclude": ["test_*", "*.log"]
            }
        }
        with open(self.config_file, "w") as f:
            json.dump(config_data, f)
        
        # Env vars should replace arrays
        os.environ["CHUNKHOUND_INDEXING__EXCLUDE"] = "*.tmp,*.cache"
        
        # CLI args should replace entirely
        args = self.create_mock_args(
            config=str(self.config_file),
            include=["*.ts", "*.tsx"]
        )
        
        config = self.create_isolated_config(args=args)
        
        # CLI args replace config file
        assert config.indexing.include == ["*.ts", "*.tsx"]
        # Env var replaces config file
        assert config.indexing.exclude == ["*.tmp", "*.cache"]


class TestConfigErrorHandling(ConfigTestBase):
    """Test configuration error handling."""
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_config()
    
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
        os.environ["CHUNKHOUND_MCP__PORT"] = "not-a-number"
        
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
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        
    def teardown_method(self):
        """Clean up."""
        reset_config()
    
    def test_validate_for_command(self):
        """Test command-specific validation."""
        # Create config missing embedding info
        config = self.create_isolated_config()
        
        # Index command requires embedding
        errors = config.validate_for_command("index")
        assert len(errors) > 0
        assert any("embedding" in err.lower() for err in errors)
        
        # Search command still needs embedding for semantic search
        # but it's less critical than index
        errors = config.validate_for_command("search")
        # May have warnings but should work
        assert isinstance(errors, list)
    
    def test_get_missing_config(self):
        """Test identification of missing config."""
        config = self.create_isolated_config()
        
        missing = config.get_missing_config()
        # Should identify missing embedding config
        assert any("embedding" in item for item in missing)
        
        # Add embedding config
        config.embedding = EmbeddingConfig(provider="openai", api_key="test-key")
        missing = config.get_missing_config()
        # Should be empty now
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
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        reset_config()
    
    def test_legacy_env_var_names(self):
        """Test that legacy environment variable names still work."""
        # Set legacy env vars
        os.environ["CHUNKHOUND_DB_PATH"] = "/legacy/db/path"
        
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
    
    def setup_method(self):
        """Setup test environment."""
        reset_config()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_config()
    
    def test_mcp_server_config_consistency(self):
        """Ensure MCP servers always use consistent config."""
        # Both servers should use same pattern
        stdio_args = self.create_mock_args(command="mcp", subcommand="stdio")
        http_args = self.create_mock_args(command="mcp", subcommand="http", port=5173, http=True)
        
        # Set same env
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "mcp.db")
        
        stdio_config = self.create_isolated_config(args=stdio_args)
        http_config = self.create_isolated_config(args=http_args)
        
        # Should have same database path
        assert stdio_config.database.path == http_config.database.path
        
        # Transport should differ based on args
        assert stdio_config.mcp.transport == "stdio"
        assert http_config.mcp.transport == "http"
    
    def test_cli_command_always_respects_local_config(self):
        """Ensure CLI commands always check for local .chunkhound.json."""
        # Create local config
        local_config = self.temp_dir / ".chunkhound.json"
        with open(local_config, "w") as f:
            json.dump({"database": {"provider": "lancedb"}}, f)
        
        # Simulate different CLI commands
        for command in ["index", "search", "run"]:
            args = self.create_mock_args(
                command=command,
                path=str(self.temp_dir)
            )
            
            config = self.create_isolated_config(args=args, mock_project_root=self.temp_dir)
            
            # Should always load local config
            assert config.database.provider == "lancedb", f"{command} didn't load local config"
    
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
        with open(env_config, "w") as f:
            json.dump({"debug": True}, f)
        
        os.environ["CHUNKHOUND_CONFIG_FILE"] = str(env_config)
        
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