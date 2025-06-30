# 2025-06-30 - Duplicate Chunks from Processing Divergence
**Priority**: HIGH
**Status**: FIXED

## Summary
Different file processing paths between MCP and CLI cause duplicate chunks when both index the same codebase at different times.

## Sequence
1. User runs MCP server → files indexed via `process_file_incremental()`
2. User stops MCP, runs CLI with `--watch` → same files re-indexed via `process_file()`  
3. Result: Database contains duplicate chunks for all files

## Root Cause
The `process_file_incremental()` method bypasses the IndexingCoordinator's smart diff logic that prevents duplicates. This unfinished incremental implementation goes direct to provider without proper deduplication.

## Why Real-Time Indexing Still Appears Broken
When testing real-time changes:
1. File already has chunks from MCP's `process_file_incremental()`
2. CLI --watch detects change, uses `process_file()` with smart diff
3. Smart diff can't match chunks due to different storage patterns
4. New chunks added instead of updating existing ones
5. Appears as if real-time indexing failed (duplicate results in search)

## Recommended Fix

### Immediate Solution
Change `mcp_server.py:513` from:
```python
result = await _database.process_file_incremental(file_path=file_path)
```

To:
```python
result = await _database._indexing_coordinator.process_file(file_path)
```

### Why This Works
1. Both MCP and CLI will use the same IndexingCoordinator logic
2. Smart diff will properly detect and update existing chunks
3. No more duplicate chunks from different processing paths
4. Content hash comparison will work correctly
5. Embeddings will be preserved during updates

### Implementation Note
The `process_file_incremental()` was meant for performance but was never fully implemented in the service layer. It bypasses critical deduplication logic. Using the standard `process_file()` path ensures consistency and correctness.

### Verification
After fix:
- Real-time indexing will show updates, not duplicates
- File modifications will properly replace old chunks
- Search results will be accurate without duplicates

## Preventing Future Regression

### Required Changes
1. **Fix MCP server** - Change to use `_database._indexing_coordinator.process_file()`
2. **Delete the method** - Remove `process_file_incremental()` from Database class
3. **Update interface** - Remove from DatabaseProvider protocol
4. **Clean providers** - Remove from all provider implementations
5. **Add regression test** - Verify method doesn't exist

### Why Full Removal Matters
- Half-implemented methods are technical debt
- Prevents someone from "fixing" it incorrectly later
- Forces future incremental processing through proper service layer
- Makes the codebase clearer and more maintainable

## Fix Applied - 2025-06-30

### What Was Done
1. **MCP server updated** to use `_database._indexing_coordinator.process_file()`
2. **Method removed** from Database class completely
3. **Interface cleaned** - removed from DatabaseProvider protocol
4. **Providers cleaned** - removed from DuckDBProvider and _fallback_process_file()

### Verification
- The `process_file_incremental()` method no longer exists anywhere
- Both MCP and CLI use the exact same processing path
- Smart diff and chunk deduplication now work correctly
- No more duplicate chunks will be created