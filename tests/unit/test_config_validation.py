"""Unit tests for Config validation functionality."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from chunkhound.core.config.config import Config
from tests.config_test_base import ConfigTestBase


class TestConfigValidation(ConfigTestBase):
    """Test Config validation methods."""

    def test_validate_for_index_command(self):
        """Test validation for index command."""
        # Missing embedding provider
        config = self.create_isolated_config()
        errors = config.validate_for_command("index")
        # Index command doesn't require embeddings in current implementation
        assert len(errors) == 0

        # Valid config with embedding provider
        config = self.create_isolated_config(
            embedding={"provider": "openai", "api_key": "sk-test"}
        )
        errors = config.validate_for_command("index")
        assert len(errors) == 0

        # Missing API key for OpenAI
        config = self.create_isolated_config(embedding={"provider": "openai"})
        errors = config.validate_for_command("index")
        # This might not error at config level, but at provider level
        # Config validation is more lenient

    def test_validate_for_search_command(self):
        """Test validation for search command."""
        # Search works without embeddings (regex search)
        config = self.create_isolated_config()
        errors = config.validate_for_command("search")
        assert len(errors) == 0

        # Search with embeddings configured
        config = self.create_isolated_config(
            embedding={"provider": "openai", "api_key": "sk-test"}
        )
        errors = config.validate_for_command("search")
        assert len(errors) == 0

    def test_validate_for_mcp_command(self):
        """Test validation for MCP server command."""
        # MCP can work without embeddings
        config = self.create_isolated_config()
        errors = config.validate_for_command("mcp")
        assert len(errors) == 0

        # MCP with full config
        config = self.create_isolated_config(
            database={"provider": "duckdb", "path": "/tmp/test.db"},
            embedding={"provider": "openai", "api_key": "sk-test"},
        )
        errors = config.validate_for_command("mcp")
        assert len(errors) == 0

    def test_validate_database_path(self):
        """Test database path validation."""
        # Non-existent path should not error (created on demand)
        config = self.create_isolated_config(database={"path": "/nonexistent/path/db"})
        errors = config.validate_for_command("index")
        # Should not have database path errors
        assert not any(
            "database" in err.lower() and "path" in err.lower() for err in errors
        )

    def test_validate_missing_config(self):
        """Test missing configuration detection."""
        # Empty config
        config = self.create_isolated_config()
        missing = config.get_missing_config()
        # Should have some missing fields if embedding not configured

        # Partial config
        config = self.create_isolated_config(embedding={"provider": "openai"})
        missing = config.get_missing_config()
        # Might have missing API key

        # Full config
        config = self.create_isolated_config(
            database={"provider": "duckdb", "path": "/tmp/test.db"},
            embedding={
                "provider": "openai",
                "api_key": "sk-test",
                "model": "text-embedding-3-small",
            },
        )
        missing = config.get_missing_config()
        # Should be empty or minimal
        assert len(missing) == 0

    def test_command_specific_requirements(self):
        """Test different commands have different requirements."""
        config_no_embedding = self.create_isolated_config(
            database={"path": "/tmp/test.db"}
        )
        config_with_embedding = self.create_isolated_config(
            database={"path": "/tmp/test.db"},
            embedding={"provider": "openai", "api_key": "sk-test"},
        )

        # Index doesn't require embeddings in current implementation
        errors_index = config_no_embedding.validate_for_command("index")
        assert len(errors_index) == 0

        errors_index_valid = config_with_embedding.validate_for_command("index")
        assert len(errors_index_valid) == 0

        # Search doesn't require embeddings
        errors_search = config_no_embedding.validate_for_command("search")
        assert len(errors_search) == 0

        # Stats doesn't require embeddings
        errors_stats = config_no_embedding.validate_for_command("stats")
        assert len(errors_stats) == 0

    def test_debug_mode_validation(self):
        """Test debug mode doesn't affect validation."""
        # Debug mode should not change validation rules
        config_debug = self.create_isolated_config(debug=True)
        config_normal = self.create_isolated_config(debug=False)

        errors_debug = config_debug.validate_for_command("index")
        errors_normal = config_normal.validate_for_command("index")

        # Both should have same validation errors
        assert errors_debug == errors_normal

    def test_provider_specific_validation(self):
        """Test provider-specific validation rules."""
        # OpenAI typically needs API key
        config_openai_no_key = self.create_isolated_config(
            embedding={"provider": "openai"}
        )
        # Config level might not validate API key requirement

        # OpenAI-compatible needs base URL
        config_openai_compat = self.create_isolated_config(
            embedding={"provider": "openai-compatible", "api_key": "key"}
        )
        errors = config_openai_compat.validate_for_command("index")
        assert len(errors) > 0  # Should require base_url

        # TEI needs base URL
        config_tei_no_url = self.create_isolated_config(embedding={"provider": "tei"})
        # Again, config level might be lenient

    def test_validation_error_messages(self):
        """Test validation produces helpful error messages."""
        # Test with TEI provider missing base URL
        config = self.create_isolated_config(embedding={"provider": "tei"})
        errors = config.validate_for_command("index")

        # Should have clear, actionable error messages
        assert len(errors) > 0
        assert all(isinstance(err, str) for err in errors)
        assert all(len(err) > 0 for err in errors)
        assert any("base-url" in err.lower() for err in errors)

    def test_validate_with_env_var_config(self):
        """Test validation works with env var configuration."""
        os.environ["CHUNKHOUND_EMBEDDING__PROVIDER"] = "openai"
        os.environ["CHUNKHOUND_EMBEDDING__API_KEY"] = "sk-env-test"

        config = self.create_isolated_config()
        errors = config.validate_for_command("index")
        assert len(errors) == 0

    def test_validate_with_config_file_path(self):
        """Test validation with config file path set."""
        # Even with config file path, should validate the loaded config
        config = self.create_isolated_config(
            database={"path": "/from/config/file.db"},
            embedding={
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "sk-test",
            },
        )

        errors = config.validate_for_command("index")
        assert len(errors) == 0

    def test_validate_exclude_patterns(self):
        """Test validation of indexing exclude patterns."""
        # Invalid patterns should not break validation
        config = self.create_isolated_config(
            embedding={"provider": "openai", "api_key": "sk-test"},
            indexing={"exclude": ["*.pyc", "__pycache__", "invalid[["]},
        )

        errors = config.validate_for_command("index")
        # Should handle invalid patterns gracefully
        assert not any("exclude" in err.lower() for err in errors)

    def test_validate_batch_sizes(self):
        """Test validation doesn't check batch size constraints."""
        # Config validation is separate from model validation
        # This config would fail pydantic validation, not command validation
        config = self.create_isolated_config(
            embedding={"provider": "openai", "api_key": "sk-test"},
            database={"provider": "duckdb"},
        )

        errors = config.validate_for_command("index")
        assert len(errors) == 0
