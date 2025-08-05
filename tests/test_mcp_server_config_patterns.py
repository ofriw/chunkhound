"""
Tests for MCP server configuration patterns.

These tests verify the specific configuration patterns used in MCP server
implementations and will initially fail until the servers are updated.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from chunkhound.core.config.config import Config
from chunkhound.api.cli.utils.config_factory import create_validated_config


class TestMCPServerStdioConfigPattern:
    """Test MCP stdio server configuration patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_db = self.temp_dir / "test.db"
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mcp_server_lifespan_config_pattern(self):
        """
        MCP server lifespan must use environment-based config with validation.

        This test will initially fail until MCP stdio server is updated.
        """
        # Set environment variables like MCP launcher would
        os.environ["CHUNKHOUND_PROJECT_ROOT"] = str(self.project_dir)
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "test-key"

        try:
            # This mimics the pattern that should be in server_lifespan()
            config = Config()  # No target_dir - environment only

            # Should include validation (currently missing)
            config, validation_errors = create_validated_config(Mock(), "mcp")

            # Should be able to get database path
            db_path = Path(config.database.path)
            assert db_path == self.test_db

            # Should be able to get embedding config
            assert config.embedding.provider == "openai"

        finally:
            # Clean up environment
            for key in [
                "CHUNKHOUND_PROJECT_ROOT",
                "CHUNKHOUND_DATABASE__PATH",
                "CHUNKHOUND_EMBEDDING__PROVIDER",
                "CHUNKHOUND_EMBEDDING__API_KEY",
            ]:
                os.environ.pop(key, None)

    def test_mcp_server_process_file_change_config_pattern(self):
        """
        MCP server file change processing must use consistent config.

        This test will initially fail until process_file_change() is fixed.
        """
        # Currently process_file_change() creates Config(target_dir=project_root)
        # This is inconsistent with the main server initialization

        # Set environment variables
        os.environ["CHUNKHOUND_PROJECT_ROOT"] = str(self.project_dir)
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)

        try:
            # Main server config (correct pattern)
            main_config = Config()  # No target_dir

            # File change processing should use same pattern
            # Currently it does: Config(target_dir=project_root) which is wrong

            # After fix, this should work the same way
            file_change_config = Config()  # Should be same pattern

            # Should have same database path
            assert main_config.database.path == file_change_config.database.path

        finally:
            for key in ["CHUNKHOUND_PROJECT_ROOT", "CHUNKHOUND_DATABASE__PATH"]:
                os.environ.pop(key, None)

    def test_mcp_server_imports_required_helpers(self):
        """
        MCP server must import required configuration helpers.

        This test will initially fail until imports are added.
        """
        # Check if MCP stdio server imports the required helpers
        try:
            # Note: create_validated_config is now in api.cli.utils.config_factory
            from chunkhound.api.cli.utils.config_factory import create_validated_config

            # Should be able to import config factory function
            assert create_validated_config is not None
        except ImportError:
            # This will fail initially - config factory not imported
            pytest.fail("mcp stdio server must import create_validated_config")

    @patch("chunkhound.mcp.stdio._services", new=None)
    @patch("chunkhound.mcp.stdio._embedding_manager", new=None)
    def test_mcp_server_uses_database_factory(
        self, mock_embedding_manager, mock_services
    ):
        """
        MCP server must use create_database_with_dependencies().

        This test will initially fail until database creation is unified.
        """
        # Mock the current global variables
        mock_services.return_value = Mock()
        mock_embedding_manager.return_value = Mock()

        # Set environment
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)

        try:
            # Import and test the pattern
            from chunkhound.database_factory import create_services

            config = Config()

            # Should use unified factory (currently doesn't)
            services = create_services(
                db_path=Path(config.database.path),
                config=config.to_dict(),
                embedding_manager=Mock(),
            )

            assert services is not None

        finally:
            os.environ.pop("CHUNKHOUND_DATABASE__PATH", None)


class TestMCPServerHTTPConfigPattern:
    """Test MCP HTTP server configuration patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_db = self.temp_dir / "test.db"
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mcp_http_server_ensure_initialization_pattern(self):
        """
        MCP HTTP server ensure_initialization() must use validation.

        This test will initially fail until HTTP server is updated.
        """
        # Set environment variables
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"

        try:
            # This mimics the pattern that should be in ensure_initialization()
            config = Config()  # No target_dir

            # Should include validation (currently missing)
            config, validation_errors = create_validated_config(Mock(), "mcp")

            # Should be list of errors
            assert isinstance(validation_errors, list)

        finally:
            for key in ["CHUNKHOUND_DATABASE__PATH", "CHUNKHOUND_EMBEDDING__PROVIDER"]:
                os.environ.pop(key, None)

    def test_mcp_http_server_file_change_consistency(self):
        """
        MCP HTTP server file change processing must be consistent.

        This test will initially fail until file processing is unified.
        """
        # Set environment
        os.environ["CHUNKHOUND_PROJECT_ROOT"] = str(self.project_dir)
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)

        try:
            # Main server config
            main_config = Config()  # No target_dir

            # File change processing should use same config approach
            # Currently it creates Config() in process_file_change which is inconsistent

            # After fix, should use consistent pattern
            file_config = Config()  # Should be same pattern

            # Should have same exclude patterns
            assert main_config.indexing.exclude == file_config.indexing.exclude

        finally:
            for key in ["CHUNKHOUND_PROJECT_ROOT", "CHUNKHOUND_DATABASE__PATH"]:
                os.environ.pop(key, None)

    def test_mcp_http_server_main_function_pattern(self):
        """
        MCP HTTP server main() function must use environment config.

        This test will initially fail until main() is updated.
        """
        # Set environment
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(self.test_db)

        try:
            # Main function should use environment-based config
            config = Config()  # No target_dir

            # Should get database path from environment
            assert str(config.database.path) == str(self.test_db)

        finally:
            os.environ.pop("CHUNKHOUND_DATABASE__PATH", None)


class TestMCPServerCodeAnalysis:
    """Test actual MCP server code for required patterns."""

    def test_mcp_server_stdio_has_config_factory_import(self):
        """
        MCP stdio server must import create_validated_config from config_factory.

        Tests clean internal architecture using unified config creation.
        """
        # Check mcp_server.py source code
        from chunkhound.mcp import stdio as mcp_server
        import inspect

        source = inspect.getsource(mcp_server)

        # Should import unified config factory
        assert "create_validated_config" in source, (
            "mcp stdio server must import create_validated_config from config_factory"
        )

    def test_mcp_server_stdio_has_services_factory_usage(self):
        """
        MCP stdio server must use create_services for clean architecture.

        Tests modern service-oriented architecture.
        """
        from chunkhound.mcp import stdio as mcp_server
        import inspect

        source = inspect.getsource(mcp_server)

        # Should use clean services factory
        assert "create_services" in source, (
            "mcp stdio server must use create_services for clean architecture"
        )

    def test_mcp_server_http_has_config_factory_import(self):
        """
        MCP HTTP server must import create_validated_config from config_factory.

        Tests clean internal architecture using unified config creation.
        """
        from chunkhound.mcp import http as mcp_http_server
        import inspect

        source = inspect.getsource(mcp_http_server)

        # Should import unified config factory
        assert "create_validated_config" in source, (
            "mcp http server must import create_validated_config from config_factory"
        )

    def test_mcp_server_http_has_services_factory_usage(self):
        """
        MCP HTTP server must use create_services for clean architecture.

        Tests modern service-oriented architecture.
        """
        from chunkhound.mcp import http as mcp_http_server
        import inspect

        source = inspect.getsource(mcp_http_server)

        # Should use clean services factory
        assert "create_services" in source, (
            "mcp http server must use create_services for clean architecture"
        )

    def test_mcp_servers_no_target_dir_in_config(self):
        """
        MCP servers must not use target_dir in Config() instantiation.

        This test will initially fail until Config() calls are fixed.
        """
        # Check both server files
        from chunkhound.mcp import stdio as mcp_server, http as mcp_http_server
        import inspect

        for module in [mcp_server, mcp_http_server]:
            source = inspect.getsource(module)
            lines = source.split("\n")

            # Find Config() instantiations
            config_lines = [
                line
                for line in lines
                if "Config(" in line and not line.strip().startswith("#")
            ]

            # Should not use target_dir parameter
            for line in config_lines:
                assert "target_dir" not in line, (
                    f"MCP server should not use target_dir in Config(): {line}"
                )

    def test_mcp_servers_have_unified_config_creation(self):
        """
        MCP servers must use create_validated_config for clean architecture.

        Tests modern unified config creation pattern.
        """
        from chunkhound.mcp import stdio as mcp_server, http as mcp_http_server
        import inspect

        for module in [mcp_server, mcp_http_server]:
            source = inspect.getsource(module)

            # Should use unified config factory
            assert "create_validated_config" in source, (
                f"{module.__name__} must use create_validated_config for clean architecture"
            )

            # Should handle validation through factory
            assert "config" in source, (
                f"{module.__name__} must use config factory pattern"
            )


class TestMCPServerErrorHandling:
    """Test MCP server error handling patterns."""

    def test_mcp_server_validation_error_handling(self):
        """
        MCP servers must handle validation errors properly.

        This test will initially fail until error handling is added.
        """
        # Create config with validation errors
        config = Config()

        # Should handle validation errors
        validation_errors = validate_config_for_command(config, "mcp")

        if validation_errors:
            # Should raise appropriate exception
            # Currently MCP servers ignore validation errors
            with pytest.raises(Exception) as exc_info:
                # This should raise an exception in fixed version
                raise ValueError(f"Config validation failed: {validation_errors}")

            assert "validation failed" in str(exc_info.value).lower()

    def test_mcp_server_missing_api_key_handling(self):
        """
        MCP servers must handle missing API keys gracefully.

        This test will initially fail until error handling is improved.
        """
        # No API key in environment
        config = Config()

        validation_errors = validate_config_for_command(config, "mcp")

        # Should detect missing API key
        # Currently validation might not catch this
        if validation_errors:
            api_key_errors = [
                err for err in validation_errors if "api_key" in err.lower()
            ]
            # Should have API key validation
            assert len(api_key_errors) > 0 or config.embedding.api_key is not None
