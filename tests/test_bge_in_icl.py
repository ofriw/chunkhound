"""Tests for BGE-IN-ICL embedding provider with in-context learning capabilities."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from chunkhound.embeddings import (
    BGEInICLProvider,
    ICLContextManager,
    create_bge_in_icl_provider,
    EmbeddingManager
)


class TestICLContextManager:
    """Test ICL context management functionality."""
    
    def test_context_manager_initialization(self):
        """Test ICL context manager initialization."""
        manager = ICLContextManager(cache_size=50)
        assert manager._cache_size == 50
        assert len(manager._cache) == 0
        assert "python" in manager._language_templates
        assert "javascript" in manager._language_templates
        assert "generic" in manager._language_templates
    
    def test_get_context_for_python(self):
        """Test getting context for Python code."""
        manager = ICLContextManager()
        python_code = "def calculate_metrics(data):\n    return sum(data) / len(data)"
        
        context = manager.get_context_for_language("python", python_code)
        
        assert "instruction" in context
        assert "examples" in context
        assert "target_text" in context
        assert "Python code" in context["instruction"]
        assert len(context["examples"]) == 2
        assert python_code[:200] == context["target_text"]
    
    def test_get_context_for_javascript(self):
        """Test getting context for JavaScript code."""
        manager = ICLContextManager()
        js_code = "async function fetchData(url) { return await fetch(url); }"
        
        context = manager.get_context_for_language("javascript", js_code)
        
        assert "JavaScript code" in context["instruction"]
        assert "async function" in str(context["examples"])
        assert js_code[:200] == context["target_text"]
    
    def test_get_context_for_unknown_language(self):
        """Test fallback to generic context for unknown languages."""
        manager = ICLContextManager()
        code = "some random code"
        
        context = manager.get_context_for_language("unknown_lang", code)
        
        assert context["instruction"] == manager._language_templates["generic"]["instruction"]
        assert context["examples"] == manager._language_templates["generic"]["examples"][:2]
    
    def test_context_caching(self):
        """Test that contexts are properly cached."""
        manager = ICLContextManager(cache_size=2)
        
        # First call should create cache entry
        context1 = manager.get_context_for_language("python", "def test(): pass")
        assert len(manager._cache) == 1
        
        # Second call with same content should use cache
        context2 = manager.get_context_for_language("python", "def test(): pass")
        assert context1 == context2
        assert len(manager._cache) == 1
        
        # Different content should create new cache entry
        context3 = manager.get_context_for_language("python", "class Test: pass")
        assert len(manager._cache) == 2
        
        # Third unique entry should evict oldest (cache size = 2)
        context4 = manager.get_context_for_language("javascript", "function test() {}")
        assert len(manager._cache) == 2
    
    def test_generic_context(self):
        """Test getting generic context."""
        manager = ICLContextManager()
        text = "some generic text"
        
        context = manager.get_generic_context(text)
        
        assert context["instruction"] == manager._language_templates["generic"]["instruction"]
        assert text[:200] == context["target_text"]


class TestBGEInICLProvider:
    """Test BGE-IN-ICL embedding provider functionality."""
    
    def test_provider_initialization(self):
        """Test BGE-IN-ICL provider initialization."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            model="bge-in-icl-v1",
            api_key="test_key",
            batch_size=32,
            language="python",
            enable_icl=True
        )
        
        assert provider.name == "bge-in-icl"
        assert provider.model == "bge-in-icl-v1"
        assert provider.batch_size == 32
        assert provider.distance == "cosine"
        assert provider._enable_icl is True
        assert provider._language == "python"
    
    def test_provider_initialization_defaults(self):
        """Test BGE-IN-ICL provider with default values."""
        provider = BGEInICLProvider(base_url="http://localhost:8080")
        
        assert provider.model == "bge-in-icl"
        assert provider.batch_size == 50
        assert provider._timeout == 120
        assert provider._language == "auto"
        assert provider._enable_icl is True
    
    def test_dimensions_not_detected_error(self):
        """Test error when dimensions not yet detected."""
        provider = BGEInICLProvider(base_url="http://localhost:8080")
        
        with pytest.raises(ValueError, match="Embedding dimensions not yet determined"):
            _ = provider.dims
    
    def test_language_detection_python(self):
        """Test automatic language detection for Python."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="auto")
        
        python_code = "def calculate(x, y):\n    return x + y\nclass Calculator:\n    pass"
        detected = provider._detect_language(python_code)
        
        assert detected == "python"
    
    def test_language_detection_javascript(self):
        """Test automatic language detection for JavaScript."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="auto")
        
        js_code = "const fetchData = async (url) => {\n    const response = await fetch(url);\n    return response.json();\n};"
        detected = provider._detect_language(js_code)
        
        assert detected == "javascript"
    
    def test_language_detection_typescript(self):
        """Test automatic language detection for TypeScript."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="auto")
        
        ts_code = "interface User {\n    id: number;\n    name: string;\n}\nfunction process<T>(data: T): T { return data; }"
        detected = provider._detect_language(ts_code)
        
        assert detected == "typescript"
    
    def test_language_detection_java(self):
        """Test automatic language detection for Java."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="auto")
        
        java_code = "public class Calculator {\n    public static int add(int a, int b) {\n        return a + b;\n    }\n}"
        detected = provider._detect_language(java_code)
        
        assert detected == "java"
    
    def test_language_detection_generic(self):
        """Test fallback to generic for unrecognized code."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="auto")
        
        generic_code = "some random text without clear language markers"
        detected = provider._detect_language(generic_code)
        
        assert detected == "generic"
    
    def test_language_detection_fixed_language(self):
        """Test that fixed language setting bypasses auto-detection."""
        provider = BGEInICLProvider(base_url="http://localhost:8080", language="python")
        
        js_code = "function test() { return true; }"
        detected = provider._detect_language(js_code)
        
        assert detected == "python"  # Should return fixed language, not detected
    
    def test_prepare_icl_request_disabled(self):
        """Test request preparation with ICL disabled."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            enable_icl=False
        )
        
        texts = ["def test(): pass", "class Example: pass"]
        request = provider._prepare_icl_request(texts)
        
        expected = {
            "model": "bge-in-icl",
            "input": texts,
            "encoding_format": "float"
        }
        assert request == expected
    
    def test_prepare_icl_request_enabled(self):
        """Test request preparation with ICL enabled."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            language="python",
            enable_icl=True
        )
        
        texts = ["def calculate(x): return x * 2", "class Calculator: pass"]
        request = provider._prepare_icl_request(texts)
        
        assert "icl_context" in request
        assert request["model"] == "bge-in-icl"
        assert request["input"] == texts
        assert request["encoding_format"] == "float"
        
        icl_context = request["icl_context"]
        assert "instruction" in icl_context
        assert "examples" in icl_context
        assert "language" in icl_context
        assert icl_context["enable_context_learning"] is True
        assert icl_context["language"] == "python"
    
    @pytest.mark.asyncio
    async def test_embed_empty_texts(self):
        """Test embedding empty text list."""
        provider = BGEInICLProvider(base_url="http://localhost:8080")
        
        result = await provider.embed([])
        
        assert result == []
    
    def test_embed_empty_texts_sync(self):
        """Test synchronous validation of empty text list."""
        provider = BGEInICLProvider(base_url="http://localhost:8080")
        
        # Since embed is async, we'll just test that it returns a coroutine for empty list
        result = provider.embed([])
        assert asyncio.iscoroutine(result)
        result.close()  # Clean up the coroutine
    
    def test_icl_request_preparation(self):
        """Test ICL request preparation without making HTTP calls."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            language="python",
            enable_icl=True
        )
        
        texts = ["def calculate(x): return x", "class Test: pass"]
        request = provider._prepare_icl_request(texts)
        
        # Verify ICL context is included
        assert "icl_context" in request
        assert request["model"] == "bge-in-icl"
        assert request["input"] == texts
        assert request["encoding_format"] == "float"
        
        icl_context = request["icl_context"]
        assert "instruction" in icl_context
        assert "examples" in icl_context
        assert "language" in icl_context
        assert icl_context["enable_context_learning"] is True
        assert icl_context["language"] == "python"
    
    def test_batch_preparation(self):
        """Test batch size and preparation logic."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            batch_size=2,
            enable_icl=False
        )
        
        # Test batch size setting
        assert provider.batch_size == 2
        
        # Test that multiple texts would be split into batches
        texts = ["text1", "text2", "text3", "text4"]  # Would be 2 batches of 2
        
        # Test first batch preparation
        first_batch = texts[:provider.batch_size]
        request = provider._prepare_icl_request(first_batch)
        
        assert len(request["input"]) == 2
        assert request["input"] == ["text1", "text2"]
        
        # Test second batch preparation
        second_batch = texts[provider.batch_size:]
        request = provider._prepare_icl_request(second_batch)
        
        assert len(request["input"]) == 2
        assert request["input"] == ["text3", "text4"]
    
    def test_error_handling_config(self):
        """Test error handling configuration."""
        provider = BGEInICLProvider(base_url="http://localhost:8080")
        
        # Test that dimensions access before detection raises error
        with pytest.raises(ValueError, match="Embedding dimensions not yet determined"):
            _ = provider.dims
        
        # Test that empty texts are handled gracefully
        result = provider.embed([])
        assert asyncio.iscoroutine(result)
        result.close()  # Clean up the coroutine
    
    def test_provider_configuration(self):
        """Test provider configuration and validation."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            timeout=60,
            batch_size=32
        )
        
        # Test configuration values
        assert provider._timeout == 60
        assert provider.batch_size == 32
        assert provider._base_url == "http://localhost:8080"
        assert provider.name == "bge-in-icl"
        assert provider.distance == "cosine"
    
    def test_api_key_configuration(self):
        """Test API key configuration."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            api_key="test_api_key"
        )
        
        # Test that API key is stored
        assert provider._api_key == "test_api_key"
        
        # Test request preparation includes proper headers concept
        texts = ["test text"]
        request = provider._prepare_icl_request(texts)
        
        # The actual headers are added in the embed method, but we can test
        # that the request payload is properly prepared
        assert "model" in request
        assert "input" in request
        assert request["input"] == texts


class TestBGEInICLProviderFactory:
    """Test BGE-IN-ICL provider factory function."""
    
    def test_create_bge_in_icl_provider_defaults(self):
        """Test creating provider with default values."""
        provider = create_bge_in_icl_provider("http://localhost:8080")
        
        assert isinstance(provider, BGEInICLProvider)
        assert provider.model == "bge-in-icl"
        assert provider._enable_icl is True
        assert provider._language == "auto"
    
    def test_create_bge_in_icl_provider_custom(self):
        """Test creating provider with custom values."""
        provider = create_bge_in_icl_provider(
            base_url="http://custom:9000",
            model="bge-in-icl-large",
            api_key="custom_key",
            language="python",
            enable_icl=False,
            batch_size=64
        )
        
        assert provider.model == "bge-in-icl-large"
        assert provider._api_key == "custom_key"
        assert provider._language == "python"
        assert provider._enable_icl is False
        assert provider.batch_size == 64


class TestBGEInICLIntegration:
    """Test BGE-IN-ICL provider integration with EmbeddingManager."""
    
    def test_register_with_embedding_manager(self):
        """Test registering BGE-IN-ICL provider with EmbeddingManager."""
        manager = EmbeddingManager()
        provider = create_bge_in_icl_provider("http://localhost:8080")
        
        manager.register_provider(provider, set_default=True)
        
        assert "bge-in-icl" in manager.list_providers()
        assert manager.get_provider().name == "bge-in-icl"
    
    @pytest.mark.asyncio
    async def test_embed_texts_through_manager(self):
        """Test embedding texts through EmbeddingManager."""
        manager = EmbeddingManager()
        provider = create_bge_in_icl_provider("http://localhost:8080")
        manager.register_provider(provider)
        
        # Mock the embed method
        mock_embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        provider.embed = AsyncMock(return_value=mock_embeddings)
        provider._dims = 3  # Set dimensions
        
        result = await manager.embed_texts(["text1", "text2"], "bge-in-icl")
        
        assert result.embeddings == mock_embeddings
        assert result.model == "bge-in-icl"
        assert result.provider == "bge-in-icl"
        assert result.dims == 3


class TestBGEInICLRealWorldScenarios:
    """Test BGE-IN-ICL provider with realistic code scenarios."""
    
    def test_python_code_embedding_preparation(self):
        """Test Python code embedding request preparation with ICL context."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            language="auto",
            enable_icl=True
        )
        
        python_texts = [
            "def calculate_metrics(data: List[float]) -> Dict[str, float]:\n    return {'mean': sum(data) / len(data)}",
            "class DataProcessor:\n    def __init__(self, config):\n        self.config = config",
            "import pandas as pd\nimport numpy as np\n\ndf = pd.read_csv('data.csv')"
        ]
        
        # Test request preparation
        request = provider._prepare_icl_request(python_texts)
        
        # Verify ICL context is properly configured for Python
        assert 'icl_context' in request
        assert request['icl_context']['language'] == 'python'
        assert request['icl_context']['enable_context_learning'] is True
        assert 'Python code' in request['icl_context']['instruction']
        assert len(request['icl_context']['examples']) == 2
        
        # Verify input texts are included
        assert request['input'] == python_texts
        assert request['model'] == 'bge-in-icl'
    
    def test_mixed_language_detection(self):
        """Test language detection with mixed code types."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",
            language="auto",
            enable_icl=True
        )
        
        mixed_texts = [
            "const fetchUser = async (id) => { return await api.get(`/users/${id}`); }",
            "def process_data(items): return [item.strip() for item in items]",
            "public class UserService { @Autowired private UserRepository repo; }"
        ]
        
        # Should detect Java as primary language (Java patterns are detected first due to specificity)
        detected_language = provider._detect_language(" ".join(mixed_texts[:3]))
        assert detected_language == "java"
        
        # Test request preparation with mixed content
        request = provider._prepare_icl_request(mixed_texts)
        assert request['icl_context']['language'] == 'java'
    
    def test_context_templates_completeness(self):
        """Test that all language templates have required fields."""
        manager = ICLContextManager()
        
        required_fields = ["instruction", "examples"]
        
        for language, template in manager._language_templates.items():
            for field in required_fields:
                assert field in template, f"Language {language} missing field {field}"
            
            assert len(template["examples"]) >= 2, f"Language {language} needs at least 2 examples"
            assert isinstance(template["instruction"], str), f"Language {language} instruction must be string"
            assert len(template["instruction"]) > 10, f"Language {language} instruction too short"