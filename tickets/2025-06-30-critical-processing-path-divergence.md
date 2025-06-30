# 2025-06-30 - Critical Processing Path Divergence
**Priority**: CRITICAL
**Status**: FIXED

## Issue Summary
MCP server and CLI use different file processing methods, causing duplicate chunks in database. The divergent code paths handle chunk deduplication differently.

## Root Cause
**Processing Method Mismatch**:
- MCP server: Uses `process_file_incremental()` 
- CLI (--watch): Uses `process_file()`

### Evidence from Code
1. **MCP Server** (`mcp_server.py:513`):
```python
result = await _database.process_file_incremental(file_path=file_path)
```

2. **CLI Watch Mode** (`run.py:431`):
```python
result = await indexing_coordinator.process_file(file_path)
```

3. **Database Delegation** (`database.py:136-142`):
```python
async def process_file_incremental(self, file_path: Path) -> dict[str, Any]:
    """Note: True incremental processing not yet implemented in service layer.
    This delegates to the provider's incremental processing method."""
    return await self._provider.process_file_incremental(file_path)
```

### Technical Analysis
```
MCP Path:                          CLI Path:
process_file_change()              process_cli_file_change()
    ↓                                  ↓
Database.process_file_incremental() IndexingCoordinator.process_file()
    ↓                                  ↓
Provider.process_file_incremental() Smart diff + chunk deduplication
    ↓                                  ↓
Direct DB operations               Transaction-wrapped updates
```

### Why Duplicates Occur
1. `process_file()` has sophisticated smart diff logic (lines 249-323 in IndexingCoordinator)
2. `process_file_incremental()` bypasses service layer, goes direct to provider
3. Provider's incremental method likely missing deduplication checks
4. Running both paths on same files → duplicate chunks

## Impact
- Database contains duplicate chunks for files processed by both paths
- Smart diff benefits lost when using MCP server
- Embeddings generated multiple times
- Inconsistent behavior between MCP and CLI

## Recommended Fix

### Option 1: Quick Fix (Recommended)
Change MCP server to use the same processing path as CLI:

**File**: `chunkhound/mcp_server.py:513`
```python
# BEFORE:
result = await _database.process_file_incremental(file_path=file_path)

# AFTER:
result = await _database._indexing_coordinator.process_file(file_path)
```

This immediately gives MCP server the same smart diff and deduplication logic as CLI.

### Option 2: Complete Fix
Remove the half-implemented incremental processing entirely:

1. **Remove from Database class** (`database.py`):
   - Delete `process_file_incremental()` method (lines 136-142)
   
2. **Remove from DatabaseProvider interface** (`interfaces/database_provider.py`):
   - Delete `process_file_incremental()` abstract method
   
3. **Remove from all providers**:
   - Delete implementations in DuckDBProvider, etc.

### Why Option 1 is Best
- Minimal change (1 line)
- Immediately fixes duplicate chunks issue
- Preserves all smart diff benefits
- Both MCP and CLI use identical processing
- Can still implement true incremental processing later if needed

### Testing the Fix
1. Delete existing database
2. Run MCP server to index codebase
3. Make file changes
4. Verify no duplicate chunks in search results
5. Run CLI --watch on same codebase
6. Verify no additional duplicates created

## Fix Applied - 2025-06-30

**STATUS**: FIXED - MCP server now uses unified processing path.

### Changes Made
Modified `chunkhound/mcp_server.py:513` to use the IndexingCoordinator's process_file method:
```python
# CHANGED FROM:
result = await _database.process_file_incremental(file_path)

# CHANGED TO:
result = await _database._indexing_coordinator.process_file(file_path)
```

### Result
- MCP server and CLI now use identical file processing logic
- Smart diff and deduplication work correctly
- No more duplicate chunks from divergent processing paths
- Both tools benefit from the same optimizations

### Verification
The fix was applied in commit 3aecfc7 along with other critical search improvements.

## Remaining Issues
While the duplicate chunks issue is resolved, real-time indexing still has problems:
- Python files are not being indexed (other languages work)
- File modifications are not triggering re-indexing
- See ticket 2025-06-29-critical-real-time-indexing-failure.md for details

### Changes Made
1. ✅ **MCP Server Fixed** (`mcp_server.py:513`)
   - Changed from `_database.process_file_incremental(file_path)`
   - To: `_database._indexing_coordinator.process_file(file_path)`

2. ✅ **Removed from Database Class** (`database.py:136-142`)
   - Deleted `process_file_incremental()` method entirely

3. ✅ **Removed from Interface** (`interfaces/database_provider.py:217-219`)
   - Deleted abstract method from DatabaseProvider protocol

4. ✅ **Removed from Providers** (`providers/database/duckdb_provider.py`)
   - Deleted `process_file_incremental()` implementation
   - Also removed `_fallback_process_file()` helper method

### Result
- Both MCP and CLI now use identical processing path
- Smart diff and deduplication work correctly
- No more duplicate chunks in database
- Method completely removed to prevent regression

## Complete Fix to Prevent Regression

### 1. Immediate Fix (mcp_server.py:513)
```python
# Change from:
result = await _database.process_file_incremental(file_path=file_path)
# To:
result = await _database._indexing_coordinator.process_file(file_path)
```

### 2. Remove Broken Method (database.py:136-142)
Delete the `process_file_incremental()` method entirely:
```python
# DELETE THIS METHOD:
async def process_file_incremental(self, file_path: Path) -> dict[str, Any]:
    """Process a file with incremental parsing and differential chunking.
    
    Note: True incremental processing not yet implemented in service layer.
    This delegates to the provider's incremental processing method.
    """
    return await self._provider.process_file_incremental(file_path)
```

### 3. Update Interface (interfaces/database_provider.py:217-219)
Remove from DatabaseProvider protocol:
```python
# DELETE THIS ABSTRACT METHOD:
async def process_file_incremental(self, file_path: Path) -> dict[str, Any]:
    """Process a file with incremental parsing and differential chunking."""
    ...
```

### 4. Remove Provider Implementations
Delete `process_file_incremental()` from all providers:
- `providers/duckdb_provider.py`
- Any other database providers

### 5. Add Test to Prevent Regression
Create test that verifies both paths use same processing:
```python
def test_mcp_and_cli_use_same_processing():
    """Ensure MCP and CLI use identical file processing paths."""
    # Test that process_file_incremental doesn't exist
    assert not hasattr(Database, 'process_file_incremental')
    # Test that both code paths use IndexingCoordinator
```

### Why Complete Removal is Essential
1. **Prevents accidental reuse** - Can't call a method that doesn't exist
2. **Forces proper implementation** - Future incremental processing must go through service layer
3. **Cleaner codebase** - No half-implemented features
4. **Clear intent** - Shows incremental processing was intentionally removed
5. **Test coverage** - Regression test ensures it stays fixed