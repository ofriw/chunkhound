"""Tests for BGE-IN-ICL Phase 3 Advanced Features: Dynamic Context Optimization."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from chunkhound.embeddings import BGEInICLProvider, ICLContextManager, PerformanceMetrics


class TestICLContextManagerAdvanced:
    """Test advanced ICL context management features."""
    
    def test_context_similarity_calculation(self):
        """Test context similarity scoring."""
        manager = ICLContextManager(similarity_threshold=0.7)
        
        # Test identical texts
        similarity = manager._calculate_context_similarity("hello world", "hello world")
        assert similarity == 1.0
        
        # Test similar texts
        similarity = manager._calculate_context_similarity(
            "function calculate(a, b) { return a + b; }",
            "function multiply(x, y) { return x * y; }"
        )
        assert 0.2 < similarity < 0.5  # Should be moderately similar
        
        # Test different texts
        similarity = manager._calculate_context_similarity(
            "class MyClass:",
            "SELECT * FROM users"
        )
        assert similarity < 0.3  # Should be dissimilar
        
        # Test empty texts
        similarity = manager._calculate_context_similarity("", "test")
        assert similarity == 0.0
    
    def test_best_example_selection(self):
        """Test selection of most relevant examples."""
        manager = ICLContextManager()
        
        examples = [
            "class Calculator:\n    def add(self, a, b):\n        return a + b",
            "function fetchData(url) {\n    return fetch(url).then(r => r.json());\n}",
            "def process_data(data):\n    return [item for item in data if item.valid]",
            "class DataProcessor:\n    def transform(self, input):\n        return input.upper()"
        ]
        
        target_text = "class UserService:\n    def get_user(self, id):\n        return self.db.find(id)"
        
        selected = manager._select_best_examples(examples, target_text, "python")
        
        # Should select the most similar Python class examples
        assert len(selected) == 2
        assert any("class Calculator" in example for example in selected)
        assert any("class DataProcessor" in example for example in selected)
    
    def test_cache_with_similarity_threshold(self):
        """Test caching with similarity threshold."""
        manager = ICLContextManager(cache_size=2, similarity_threshold=0.8)
        
        # First request - should create new context
        context1 = manager.get_context_for_language("python", "def test(): pass")
        assert context1["similarity_score"] == 1.0
        
        # Similar request - should use cache if similarity is high enough
        context2 = manager.get_context_for_language("python", "def test(): return")
        # This might use cache or create new depending on similarity
        
        # Very different request - should create new context
        context3 = manager.get_context_for_language("python", "class CompletelyDifferentClass:")
        assert "timestamp" in context3
    
    def test_lru_cache_eviction(self):
        """Test LRU cache eviction with quality scoring."""
        manager = ICLContextManager(cache_size=2)
        
        # Fill cache
        context1 = manager.get_context_for_language("python", "first")
        context2 = manager.get_context_for_language("javascript", "second")
        
        # Add third item - should evict oldest
        context3 = manager.get_context_for_language("java", "third")
        
        # Cache should have only 2 items
        assert len(manager._cache) == 2
        assert len(manager._context_scores) == 2


class TestBGEInICLProviderAdvanced:
    """Test advanced BGE-IN-ICL provider features."""
    
    @pytest.fixture
    def provider(self):
        """Create a BGE-IN-ICL provider for testing."""
        return BGEInICLProvider(
            base_url="http://test-server:8080",
            model="bge-in-icl-test",
            batch_size=20,
            adaptive_batching=True,
            min_batch_size=5,
            max_batch_size=50
        )
    
    def test_performance_metrics_initialization(self, provider):
        """Test performance metrics are properly initialized."""
        metrics = provider.get_performance_metrics()
        
        assert metrics["total_requests"] == 0
        assert metrics["total_texts"] == 0
        assert metrics["total_time"] == 0.0
        assert metrics["avg_texts_per_second"] == 0.0
        assert metrics["cache_hit_rate"] == 0.0
        assert metrics["current_batch_size"] == 20
        assert metrics["adaptive_batching_enabled"] is True
        assert metrics["recent_batch_sizes"] == []
    
    def test_adaptive_batch_sizing_increase(self, provider):
        """Test batch size increases when performance is good."""
        # First establish baseline with normal times
        for _ in range(3):
            provider._adapt_batch_size(1.0)
        
        # Then simulate consistently good performance (fast response times)
        for _ in range(5):
            provider._adapt_batch_size(0.3)  # Very fast response time
        
        # Batch size should increase
        assert provider.batch_size > 20
    
    def test_adaptive_batch_sizing_decrease(self, provider):
        """Test batch size decreases when performance is poor."""
        # First establish baseline with good times
        for _ in range(3):
            provider._adapt_batch_size(0.5)
        
        # Then simulate consistently poor performance
        for _ in range(5):
            provider._adapt_batch_size(4.0)  # Very slow response time
        
        # Batch size should decrease
        assert provider.batch_size < 20
    
    def test_adaptive_batch_sizing_limits(self, provider):
        """Test batch size respects min/max limits."""
        # Try to force batch size below minimum
        for _ in range(10):
            provider._adapt_batch_size(10.0)  # Very slow
        
        assert provider.batch_size >= provider._min_batch_size
        
        # Reset and try to force above maximum
        provider._batch_size = 20
        for _ in range(10):
            provider._adapt_batch_size(0.1)  # Very fast
        
        assert provider.batch_size <= provider._max_batch_size
    
    def test_adaptive_batching_disabled(self):
        """Test adaptive batching can be disabled."""
        provider = BGEInICLProvider(
            base_url="http://test-server:8080",
            adaptive_batching=False,
            batch_size=25
        )
        
        original_size = provider.batch_size
        
        # Simulate various response times - batch size shouldn't change
        for response_time in [0.1, 5.0, 0.2, 8.0]:
            provider._adapt_batch_size(response_time)
        
        assert provider.batch_size == original_size
    
    @pytest.mark.asyncio
    async def test_icl_request_preparation_with_context_scoring(self, provider):
        """Test ICL request preparation includes context quality metrics."""
        texts = [
            "def calculate_sum(numbers):\n    return sum(numbers)",
            "class Calculator:\n    def add(self, a, b):\n        return a + b"
        ]
        
        request = provider._prepare_icl_request(texts)
        
        assert "icl_context" in request
        icl_context = request["icl_context"]
        
        assert "instruction" in icl_context
        assert "examples" in icl_context
        assert "language" in icl_context
        assert "enable_context_learning" in icl_context
        assert "similarity_score" in icl_context
        assert "context_processing_time" in icl_context
        
        # Similarity score should be reasonable
        assert 0.0 <= icl_context["similarity_score"] <= 1.0
        
        # Context processing time should be recorded
        assert icl_context["context_processing_time"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_embed_with_performance_monitoring(self, provider):
        """Test embedding generation with performance monitoring."""
        texts = ["test text 1", "test text 2"]
        
        # Mock the HTTP response
        mock_response_data = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]}
            ],
            "icl_info": {
                "language": "python",
                "examples": ["example1", "example2"]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            
            # Create proper async context manager mock
            mock_post = MagicMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_instance = MagicMock()
            mock_session_instance.post = MagicMock(return_value=mock_post)
            
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Test embedding generation
            embeddings = await provider.embed(texts)
            
            # Verify embeddings
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]
            
            # Verify performance metrics were updated
            metrics = provider.get_performance_metrics()
            assert metrics["total_requests"] == 1
            assert metrics["total_texts"] == 2
            assert metrics["total_time"] > 0.0
            assert len(metrics["recent_batch_sizes"]) == 1
            assert metrics["recent_batch_sizes"][0] == 2
    
    def test_language_detection_priority(self, provider):
        """Test language detection prioritizes more specific patterns."""
        # TypeScript should be detected before JavaScript
        ts_text = "interface User { id: number; name: string; }"
        assert provider._detect_language(ts_text) == "typescript"
        
        # Java should be detected correctly
        java_text = "@Service\npublic class UserService { @Autowired private UserRepository repo; }"
        assert provider._detect_language(java_text) == "java"
        
        # C# should be detected correctly (need more C#-specific patterns)
        csharp_text = "using System; public class User { public int Id { get; set; } }"
        assert provider._detect_language(csharp_text) == "csharp"
        
        # Python should be detected
        python_text = "def calculate(self, data):\n    return sum(data)"
        assert provider._detect_language(python_text) == "python"
        
        # JavaScript (after TypeScript check)
        js_text = "const fetchData = async (url) => { return await fetch(url); }"
        assert provider._detect_language(js_text) == "javascript"
        
        # Generic fallback
        generic_text = "some random text without programming patterns"
        assert provider._detect_language(generic_text) == "generic"


class TestPerformanceMetrics:
    """Test performance metrics data class."""
    
    def test_performance_metrics_initialization(self):
        """Test metrics initialize correctly."""
        metrics = PerformanceMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.total_texts == 0
        assert metrics.total_time == 0.0
        assert metrics.avg_texts_per_second == 0.0
        assert metrics.cache_hit_rate == 0.0
        assert metrics.batch_sizes == []
        assert metrics.response_times == []
    
    def test_performance_metrics_calculations(self):
        """Test calculated properties work correctly."""
        metrics = PerformanceMetrics()
        
        # Set some test data
        metrics.total_texts = 100
        metrics.total_time = 10.0
        metrics.response_times = [1.0, 2.0, 3.0]
        metrics.context_hits = 8
        metrics.context_misses = 2
        
        assert metrics.avg_texts_per_second == 10.0
        assert metrics.avg_response_time == 2.0
        assert metrics.cache_hit_rate == 0.8
    
    def test_performance_metrics_edge_cases(self):
        """Test metrics handle edge cases properly."""
        metrics = PerformanceMetrics()
        
        # Zero division protection
        assert metrics.avg_texts_per_second == 0.0  # Uses max(time, 0.001)
        assert metrics.avg_response_time == 0.0     # Uses max(len, 1)
        assert metrics.cache_hit_rate == 0.0        # Uses max(total, 1)


@pytest.mark.integration
class TestBGEInICLIntegration:
    """Integration tests for BGE-IN-ICL advanced features."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_with_adaptive_batching(self):
        """Test end-to-end functionality with adaptive batching."""
        provider = BGEInICLProvider(
            base_url="http://localhost:8080",  # Would need real server for true integration
            adaptive_batching=True,
            min_batch_size=2,
            max_batch_size=10
        )
        
        # This would require a real BGE-IN-ICL server to test properly
        # For now, just verify the provider is configured correctly
        assert provider._adaptive_batching is True
        assert provider._min_batch_size == 2
        assert provider._max_batch_size == 10
        
        metrics = provider.get_performance_metrics()
        assert metrics["adaptive_batching_enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])