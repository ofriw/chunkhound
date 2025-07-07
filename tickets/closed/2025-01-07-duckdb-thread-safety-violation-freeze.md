# 2025-01-07 - [BUG] DuckDB Thread Safety Violation Causes Search Freeze

**Status**: CLOSED - Fixed via async/sync boundary correction  
**Severity**: Critical  
**Problem**: Search queries freeze after file deletion operations due to thread safety violation in DuckDB provider  
**Root Cause**: Multiple thread safety issues - WAL cleanup (partially fixed) and file deletion handling  
**Fix Implemented**: 2025-01-07 - Moved WAL cleanup inside executor thread with synchronization (partial fix)

## Problem Description

When using semantic search with queries like "LanceDB provider implementation database", the search tool freezes and becomes unresponsive. All subsequent search operations fail to execute, requiring a process restart.

## Root Cause Analysis

### Real Issue: WAL Cleanup Race Condition
The actual root cause was WAL cleanup happening outside the executor thread:

```python
# In _create_connection():
self._connection_manager._preemptive_wal_cleanup()  # CREATES TEST CONNECTION!
```

The `_preemptive_wal_cleanup()` method creates a test DuckDB connection to validate the WAL file. This violates thread safety because:
1. Multiple executor threads call `_create_connection()` concurrently
2. Each calls WAL cleanup without synchronization
3. WAL cleanup creates its own test connection outside the executor
4. Multiple threads access WAL files and create connections simultaneously
5. DuckDB enters undefined behavior and freezes

## Fix Implementation

### Moved WAL Cleanup Inside Executor Thread

1. **Added synchronization** (duckdb_provider.py:54-55):
```python
self._wal_cleanup_lock = threading.Lock()
self._wal_cleanup_done = False
```

2. **Removed WAL cleanup from connection creation** (duckdb_provider.py:72-93):
```python
def _create_connection(self) -> Any:
    # No WAL cleanup here - just create connection
    conn = duckdb.connect(str(self._connection_manager.db_path))
    # Load extensions...
```

3. **Added synchronized WAL cleanup in executor** (duckdb_provider.py:147-151):
```python
# In _executor_connect():
with self._wal_cleanup_lock:
    if not self._wal_cleanup_done:
        self._perform_wal_cleanup_in_executor(conn)
        self._wal_cleanup_done = True
```

4. **WAL cleanup now runs in executor thread** (duckdb_provider.py:168-202):
- Uses existing connection for validation
- No new connections created outside executor
- File operations synchronized via lock

## Key Insights

1. **ALL DuckDB operations must happen in same thread** - Including WAL validation
2. **File operations need synchronization** - WAL cleanup modifies shared filesystem state
3. **One-time initialization pattern** - WAL cleanup only needs to happen once per provider instance

## Solution Benefits

- **Thread Safety**: All DuckDB operations now occur within executor thread
- **No Race Conditions**: Lock ensures single WAL cleanup operation
- **Better Performance**: WAL cleanup happens once, not per connection
- **Maintains Isolation**: Each executor thread still has its own connection

# History

## 2025-01-07 - File Deletion Freeze Discovered

QA testing revealed the freeze issue persists with file deletion operations:

### New Findings
1. **File Deletion Triggers Freeze**: When a file is deleted from the filesystem, subsequent regex searches cause the MCP server to freeze completely
2. **Stale Data Issue**: Deleted file content remains searchable in the index
3. **New File Indexing Failure**: Files created in the working directory are not being indexed by the file watcher

### Test Results
- ✅ Search existing files: Working
- ❌ Add new file and search: New files not indexed
- ✅ Edit existing file: Changes reflected in ~10 seconds
- ❌ Delete file: Content remains searchable, causes freeze on next regex search
- ⚠️ Other tests blocked due to freeze

### Root Cause Analysis
The WAL cleanup fix only addressed initialization issues. File deletion creates a new thread safety violation:
1. File deletion operations don't properly clean up database state
2. Subsequent searches try to access deleted file records
3. This creates a thread safety violation similar to the WAL issue
4. DuckDB freezes when accessing inconsistent state

### Next Steps
- Investigate file deletion handling in the serial executor
- Check if file deletion operations bypass the executor thread
- Review transaction handling during file deletion
- Ensure all database operations related to file deletion go through the serial executor

## 2025-01-07 - Root Cause Identified: Async/Sync Boundary Violation

### Real Root Cause
The actual root cause is an **async/sync boundary violation** in the file watcher integration:

1. **Event Flow**:
   - File deletion event → buffered by watchdog handler
   - FileWatcherManager polls events every 200ms in async loop (`_polling_loop`)
   - Calls async `process_file_change` → calls **sync** `delete_file_completely`
   
2. **The Problem**:
   - `delete_file_completely` is synchronous and blocks the event loop
   - Uses `_execute_in_db_thread_sync` which waits for executor thread completion
   - While waiting, the entire async event loop is blocked
   - No other async operations (like search) can execute
   - Creates the appearance of a "freeze"

3. **Why File Deletion is Different**:
   - Involves multiple sequential database operations (embeddings → chunks → file)
   - Takes longer than simple queries, increasing blocking time
   - More likely to cause noticeable freezes

### Fix Implementation

Created async version of `delete_file_completely` to properly yield control:

1. **Added to DuckDBProvider** (duckdb_provider.py:1063-1065):
```python
async def delete_file_completely_async(self, file_path: str) -> bool:
    """Async version of delete_file_completely for non-blocking operation."""
    return await self._execute_in_db_thread("delete_file_completely", file_path)
```

2. **Added to Database wrapper** (database.py:353-366):
```python
async def delete_file_completely_async(self, file_path: str) -> bool:
    """Async version of delete_file_completely for non-blocking operation."""
    if hasattr(self._provider, 'delete_file_completely_async'):
        return await self._provider.delete_file_completely_async(file_path)
    else:
        # Fallback for providers without async support
        return self._provider.delete_file_completely(file_path)
```

3. **Updated process_file_change** (mcp_server.py:630):
```python
# Changed from:
_database.delete_file_completely(str(file_path))
# To:
await _database.delete_file_completely_async(str(file_path))
```

### Key Insights
- **All database operations called from async contexts must be async**
- Sync operations in async contexts block the entire event loop
- The serial executor pattern works correctly - the issue was at the async/sync boundary
- File operations are particularly susceptible due to their longer execution time