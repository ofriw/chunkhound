"""Unit tests for EmbeddingConfig class."""

import pytest
from pydantic import ValidationError, SecretStr

from chunkhound.core.config.embedding_config import EmbeddingConfig


class TestEmbeddingConfig:
    """Test EmbeddingConfig class functionality."""

    def test_provider_required(self):
        """Test EmbeddingConfig requires provider to be set."""
        # Provider is required
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig()
        assert "provider" in str(exc_info.value).lower()

    def test_provider_validation(self):
        """Test provider must be from allowed list."""
        # Valid providers
        valid_providers = ["openai", "openai-compatible", "tei", "bge-in-icl"]
        for provider in valid_providers:
            config = EmbeddingConfig(provider=provider)
            assert config.provider == provider

        # Invalid provider
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(provider="invalid-provider")
        assert "provider" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for optional fields."""
        config = EmbeddingConfig(provider="openai")
        assert config.model is None  # Uses provider default
        assert config.api_key is None
        assert config.base_url is None
        assert config.batch_size == 50
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.max_concurrent_batches == 3

    def test_batch_size_validation(self):
        """Test batch_size validation and provider-specific limits."""
        # Valid batch size
        config = EmbeddingConfig(provider="openai", batch_size=100)
        assert config.batch_size == 100

        # batch_size is limited to 1000 by Field constraint
        config = EmbeddingConfig(provider="openai", batch_size=1000)
        assert config.batch_size == 1000

        # TEI has lower limit
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(provider="tei", batch_size=1000)
        assert "batch_size" in str(exc_info.value)

    def test_timeout_validation(self):
        """Test timeout must be within valid range."""
        # Valid timeouts
        config1 = EmbeddingConfig(provider="openai", timeout=60)
        assert config1.timeout == 60

        # Edge cases
        config2 = EmbeddingConfig(provider="openai", timeout=1)
        assert config2.timeout == 1

        config3 = EmbeddingConfig(provider="openai", timeout=300)
        assert config3.timeout == 300

        # Invalid timeouts
        with pytest.raises(ValidationError):
            EmbeddingConfig(provider="openai", timeout=0)

        with pytest.raises(ValidationError):
            EmbeddingConfig(provider="openai", timeout=400)

    def test_api_key_as_secret(self):
        """Test API key is handled as SecretStr."""
        config = EmbeddingConfig(provider="openai", api_key="sk-very-secret-key")

        # API key should be SecretStr
        assert isinstance(config.api_key, SecretStr)
        assert config.api_key.get_secret_value() == "sk-very-secret-key"

    def test_base_url_validation(self):
        """Test base_url validation and normalization."""
        # Valid URLs
        config1 = EmbeddingConfig(
            provider="openai-compatible", base_url="http://localhost:11434/"
        )
        # Trailing slash should be removed
        assert config1.base_url == "http://localhost:11434"

        # HTTPS URL
        config2 = EmbeddingConfig(
            provider="openai-compatible", base_url="https://api.example.com/v1"
        )
        assert config2.base_url == "https://api.example.com/v1"

        # Invalid URL (no protocol)
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(provider="openai-compatible", base_url="localhost:11434")
        assert "must start with http://" in str(exc_info.value)

    def test_openai_model_validation(self):
        """Test OpenAI model validation and typo correction."""
        # Valid OpenAI models
        valid_models = [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]

        for model in valid_models:
            config = EmbeddingConfig(provider="openai", model=model)
            assert config.model == model

        # Common typo correction
        config = EmbeddingConfig(provider="openai", model="text-embedding-small")
        assert config.model == "text-embedding-3-small"

        # Unknown model is allowed (for custom/future models)
        config = EmbeddingConfig(provider="openai", model="custom-model")
        assert config.model == "custom-model"

    def test_bge_in_icl_provider(self):
        """Test BGE-IN-ICL provider configuration."""
        # BGE-IN-ICL is a valid provider
        config = EmbeddingConfig(provider="bge-in-icl")
        assert config.provider == "bge-in-icl"

        # Can configure with standard fields
        config = EmbeddingConfig(
            provider="bge-in-icl", model="BAAI/bge-en-icl", batch_size=50
        )
        assert config.model == "BAAI/bge-en-icl"
        assert config.batch_size == 50

    def test_config_dict_serialization(self):
        """Test EmbeddingConfig can be serialized to dict."""
        config = EmbeddingConfig(
            provider="tei",
            model="BAAI/bge-base-en-v1.5",
            base_url="http://localhost:8080",
            batch_size=200,
        )

        config_dict = config.model_dump()
        assert config_dict["provider"] == "tei"
        assert config_dict["model"] == "BAAI/bge-base-en-v1.5"
        assert config_dict["base_url"] == "http://localhost:8080"
        assert config_dict["batch_size"] == 200
        assert config_dict["timeout"] == 30  # default

    def test_config_json_serialization(self):
        """Test EmbeddingConfig can be serialized to JSON."""
        config = EmbeddingConfig(provider="openai", api_key="sk-test", batch_size=75)

        json_str = config.model_dump_json()
        assert '"provider":"openai"' in json_str
        # SecretStr should be serialized as string
        assert '"api_key":"**********"' in json_str or '"api_key":"sk-test"' in json_str
        assert '"batch_size":75' in json_str

    def test_env_prefix(self):
        """Test environment variable prefix configuration."""
        # This is configured via model_config
        assert EmbeddingConfig.model_config["env_prefix"] == "CHUNKHOUND_EMBEDDING_"
        assert EmbeddingConfig.model_config["env_nested_delimiter"] == "__"

    def test_max_concurrent_batches_validation(self):
        """Test max_concurrent_batches validation."""
        # Valid values
        config = EmbeddingConfig(provider="openai", max_concurrent_batches=10)
        assert config.max_concurrent_batches == 10

        # Edge cases
        config1 = EmbeddingConfig(provider="openai", max_concurrent_batches=1)
        assert config1.max_concurrent_batches == 1

        config2 = EmbeddingConfig(provider="openai", max_concurrent_batches=20)
        assert config2.max_concurrent_batches == 20

        # Invalid values
        with pytest.raises(ValidationError):
            EmbeddingConfig(provider="openai", max_concurrent_batches=0)

        with pytest.raises(ValidationError):
            EmbeddingConfig(provider="openai", max_concurrent_batches=50)
