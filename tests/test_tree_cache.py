"""Unit tests for TreeCache class."""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from chunkhound.tree_cache import TreeCache, TreeCacheEntry, get_default_cache, configure_default_cache


class MockTree:
    """Mock tree-sitter tree for testing."""
    
    def __init__(self, content: str = "mock_tree"):
        self.content = content
        self.root_node = Mock()
    
    def __eq__(self, other):
        return isinstance(other, MockTree) and self.content == other.content
    
    def __repr__(self):
        return f"MockTree({self.content})"


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n    return 'world'\n")
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_dir():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        
        # Create test files
        (temp_path / "file1.py").write_text("print('file1')")
        (temp_path / "file2.py").write_text("print('file2')")
        (temp_path / "file3.py").write_text("print('file3')")
        
        yield temp_path


@pytest.fixture
def cache():
    """Create a TreeCache instance for testing."""
    return TreeCache(max_entries=5, max_memory_mb=1)


class TestTreeCacheEntry:
    """Test TreeCacheEntry class."""
    
    def test_cache_entry_creation(self, temp_file):
        """Test creating a cache entry."""
        tree = MockTree("test_tree")
        stat = temp_file.stat()
        
        entry = TreeCacheEntry(tree, temp_file, stat.st_mtime, stat.st_size)
        
        assert entry.tree == tree
        assert entry.file_path == temp_file
        assert entry.mtime == stat.st_mtime
        assert entry.size == stat.st_size
        assert entry.hit_count == 0
        assert isinstance(entry.access_time, float)
    
    def test_cache_entry_is_valid(self, temp_file):
        """Test cache entry validation."""
        tree = MockTree("test_tree")
        stat = temp_file.stat()
        
        entry = TreeCacheEntry(tree, temp_file, stat.st_mtime, stat.st_size)
        
        # Should be valid initially
        assert entry.is_valid() is True
        
        # Modify file to make entry invalid
        time.sleep(0.1)  # Ensure different mtime
        temp_file.write_text("modified content")
        
        assert entry.is_valid() is False
    
    def test_cache_entry_is_valid_missing_file(self):
        """Test cache entry validation with missing file."""
        tree = MockTree("test_tree")
        missing_file = Path("/nonexistent/file.py")
        
        entry = TreeCacheEntry(tree, missing_file, 12345.0, 100)
        
        assert entry.is_valid() is False
    
    def test_cache_entry_touch(self, temp_file):
        """Test updating access time and hit count."""
        tree = MockTree("test_tree")
        stat = temp_file.stat()
        
        entry = TreeCacheEntry(tree, temp_file, stat.st_mtime, stat.st_size)
        original_access_time = entry.access_time
        original_hit_count = entry.hit_count
        
        time.sleep(0.01)  # Small delay
        entry.touch()
        
        assert entry.access_time > original_access_time
        assert entry.hit_count == original_hit_count + 1


class TestTreeCache:
    """Test TreeCache class."""
    
    def test_cache_initialization(self):
        """Test cache initialization with custom parameters."""
        cache = TreeCache(max_entries=100, max_memory_mb=50)
        
        assert cache.max_entries == 100
        assert cache.max_memory_bytes == 50 * 1024 * 1024
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0
    
    def test_cache_put_and_get(self, cache, temp_file):
        """Test basic cache put and get operations."""
        tree = MockTree("test_tree")
        
        # Initially not cached
        result = cache.get(temp_file)
        assert result is None
        
        # Cache the tree
        cache.put(temp_file, tree)
        
        # Should now be cached
        result = cache.get(temp_file)
        assert result == tree
    
    def test_cache_miss_statistics(self, cache, temp_file):
        """Test cache miss statistics."""
        initial_misses = cache._misses
        
        # Cache miss
        result = cache.get(temp_file)
        assert result is None
        assert cache._misses == initial_misses + 1
    
    def test_cache_hit_statistics(self, cache, temp_file):
        """Test cache hit statistics."""
        tree = MockTree("test_tree")
        cache.put(temp_file, tree)
        
        initial_hits = cache._hits
        
        # Cache hit
        result = cache.get(temp_file)
        assert result == tree
        assert cache._hits == initial_hits + 1
    
    def test_cache_invalidation_on_file_change(self, cache, temp_file):
        """Test automatic cache invalidation when file changes."""
        tree = MockTree("test_tree")
        cache.put(temp_file, tree)
        
        # Verify cached
        result = cache.get(temp_file)
        assert result == tree
        
        # Modify file
        time.sleep(0.1)  # Ensure different mtime
        temp_file.write_text("modified content")
        
        # Should be invalidated
        result = cache.get(temp_file)
        assert result is None
        assert cache._invalidations == 1
    
    def test_manual_invalidation(self, cache, temp_file):
        """Test manual cache invalidation."""
        tree = MockTree("test_tree")
        cache.put(temp_file, tree)
        
        # Verify cached
        assert cache.get(temp_file) == tree
        
        # Manually invalidate
        result = cache.invalidate(temp_file)
        assert result is True
        
        # Should no longer be cached
        assert cache.get(temp_file) is None
        assert cache._invalidations == 1
    
    def test_invalidate_nonexistent_entry(self, cache):
        """Test invalidating non-existent cache entry."""
        nonexistent_file = Path("/nonexistent/file.py")
        
        result = cache.invalidate(nonexistent_file)
        assert result is False
        assert cache._invalidations == 0
    
    def test_lru_eviction_by_count(self, temp_dir):
        """Test LRU eviction when max_entries is exceeded."""
        cache = TreeCache(max_entries=2, max_memory_mb=100)
        
        files = list(temp_dir.glob("*.py"))[:3]  # Get 3 files
        trees = [MockTree(f"tree_{i}") for i in range(3)]
        
        # Cache first two files
        cache.put(files[0], trees[0])
        cache.put(files[1], trees[1])
        
        assert len(cache._cache) == 2
        assert cache.get(files[0]) == trees[0]
        assert cache.get(files[1]) == trees[1]
        
        # Cache third file - should evict first (LRU)
        cache.put(files[2], trees[2])
        
        assert len(cache._cache) == 2
        assert cache.get(files[0]) is None  # Evicted
        assert cache.get(files[1]) == trees[1]  # Still cached
        assert cache.get(files[2]) == trees[2]  # Newly cached
        assert cache._evictions == 1
    
    def test_lru_order_on_access(self, cache, temp_dir):
        """Test that accessing entries updates LRU order."""
        files = list(temp_dir.glob("*.py"))[:2]
        trees = [MockTree(f"tree_{i}") for i in range(3)]
        
        # Cache both files
        cache.put(files[0], trees[0])
        cache.put(files[1], trees[1])
        
        # Access first file to make it more recently used
        cache.get(files[0])
        
        # Add third file (should evict second file, not first)
        cache = TreeCache(max_entries=2, max_memory_mb=100)
        cache.put(files[0], trees[0])
        cache.put(files[1], trees[1])
        cache.get(files[0])  # Make files[0] more recent
        
        # Manually evict to test LRU order
        evicted = cache._evict_lru()
        assert evicted is not None
        assert evicted.file_path == files[1]  # files[1] should be LRU
    
    def test_cache_clear(self, cache, temp_dir):
        """Test clearing the entire cache."""
        files = list(temp_dir.glob("*.py"))
        trees = [MockTree(f"tree_{i}") for i in range(len(files))]
        
        # Cache multiple files
        for file, tree in zip(files, trees):
            cache.put(file, tree)
        
        assert len(cache._cache) > 0
        
        # Clear cache
        cache.clear()
        
        assert len(cache._cache) == 0
        for file in files:
            assert cache.get(file) is None
    
    def test_put_none_tree(self, cache, temp_file):
        """Test putting None tree (should be rejected)."""
        cache.put(temp_file, None)
        
        # Should not be cached
        assert cache.get(temp_file) is None
        assert len(cache._cache) == 0
    
    def test_put_missing_file(self, cache):
        """Test putting tree for missing file."""
        missing_file = Path("/nonexistent/file.py")
        tree = MockTree("test_tree")
        
        cache.put(missing_file, tree)
        
        # Should not be cached due to stat error
        assert len(cache._cache) == 0
    
    def test_get_stats(self, cache, temp_file):
        """Test cache statistics."""
        tree = MockTree("test_tree")
        
        # Initial stats
        stats = cache.get_stats()
        assert stats['entries'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_rate_percent'] == 0.0
        
        # Add some cache activity
        cache.get(temp_file)  # Miss
        cache.put(temp_file, tree)
        cache.get(temp_file)  # Hit
        cache.get(temp_file)  # Hit
        
        stats = cache.get_stats()
        assert stats['entries'] == 1
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['hit_rate_percent'] == 66.67
        assert stats['total_requests'] == 3
    
    def test_cleanup_stale_entries(self, cache, temp_dir):
        """Test cleaning up stale cache entries."""
        files = list(temp_dir.glob("*.py"))
        trees = [MockTree(f"tree_{i}") for i in range(len(files))]
        
        # Cache all files
        for file, tree in zip(files, trees):
            cache.put(file, tree)
        
        assert len(cache._cache) == len(files)
        
        # Modify one file to make it stale
        time.sleep(0.1)
        files[0].write_text("modified content")
        
        # Cleanup stale entries
        stale_count = cache.cleanup_stale_entries()
        
        assert stale_count == 1
        assert len(cache._cache) == len(files) - 1
        assert cache.get(files[0]) is None  # Stale entry removed
        assert cache.get(files[1]) == trees[1]  # Valid entry remains
    
    def test_get_cache_info(self, cache, temp_file):
        """Test getting detailed cache entry information."""
        tree = MockTree("test_tree")
        
        # No cache info for uncached file
        info = cache.get_cache_info(temp_file)
        assert info is None
        
        # Cache the file
        cache.put(temp_file, tree)
        
        # Get cache info
        info = cache.get_cache_info(temp_file)
        assert info is not None
        assert info['file_path'] == str(temp_file)
        assert info['hit_count'] == 0
        assert info['is_valid'] is True
        assert isinstance(info['cached_mtime'], float)
        assert isinstance(info['cached_size'], int)
        
        # Access the file to update stats
        cache.get(temp_file)
        
        # Check updated info
        info = cache.get_cache_info(temp_file)
        assert info['hit_count'] == 1
    
    def test_thread_safety_basic(self, cache, temp_file):
        """Basic test for thread safety (uses RLock)."""
        import threading
        
        tree = MockTree("test_tree")
        results = []
        
        def cache_operation():
            cache.put(temp_file, tree)
            result = cache.get(temp_file)
            results.append(result)
        
        # Run multiple threads
        threads = [threading.Thread(target=cache_operation) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        assert len(results) == 5
        assert all(result == tree for result in results)


class TestGlobalCache:
    """Test global cache functions."""
    
    def test_get_default_cache(self):
        """Test getting default global cache."""
        cache1 = get_default_cache()
        cache2 = get_default_cache()
        
        # Should return same instance
        assert cache1 is cache2
        assert isinstance(cache1, TreeCache)
    
    def test_configure_default_cache(self):
        """Test configuring default global cache."""
        cache = configure_default_cache(max_entries=200, max_memory_mb=100)
        
        assert isinstance(cache, TreeCache)
        assert cache.max_entries == 200
        assert cache.max_memory_bytes == 100 * 1024 * 1024
        
        # Should be the same as get_default_cache()
        assert get_default_cache() is cache


class TestTreeCacheIntegration:
    """Integration tests for TreeCache with realistic scenarios."""
    
    def test_realistic_development_workflow(self, temp_dir):
        """Test cache behavior in realistic development scenario."""
        cache = TreeCache(max_entries=10, max_memory_mb=5)
        
        files = list(temp_dir.glob("*.py"))
        trees = [MockTree(f"tree_{i}") for i in range(len(files))]
        
        # Initial parsing (all misses)
        for file, tree in zip(files, trees):
            assert cache.get(file) is None  # Miss
            cache.put(file, tree)
        
        # Second access (all hits)
        for file, tree in zip(files, trees):
            assert cache.get(file) == tree  # Hit
        
        # Simulate file modification
        time.sleep(0.1)
        files[0].write_text("# Modified file")
        new_tree = MockTree("new_tree_0")
        
        # Should be cache miss due to modification
        assert cache.get(files[0]) is None
        cache.put(files[0], new_tree)
        assert cache.get(files[0]) == new_tree
        
        # Verify statistics
        stats = cache.get_stats()
        assert stats['hits'] >= len(files)
        assert stats['misses'] >= len(files) + 1  # +1 for modified file
        assert stats['invalidations'] == 1
    
    def test_memory_pressure_simulation(self):
        """Test cache behavior under memory pressure."""
        # Small cache to force evictions
        cache = TreeCache(max_entries=2, max_memory_mb=1)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            
            # Create files with different sizes
            files = []
            trees = []
            
            for i in range(5):
                file_path = temp_path / f"file_{i}.py"
                # Create files with increasing sizes
                content = f"# File {i}\n" + "print('x')\n" * (i * 100)
                file_path.write_text(content)
                files.append(file_path)
                trees.append(MockTree(f"tree_{i}"))
            
            # Cache files - should trigger evictions
            for file, tree in zip(files, trees):
                cache.put(file, tree)
            
            # Verify cache size is within limits
            assert len(cache._cache) <= cache.max_entries
            assert cache._evictions > 0
            
            # Most recently cached files should still be present
            assert cache.get(files[-1]) == trees[-1]