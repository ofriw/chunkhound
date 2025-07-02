# 2025-08-02 - [IMPLEMENTATION] Serialize DuckDB Operations
**Priority**: Critical
**Type**: Bug Fix / Implementation
**Status**: Planned

## Problem
MCP server has database duplication bug due to thread-local cursors creating isolation between concurrent async tasks. When multiple file events are processed simultaneously on different threads, they cannot see each other's uncommitted changes, leading to duplicate chunk insertions.

## Root Cause
1. DuckDB connections are NOT thread-safe
2. `_get_connection()` returns thread-local cursors for non-transactional operations in MCP mode
3. Each thread's cursor has isolation from others
4. File processing tasks may run on different threads via TaskCoordinator
5. Contextvars solution tracks transaction state correctly but doesn't solve cursor isolation

## Solution: Serialize All DuckDB Operations

### Requirements
1. All database operations MUST be serialized to a single thread
2. Solution MUST be transparent to layers above DuckDBProvider
3. MUST work seamlessly with MCP server's priority queue (TaskCoordinator)
4. No changes to IndexingCoordinator, repositories, or MCP server
5. Implementation detail contained within DuckDBProvider

### Implementation Plan

#### 1. Create DuckDB Executor (Single Thread)
```python
# In DuckDBProvider.__init__
self._db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="duckdb")
# No need for separate event loop - executor has its own
```

**CRITICAL: Complete State Isolation to Executor Thread**

The executor thread must have COMPLETE isolation - no state sharing:

1. **Executor Thread State (NEVER accessed from other threads):**
   - `self._executor_connection` - The DuckDB connection (created IN executor thread)
   - `self._executor_transaction_state` - Transaction state (local to executor)
   - `self._executor_checkpoint_state` - Checkpoint state (local to executor)
   - All connection/cursor operations must happen within executor
   
2. **Main Thread State (safe to access):**
   - `self._db_executor` - The ThreadPoolExecutor instance
   - `self._db_path` - Database file path (immutable)
   - Configuration values (read-only)

3. **Key Principles:**
   - NO CONNECTION OBJECT should exist outside the executor thread
   - Connection is created INSIDE the executor on first operation
   - All state management happens INSIDE executor functions
   - Context propagation via `contextvars.copy_context()` for async compatibility
   - Results must be fully materialized before returning from executor

#### 2. Wrap All Database Operations
Create a pattern that ensures ALL operations execute in the dedicated thread:

```python
async def _run_in_db_thread(self, func, *args, **kwargs):
    """Execute database operation in dedicated thread with complete isolation."""
    loop = asyncio.get_event_loop()
    
    # Capture context for async compatibility
    ctx = contextvars.copy_context()
    
    # Create wrapper that executes in executor thread
    def executor_wrapper():
        # This runs IN the executor thread
        # Connection is created/accessed only here
        return func(*args, **kwargs)
    
    # Submit to executor with context
    future = loop.run_in_executor(
        self._db_executor,
        ctx.run,
        executor_wrapper
    )
    return await future
```

**Critical Design Pattern:**
1. The connection is NEVER passed as a parameter
2. Each executor function creates/accesses connection locally
3. State variables are thread-local to the executor
4. Only serializable results cross thread boundary

#### 3. Call Sites to Modify

**DuckDBProvider Direct Operations:**
- `create_vector_index()` - Line 219: `self._get_connection().execute(...)`
- `drop_vector_index()` - Line 239: `self._get_connection().execute(...)`
- `get_existing_vector_indexes()` - Line 255: `self._get_connection().execute(...)`
- `search_semantic()` - Lines 590, 729: `self._get_connection().execute(...)`
- `search_regex()` - Lines 646, 652, 671: `self._get_connection().execute(...)`
- `search_text()` - Line 712: `self._get_connection().execute(...)`
- `get_stats()` - Lines 754, 755, 761, 767: `self._get_connection().execute(...)`
- `execute_query()` - Lines 856, 858: `self._get_connection().execute(...)`
- `begin_transaction()` - Line 882: `self._connection_manager.connection.execute(...)`
- `commit_transaction()` - Line 892: `self._connection_manager.connection.execute(...)`
- `rollback_transaction()` - Line 916: `self._connection_manager.connection.execute(...)`

**Repository Delegations:**
All repository methods are already delegated, need to ensure repositories use serialized operations:
- ChunkRepository: All operations via `_get_connection().execute()`
- FileRepository: All operations via `_get_connection().execute()`
- EmbeddingRepository: All operations via `_get_connection().execute()`

**Properties That Expose Connection State:**
- `DuckDBProvider.connection` - Returns `self._connection_manager.connection`
- `DuckDBProvider.db_path` - Returns `self._connection_manager.db_path`
- `DuckDBProvider.is_connected` - Returns `self._connection_manager.is_connected`

These properties must either:
1. Be wrapped to execute in DB thread
2. Return safe copies/values that don't expose connection objects
3. Be documented as "internal use only"

### Implementation Approach: Complete Isolation Pattern

#### Recommended Pattern: Executor-Local State
Instead of wrapping methods or connections, use a pattern where ALL state lives in the executor:

```python
class DuckDBProvider:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="duckdb")
        # NO connection created here - it's created IN the executor
        
    async def _execute_in_db_thread(self, operation_name: str, *args, **kwargs):
        """Execute named operation in DB thread with complete isolation."""
        loop = asyncio.get_event_loop()
        
        def executor_operation():
            # Get thread-local connection (created on first access)
            conn = _get_thread_local_connection(self._db_path)
            
            # Get thread-local state
            state = _get_thread_local_state()
            
            # Execute operation
            op_func = getattr(self, f'_executor_{operation_name}')
            return op_func(conn, state, *args, **kwargs)
        
        # Run in executor
        return await loop.run_in_executor(self._db_executor, executor_operation)
    
    # Public API methods delegate to executor
    async def search_semantic(self, query: str, **kwargs):
        return await self._execute_in_db_thread('search_semantic', query, **kwargs)
    
    # Executor-only methods (run IN executor thread)
    def _executor_search_semantic(self, conn, state, query: str, **kwargs):
        # This runs IN the executor thread
        # Can safely use connection and state
        cursor = conn.execute("SELECT * FROM chunks WHERE ...")
        return cursor.fetchall()  # Materialize results
```

**Key Benefits:**
1. Connection NEVER exists outside executor thread
2. All state management is local to executor thread
3. No complex wrapping or proxying needed
4. Clean separation between public API and executor operations

### Considerations
1. **Thread-Local Storage**: Use `threading.local()` for executor thread state
   ```python
   # Global thread-local storage for executor thread
   _executor_local = threading.local()
   
   def _get_thread_local_connection(db_path):
       if not hasattr(_executor_local, 'connection'):
           _executor_local.connection = duckdb.connect(db_path)
       return _executor_local.connection
   ```

2. **Error Handling**: Exceptions automatically propagate from executor
3. **Cleanup**: Shutdown executor and close connection on provider disconnect
4. **Performance**: Single thread ensures consistency; DuckDB already serializes writes
5. **State Isolation**: Complete - no shared state between threads
6. **Simplification**: Remove ALL thread-safety code from ConnectionManager

### Testing Plan
1. Create concurrent file processing test
2. Verify no duplicate chunks with rapid file changes
3. Ensure priority queue still works (high priority searches preempt low priority indexing)
4. Test transaction rollback scenarios
5. Benchmark performance impact

### Success Criteria
1. No database duplications under any concurrent load
2. All existing tests pass
3. MCP server tools maintain responsiveness
4. No changes required in upper layers

## Q&A / Clarifications

**Q: Why complete isolation instead of shared state?**
A: Based on best practices:
- Thread safety bugs are eliminated when threads share NO mutable state
- DuckDB connections are not thread-safe
- Isolation pattern is simpler to reason about and maintain

**Q: Will this impact performance?**
A: Minimal impact:
- DuckDB already serializes writes internally
- Single writer pattern matches DuckDB's architecture
- No lock contention since there's only one DB thread
- TaskCoordinator's priority queue still ensures responsiveness

**Q: What about connection pooling?**
A: Not needed:
- Single connection in executor thread
- Connection persists for provider lifetime
- No overhead of connection creation/destruction

**Q: How does transaction state work across threads?**
A: Transaction state is executor-local:
- Begin/commit/rollback operations execute in DB thread
- Transaction state never crosses thread boundary
- Each operation checks local transaction state

**Q: What about the ConnectionManager?**
A: Significantly simplified:
- Remove all thread-local cursor code
- Remove connection locks
- Keep only checkpoint/transaction logic
- All operations happen in single thread