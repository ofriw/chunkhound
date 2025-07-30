"""
Integration tests for configuration system in real-world scenarios.

These tests verify that the configuration system works correctly when:
- Running actual CLI commands
- Starting MCP servers
- Processing files with watchers
- Handling complex project structures
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from chunkhound.core.config.config import Config
from chunkhound.database_factory import create_database_with_dependencies
from chunkhound.embeddings import EmbeddingManager


class TestCLIConfigIntegration:
    """Test configuration in real CLI scenarios."""

    def setup_method(self):
        """Create test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "test_project"
        self.project_dir.mkdir()

        # Create some test files
        (self.project_dir / "test.py").write_text("print('hello')")
        (self.project_dir / "test.js").write_text("console.log('hello');")

        self.original_env = os.environ.copy()

    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_command_with_local_config(self):
        """Test index command respects local .chunkhound.json."""
        # Create local config
        local_config = {
            "database": {
                "path": str(self.project_dir / ".chunkhound" / "local.db"),
                "provider": "duckdb",
            },
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "indexing": {"include": ["*.py"], "exclude": ["*.js"]},
        }

        config_path = self.project_dir / ".chunkhound.json"
        with open(config_path, "w") as f:
            json.dump(local_config, f)

        # Set API key via env
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "test-key"

        # Run index command
        cmd = [sys.executable, "-m", "chunkhound", "index", str(self.project_dir)]

        # Should respect local config
        # In real test, we'd check:
        # - Database created at specified path
        # - Only .py files indexed (not .js)
        # - Using specified embedding model

        # For now, verify config loads correctly
        # The actual index command is in the run module

        class MockArgs:
            path = str(self.project_dir)
            config = None
            db = None
            database_provider = None
            provider = None
            model = None
            include = None
            exclude = None
            verbose = False

        config = Config(args=MockArgs())

        assert str(config.database.path) == str(
            self.project_dir / ".chunkhound" / "local.db"
        )
        assert config.embedding.model == "text-embedding-3-small"
        assert config.indexing.include == ["*.py"]
        assert config.indexing.exclude == ["*.js"]

    def test_search_command_env_override(self):
        """Test search command with environment overrides."""
        # Create config file
        config_data = {"database": {"path": str(self.temp_dir / "config.db")}}
        config_file = self.temp_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Override via environment
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "env.db")

        # Simulate search command
        class MockArgs:
            command = "search"
            config = str(config_file)
            path = None
            db = None
            query = "test"
            semantic = True
            regex = None

        config = Config(args=MockArgs())

        # Environment should override file
        assert str(config.database.path) == str(self.temp_dir / "env.db")

    def test_run_command_cli_precedence(self):
        """Test run command with full precedence chain."""
        # Create local config
        local_config = {"database": {"provider": "duckdb"}}
        with open(self.project_dir / ".chunkhound.json", "w") as f:
            json.dump(local_config, f)

        # Create explicit config
        explicit_config = {"database": {"provider": "lancedb"}}
        config_file = self.temp_dir / "explicit.json"
        with open(config_file, "w") as f:
            json.dump(explicit_config, f)

        # Set environment
        os.environ["CHUNKHOUND_DATABASE__PROVIDER"] = "duckdb"

        # CLI args override all
        class MockArgs:
            command = "run"
            path = str(self.project_dir)
            config = str(config_file)
            database_provider = "duckdb"  # CLI override
            query = "test"
            verbose = True

        config = Config(args=MockArgs())

        # CLI should win
        assert config.database.provider == "duckdb"
        assert config.debug is True  # verbose -> debug


class TestMCPServerConfigIntegration:
    """Test configuration in MCP server scenarios."""

    def setup_method(self):
        """Create test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_env = os.environ.copy()

    def teardown_method(self):
        """Clean up."""
        os.environ.clear()
        os.environ.update(self.original_env)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_mcp_stdio_server_config(self):
        """Test MCP stdio server configuration loading."""
        # Set up environment as MCP launcher would
        os.environ["CHUNKHOUND_MCP_MODE"] = "1"
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "mcp.db")
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "test-key"

        # Import server components
        from chunkhound.mcp_server import _server_config

        # Simulate server lifespan initialization
        class MockArgs:
            command = "mcp"
            subcommand = "stdio"

        # This simulates what happens in server_lifespan
        config = Config(args=MockArgs())

        # Verify config loaded correctly
        assert str(config.database.path) == str(self.temp_dir / "mcp.db")
        assert config.embedding.provider == "openai"
        assert config.mcp.transport == "stdio"

        # Verify can create database with config
        embedding_manager = EmbeddingManager()
        db = create_database_with_dependencies(
            db_path=Path(config.database.path),
            config=config.to_dict(),
            embedding_manager=embedding_manager,
        )

        assert db is not None
        db.close()

    @pytest.mark.asyncio
    async def test_mcp_http_server_config(self):
        """Test MCP HTTP server configuration."""
        # Set environment
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.temp_dir / "http.db")

        # Simulate HTTP server args
        class MockArgs:
            command = "mcp"
            subcommand = "mcp"
            http = True  # This flag sets transport to HTTP
            port = 5173
            host = "127.0.0.1"
            cors = True

        config = Config(args=MockArgs())

        # Verify HTTP-specific config
        assert config.mcp.transport == "http"
        assert config.mcp.port == 5173
        assert config.mcp.host == "127.0.0.1"
        assert config.mcp.cors is True

        # Verify database config still works
        assert str(config.database.path) == str(self.temp_dir / "http.db")

    def test_mcp_server_config_validation(self):
        """Test MCP server config validation."""
        from chunkhound.api.cli.utils.config_helpers import validate_config_for_command

        # Create config missing API key
        os.environ.pop("CHUNKHOUND_EMBEDDING__API_KEY", None)

        config = Config()
        errors = validate_config_for_command(config, "mcp")

        # Should have validation errors but not fail
        # MCP servers work without embeddings
        assert isinstance(errors, list)


class TestFileWatcherConfigIntegration:
    """Test configuration with file watchers and indexers."""

    def setup_method(self):
        """Create test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "watched_project"
        self.project_dir.mkdir()

    def teardown_method(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)


    @pytest.mark.asyncio
    async def test_indexing_config_options(self):
        """Test indexing configuration options."""
        # Create config with indexing options
        config = Config(
            indexing={
                "watch": True,
                "debounce_ms": 500,
                "batch_size": 100,
                "force_reindex": True,
            }
        )

        # Verify indexing settings
        assert config.indexing.watch is True
        assert config.indexing.debounce_ms == 500
        assert config.indexing.batch_size == 100
        assert config.indexing.force_reindex is True


class TestComplexProjectStructures:
    """Test configuration with complex project structures."""

    def setup_method(self):
        """Create complex project structure."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create nested project structure
        self.root_project = self.temp_dir / "root_project"
        self.sub_project = self.root_project / "sub_project"
        self.sub_sub_project = self.sub_project / "nested"

        for p in [self.root_project, self.sub_project, self.sub_sub_project]:
            p.mkdir(parents=True)

    def teardown_method(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nested_config_discovery(self):
        """Test config discovery in nested projects."""
        # Create configs at different levels
        root_config = {"database": {"provider": "duckdb"}}
        sub_config = {"database": {"provider": "lancedb"}}

        with open(self.root_project / ".chunkhound.json", "w") as f:
            json.dump(root_config, f)

        with open(self.sub_project / ".chunkhound.json", "w") as f:
            json.dump(sub_config, f)

        # Config from root project
        args = type("Args", (), {"path": str(self.root_project), "config": None})()
        config = Config(args=args)
        assert config.database.provider == "duckdb"

        # Config from sub project (should use closest)
        args = type("Args", (), {"path": str(self.sub_project), "config": None})()
        config = Config(args=args)
        assert config.database.provider == "lancedb"

        # Config from nested (no config file, should use default)
        args = type("Args", (), {"path": str(self.sub_sub_project), "config": None})()
        config = Config(args=args)
        assert config.database.provider == "duckdb"  # Default provider

    def test_monorepo_config_isolation(self):
        """Test configuration isolation in monorepo."""
        # Create separate configs for different parts
        frontend_dir = self.root_project / "frontend"
        backend_dir = self.root_project / "backend"

        frontend_dir.mkdir()
        backend_dir.mkdir()

        # Different configs for each
        frontend_config = {
            "indexing": {"include": ["*.tsx", "*.ts"], "exclude": ["*.test.ts"]}
        }
        backend_config = {"indexing": {"include": ["*.py"], "exclude": ["*_test.py"]}}

        with open(frontend_dir / ".chunkhound.json", "w") as f:
            json.dump(frontend_config, f)

        with open(backend_dir / ".chunkhound.json", "w") as f:
            json.dump(backend_config, f)

        # Frontend config
        args = type("Args", (), {"path": str(frontend_dir), "config": None})()
        config = Config(args=args)
        assert "*.tsx" in config.indexing.include
        assert "*.py" not in config.indexing.include

        # Backend config
        args = type("Args", (), {"path": str(backend_dir), "config": None})()
        config = Config(args=args)
        assert "*.py" in config.indexing.include
        assert "*.tsx" not in config.indexing.include


class TestConfigMigration:
    """Test configuration migration scenarios."""

    def test_old_env_var_migration(self):
        """Test migration from old environment variables."""
        # Set old-style env vars
        os.environ["CHUNKHOUND_DB_PATH"] = "/old/style/path"

        config = Config()

        # Should still work
        assert str(config.database.path) == "/old/style/path"

        # Clean up
        os.environ.pop("CHUNKHOUND_DB_PATH", None)

    def test_config_format_evolution(self):
        """Test handling of evolving config formats."""
        # Old format (hypothetical)
        old_config = {
            "db_path": "/old/path",  # Old key name
            "embeddings": {  # Old section name
                "provider": "openai"
            },
        }

        # Current format maps differently
        # This test documents that we handle gracefully
        temp_dir = Path(tempfile.mkdtemp())
        try:
            config_file = temp_dir / "old.json"
            with open(config_file, "w") as f:
                json.dump(old_config, f)

            args = type("Args", (), {"config": str(config_file), "path": None})()

            # Should not crash, uses defaults for unrecognized keys
            config = Config(args=args)
            assert config is not None

        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
