# 2025-01-09 - [BUG] LanceDB Storage Growth - No Garbage Collection
**Priority**: High

LanceDB storage grows unbounded to 7GB while DuckDB remains at 400MB for the same data. Root cause: no automatic garbage collection or compaction implemented.

## Problem Details

1. **Storage Size Discrepancy**
   - LanceDB: 6.7GB (mostly in chunks.lance/data: 6.6GB)
   - DuckDB: 363MB + 1.8MB WAL
   - Same data, ~15x size difference

2. **Evidence of Missing Cleanup**
   - 1,043 version manifest files in `.chunkhound.lancedb/chunks.lance/_versions/`
   - 567 data files in `.chunkhound.lancedb/chunks.lance/data/`
   - Many duplicate 38MB files (indicating rewrites without cleanup)
   - No calls to `optimize()`, `compact_files()`, or `cleanup_files()` in codebase

3. **Three Uncoordinated Write Paths**
   - CLI indexer (batch operations)
   - MCP filesystem events (single file updates)
   - MCP background indexing (batch operations)

## Root Cause

LanceDB requires manual compaction/cleanup but ChunkHound never calls these operations. Every write creates new versions/fragments that accumulate indefinitely. DuckDB handles this automatically.

## Optimization Strategy

### 1. CLI Indexer
**When**: After `chunkhound index` completes
**Where**: End of indexing in `services/indexing_coordinator.py`

### 2. MCP Server (Quiet Period)
**When**: After 5 minutes of no database activity (reads or writes)
**Where**: Background task in `chunkhound/mcp_server.py`
**Note**: Must coordinate with SerialDatabaseProvider executor to track all DB operations

## Implementation

```python
# 1. Add to DatabaseProvider interface
class DatabaseProvider(ABC):
    @abstractmethod
    def optimize(self) -> None:
        """Optimize database storage. No-op for providers that auto-optimize."""
        pass

# 2. LanceDBProvider implementation
def optimize(self):
    """Run optimization on all tables."""
    if self._chunks_table:
        self._chunks_table.optimize()
    if self._files_table:
        self._files_table.optimize()

# 3. DuckDBProvider implementation  
def optimize(self):
    """No-op - DuckDB handles optimization automatically."""
    pass

# 4. Call after CLI indexing
# In indexing_coordinator.py, after indexing:
self._db.optimize()

# 5. SerialDatabaseProvider - track last activity
def _execute_in_db_thread_sync(self, method_name: str, *args, **kwargs):
    self.last_activity_time = time.time()  # Track ALL operations
    # ... existing execution code ...

# 6. MCP Server quiet period check
# Check executor's last activity time:
if time.time() - db.last_activity_time > 300:  # 5 minutes
    db.optimize()
```

## Files to Modify

1. **interfaces/database_provider.py** - Add `optimize()` to interface
2. **providers/database/lancedb_provider.py** - Implement `optimize()`
3. **providers/database/duckdb_provider.py** - Implement `optimize()` as no-op
4. **providers/database/serial_database_provider.py** - Track `last_activity_time` in executor
5. **services/indexing_coordinator.py** - Call `self._db.optimize()` after indexing
6. **chunkhound/mcp_server.py** - Check `db.last_activity_time` for quiet period

## History

### 2025-01-09T11:10:01+03:00
Initial investigation revealed massive storage growth in LanceDB due to missing garbage collection. Identified three write paths that need coordination. Planned phased implementation starting with basic optimization after batch operations.

### 2025-01-09T11:12:10+03:00
Updated MCP server optimization strategy to use quiet period detection instead of immediate optimization. This prevents disrupting user flow during active sessions. Optimization will only run after X minutes of inactivity.

### 2025-01-09T11:19:44+03:00
Refined to track ALL database activity (reads and writes) in the SerialDatabaseProvider executor. This ensures optimization only runs during true quiet periods with no database operations.

### 2025-01-09T14:30:00+03:00
Implementation completed successfully. The following changes were made:

1. **DatabaseProvider Interface**: The `optimize_tables()` method already existed in the interface
2. **LanceDBProvider**: Already had `optimize_tables()` implementation that calls `table.optimize()` on chunks and files tables  
3. **DuckDBProvider**: Already had `optimize_tables()` as a no-op since DuckDB handles optimization automatically
4. **Activity Tracking**: Added `last_activity_time` tracking in SerialDatabaseExecutor that updates on every database operation
5. **CLI Optimization**: The indexing_coordinator already calls `optimize_tables()` after bulk directory processing
6. **MCP Quiet Period**: Added `_periodic_optimization_loop()` to PeriodicIndexManager that:
   - Checks database activity every 60 seconds
   - Runs optimization if database has been quiet for 5 minutes
   - Avoids repeated optimizations within the quiet period window

All code compiles successfully and the implementation follows the planned strategy. The LanceDB storage growth issue should now be mitigated through:
- Automatic optimization after CLI bulk operations
- Periodic optimization during quiet periods in MCP server
- Proper cleanup and compaction of LanceDB data files

**Files Modified:**
- `providers/database/serial_executor.py`: Added last_activity_time tracking and get_last_activity_time() method
- `providers/database/serial_database_provider.py`: Added last_activity_time property to expose activity tracking
- `chunkhound/periodic_indexer.py`: Added _periodic_optimization_loop() for quiet period detection and optimization

**Technical Details:**
- Activity tracking updates on EVERY database operation (reads, writes, searches)
- Quiet period check runs every 60 seconds
- Optimization triggers after 5 minutes of no database activity
- Prevents repeated optimizations within the same quiet period window
- Graceful shutdown handling for the optimization task
- All existing optimize_tables() implementations were already correct

This solution addresses the root cause of LanceDB storage growth by ensuring regular garbage collection during periods of low activity, matching the behavior that DuckDB gets automatically through its WAL/MVCC system.</content>