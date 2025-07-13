"""
File Discovery Cache for optimizing glob operations.

This module provides caching for expensive filesystem operations,
specifically glob pattern matching and file filtering.
"""

import logging
import os
import time
from collections import OrderedDict
from fnmatch import fnmatch
from pathlib import Path

logger = logging.getLogger(__name__)


class FileDiscoveryCache:
    """Cache for file discovery operations to reduce filesystem overhead."""

    def __init__(self, max_entries: int = 100, ttl_seconds: int = 300):
        """Initialize the cache.

        Args:
            max_entries: Maximum number of cache entries to keep (LRU eviction)
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds

        # Cache structure: key -> (result, timestamp, directory_mtime)
        self._cache: OrderedDict[str, tuple[list[Path], float, float]] = OrderedDict()

        # Statistics for monitoring
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "invalidations": 0}

    def get_files(
        self,
        directory: Path,
        patterns: list[str],
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Get files matching patterns with caching.

        Args:
            directory: Directory to search
            patterns: List of glob patterns to match
            exclude_patterns: List of glob patterns to exclude

        Returns:
            List of matching file paths
        """
        # Create cache key from directory and patterns
        cache_key = self._make_cache_key(directory, patterns, exclude_patterns)

        # Check cache first
        cached_result = self._get_from_cache(cache_key, directory)
        if cached_result is not None:
            self.stats["hits"] += 1
            logger.debug(f"Cache hit for {directory} with {len(patterns)} patterns")
            return cached_result

        # Cache miss - perform file discovery
        self.stats["misses"] += 1
        logger.debug(f"Cache miss for {directory} with {len(patterns)} patterns")

        # Discover files
        files = self._discover_files(directory, patterns, exclude_patterns)

        # Store in cache
        self._store_in_cache(cache_key, files, directory)

        return files

    def invalidate_directory(self, directory: Path) -> int:
        """Invalidate all cache entries for a directory.

        Args:
            directory: Directory to invalidate

        Returns:
            Number of entries invalidated
        """
        dir_str = str(directory)
        keys_to_remove = []

        for key in self._cache:
            if key.startswith(f"{dir_str}|"):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]
            self.stats["invalidations"] += 1

        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for {directory}")
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self.stats["evictions"] += count
        logger.debug(f"Cleared {count} cache entries")

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache hit/miss statistics
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self.stats,
            "cache_size": len(self._cache),
            "hit_rate_percent": int(round(hit_rate, 2)),
        }

    def _make_cache_key(
        self, directory: Path, patterns: list[str], exclude_patterns: list[str] | None
    ) -> str:
        """Create a cache key from directory and patterns.

        Args:
            directory: Directory path
            patterns: Include patterns
            exclude_patterns: Exclude patterns

        Returns:
            Cache key string
        """
        patterns_str = "|".join(sorted(patterns))
        exclude_str = "|".join(sorted(exclude_patterns or []))
        return f"{directory}|{patterns_str}|{exclude_str}"

    def _get_from_cache(self, cache_key: str, directory: Path) -> list[Path] | None:
        """Get entry from cache if valid.

        Args:
            cache_key: Cache key to lookup
            directory: Directory path for mtime checking

        Returns:
            Cached file list if valid, None otherwise
        """
        if cache_key not in self._cache:
            return None

        files, timestamp, cached_mtime = self._cache[cache_key]
        current_time = time.time()

        # Check TTL expiration
        if current_time - timestamp > self.ttl_seconds:
            del self._cache[cache_key]
            self.stats["evictions"] += 1
            logger.debug(f"Cache entry expired for key: {cache_key}")
            return None

        # Check directory modification time
        try:
            current_mtime = directory.stat().st_mtime
            if current_mtime > cached_mtime:
                del self._cache[cache_key]
                self.stats["invalidations"] += 1
                logger.debug(
                    f"Cache entry invalidated (directory modified): {cache_key}"
                )
                return None
        except OSError:
            # Directory might not exist anymore
            del self._cache[cache_key]
            self.stats["invalidations"] += 1
            return None

        # Move to end (LRU)
        self._cache.move_to_end(cache_key)
        return files

    def _store_in_cache(
        self, cache_key: str, files: list[Path], directory: Path
    ) -> None:
        """Store files in cache.

        Args:
            cache_key: Cache key
            files: List of file paths to cache
            directory: Directory path for mtime tracking
        """
        try:
            directory_mtime = directory.stat().st_mtime
        except OSError:
            # Can't cache if we can't get mtime
            return

        # Enforce max entries (LRU eviction)
        while len(self._cache) >= self.max_entries:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self.stats["evictions"] += 1

        # Store entry
        self._cache[cache_key] = (files, time.time(), directory_mtime)
        logger.debug(f"Cached {len(files)} files for key: {cache_key}")

    def _discover_files(
        self, directory: Path, patterns: list[str], exclude_patterns: list[str] | None
    ) -> list[Path]:
        """Fast file discovery using os.scandir() - single traversal for all platforms.

        Args:
            directory: Directory to search
            patterns: Include patterns
            exclude_patterns: Exclude patterns

        Returns:
            List of matching file paths
        """
        try:
            # Parse patterns to extract extensions and special filenames
            extensions = set()
            special_files = set()
            for pattern in patterns:
                if '**/*' in pattern:
                    extensions.add(pattern.replace('**/*', ''))
                elif '**/' in pattern:
                    special_files.add(pattern.replace('**/', ''))
            
            files = []
            
            def scan_directory(path: Path):
                """Recursively scan directory using os.scandir()."""
                try:
                    with os.scandir(path) as entries:
                        for entry in entries:
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    # Check extensions or special filenames
                                    if any(entry.name.endswith(ext) for ext in extensions) or entry.name in special_files:
                                        file_path = Path(entry.path)
                                        # Apply exclusions if any
                                        if exclude_patterns:
                                            rel_path = file_path.relative_to(directory)
                                            if any(fnmatch(str(rel_path), pattern) for pattern in exclude_patterns):
                                                continue
                                        files.append(file_path)
                                elif entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.'):
                                    # Recurse into non-hidden directories
                                    scan_directory(Path(entry.path))
                            except OSError:
                                # Skip inaccessible entries
                                continue
                except OSError:
                    # Skip inaccessible directories
                    pass
            
            scan_directory(directory)
            return files

        except Exception as e:
            logger.error(f"Failed to discover files in {directory}: {e}")
            return []
