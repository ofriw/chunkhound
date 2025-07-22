"""Unit tests for DatabaseConfig class."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from chunkhound.core.config.database_config import DatabaseConfig


class TestDatabaseConfig:
    """Test DatabaseConfig class functionality."""
    
    def test_default_values(self):
        """Test DatabaseConfig has correct defaults."""
        config = DatabaseConfig()
        assert config.provider == "duckdb"
        assert config.path is None
        assert config.lancedb_index_type == "IVF_PQ"
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.cache_size == 1000
        assert config.timeout == 30
        
    def test_provider_validation(self):
        """Test provider must be duckdb or lancedb."""
        # Valid providers
        config1 = DatabaseConfig(provider="duckdb")
        assert config1.provider == "duckdb"
        
        config2 = DatabaseConfig(provider="lancedb")
        assert config2.provider == "lancedb"
        
        # Invalid provider
        with pytest.raises(ValidationError) as exc_info:
            DatabaseConfig(provider="sqlite")
        # The error message is from pydantic's literal validation
        assert "provider" in str(exc_info.value) or "literal_error" in str(exc_info.value)
            
    def test_get_db_path_with_explicit_path(self):
        """Test get_db_path returns correct path based on provider."""
        # DuckDB path
        config = DatabaseConfig(provider="duckdb", path="/tmp/test")
        assert config.get_db_path() == Path("/tmp/test/chunks.db")
        
        # LanceDB path
        config = DatabaseConfig(provider="lancedb", path="/tmp/test")
        assert config.get_db_path() == Path("/tmp/test/lancedb")
        
    def test_get_db_path_no_path_configured(self):
        """Test get_db_path raises error when no path configured."""
        config = DatabaseConfig()
        with pytest.raises(ValueError, match="Database path not configured"):
            config.get_db_path()
        
    def test_is_configured(self):
        """Test is_configured logic for various scenarios."""
        # Not configured - no path
        config = DatabaseConfig()
        assert not config.is_configured()
        
        # Configured - has path
        config = DatabaseConfig(path="/tmp/test.db")
        assert config.is_configured()
        
    def test_path_types(self):
        """Test path can be string or Path object."""
        # String path
        config1 = DatabaseConfig(path="/tmp/string/path")
        assert isinstance(config1.path, Path)
        assert str(config1.path) == "/tmp/string/path"
        
        # Path object
        path_obj = Path("/tmp/path/object")
        config2 = DatabaseConfig(path=path_obj)
        assert config2.path == path_obj
        
    def test_lancedb_index_type_validation(self):
        """Test LanceDB index type validation."""
        # Valid index types
        for index_type in ["IVF_PQ", "IVF_HNSW_SQ"]:
            config = DatabaseConfig(lancedb_index_type=index_type)
            assert config.lancedb_index_type == index_type
            
        # Invalid index type should fail validation
        with pytest.raises(ValidationError):
            DatabaseConfig(lancedb_index_type="INVALID_TYPE")
            
    def test_pool_settings_validation(self):
        """Test pool settings have valid constraints."""
        # Valid pool settings
        config = DatabaseConfig(
            pool_size=10,
            max_overflow=20,
            cache_size=500,
            timeout=60
        )
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.cache_size == 500
        assert config.timeout == 60
        
        # Invalid pool size (too small)
        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=0)
            
        # Invalid pool size (too large)
        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=100)
            
        # Invalid timeout (too small)
        with pytest.raises(ValidationError):
            DatabaseConfig(timeout=0)
            
        # Invalid timeout (too large)
        with pytest.raises(ValidationError):
            DatabaseConfig(timeout=400)
            
    def test_config_dict_serialization(self):
        """Test DatabaseConfig can be serialized to dict."""
        config = DatabaseConfig(
            provider="lancedb",
            path="/tmp/test",
            lancedb_index_type="IVF_HNSW_SQ",
            pool_size=10
        )
        
        config_dict = config.model_dump()
        assert config_dict["provider"] == "lancedb"
        assert str(config_dict["path"]) == "/tmp/test"
        assert config_dict["lancedb_index_type"] == "IVF_HNSW_SQ"
        assert config_dict["pool_size"] == 10
        
    def test_config_json_serialization(self):
        """Test DatabaseConfig can be serialized to JSON."""
        config = DatabaseConfig(
            provider="duckdb",
            path="/tmp/test.db",
            pool_size=15
        )
        
        json_str = config.model_dump_json()
        assert '"provider":"duckdb"' in json_str
        assert '"pool_size":15' in json_str
        assert '"/tmp/test.db"' in json_str
        
    def test_repr(self):
        """Test string representation of config."""
        config = DatabaseConfig(
            provider="lancedb",
            path="/tmp/db",
            pool_size=8
        )
        
        repr_str = repr(config)
        assert "DatabaseConfig" in repr_str
        assert "provider=lancedb" in repr_str
        assert "path=/tmp/db" in repr_str
        assert "pool_size=8" in repr_str
        
    def test_different_providers_different_paths(self):
        """Test different providers create different database paths."""
        base_path = "/tmp/testdb"
        
        duckdb_config = DatabaseConfig(provider="duckdb", path=base_path)
        lancedb_config = DatabaseConfig(provider="lancedb", path=base_path)
        
        duckdb_path = duckdb_config.get_db_path()
        lancedb_path = lancedb_config.get_db_path()
        
        # Paths should be different
        assert duckdb_path != lancedb_path
        assert duckdb_path.name == "chunks.db"
        assert lancedb_path.name == "lancedb"