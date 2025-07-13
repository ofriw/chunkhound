# 2025-01-13 - [BUG] Chunk Cleanup Fails on File Modification
**Priority**: High

When files are modified, old chunks are not removed from the database. New chunks are added alongside old ones, resulting in duplicate and stale content appearing in search results.

## Problem Description

During file modification, the chunk diffing logic fails to properly identify and remove obsolete chunks. This leads to:
- Old content remaining searchable after file edits
- Chunk count growing with each modification
- Search results containing both old and new versions of code
- Database bloat over time

## Evidence

From test output:
```
Old content found: 2 results
New content found: 2 results

Chunks for test1.py after modification: 4
  Chunk 1: function - def test_function1():        # OLD
  Chunk 2: docstring - '''RELPATH_TEST_MARKER_111''' # OLD
  Chunk 3: function - def test_function1_modified(): # NEW
  Chunk 4: docstring - '''RELPATH_TEST_MODIFIED_333''' # NEW
```

Expected: 2 chunks (only new content)
Actual: 4 chunks (both old and new content)

## Root Cause

The issue appears to be in the chunk diffing logic in `IndexingCoordinator._process_file_locked()`. The smart diff mechanism that should identify unchanged, modified, added, and deleted chunks is not working correctly for modifications.

## Impact

- **Search accuracy**: Users get outdated results mixed with current code
- **Database size**: Grows unnecessarily with duplicate chunks
- **Performance**: More chunks to search through and compare
- **User confusion**: Multiple versions of the same function in results

## Reproduction Steps

1. Create a file with identifiable content
2. Index the file
3. Modify the file (change function names, docstrings, etc.)
4. Re-index the file
5. Search for both old and new content
6. Both will be found, confirming chunks weren't cleaned up

## Workarounds

- Manually delete and re-add files instead of modifying
- Periodically rebuild the database from scratch
- Use file deletion + recreation instead of in-place edits

## Related Issues

- This bug was discovered while implementing relative path storage
- It's unrelated to path handling - it's a pure chunk management issue
- May be related to the file modification indexing bug (files disappearing)

## Suggested Fix

1. Debug `ChunkCacheService` and chunk comparison logic
2. Ensure chunk IDs are properly tracked during modifications  
3. Verify the diff algorithm correctly identifies removed chunks
4. Add comprehensive tests for chunk lifecycle management
5. Consider simplifying to "delete all chunks and re-add" for modified files

## Test Case

See `test/test-relative-paths.py` which demonstrates the issue:
- After file modification, both old and new chunks exist
- `stats['chunks']` shows 6 instead of expected 4
- Search finds both old and new content

# History

## 2025-01-13T18:30:00+03:00
Bug discovered during relative path implementation. Chunk cleanup is failing during file modifications, causing old content to persist in the database alongside new content. This is a chunk management issue, not related to path handling.

## 2025-01-13T18:45:00+03:00
**Root Cause Found and Fixed**

The issue was an interface mismatch in the `database.py` wrapper class:

1. **Problem**: The `Database.get_chunks_by_file_id()` method didn't accept the `as_model` parameter
   - IndexingCoordinator calls `self._db.get_chunks_by_file_id(file_id, as_model=True)`
   - Database wrapper was hardcoded to always return dictionaries
   - Chunk deletion logic expects Chunk models with `.id` attribute
   - Dictionary access to `.id` failed silently, returning empty list
   - No chunks were deleted, causing duplicates

2. **Fix Applied**: Updated `database.py` to properly pass through the parameter:
   ```python
   def get_chunks_by_file_id(self, file_id: int, as_model: bool = False) -> list[dict[str, Any] | Chunk]:
       """Get chunks for a specific file."""
       return self._provider.get_chunks_by_file_id(file_id, as_model=as_model)
   ```

3. **Testing**: Created comprehensive tests that confirm:
   - Bug reproduction: 8 chunks after modification (4 old + 4 new)
   - Expected behavior: 4 chunks after modification
   - Both old and new content searchable before fix
   - Only new content searchable after fix

The fix ensures the indexing coordinator receives proper Chunk models during modification, allowing the deletion logic to work correctly.