# 2025-01-07 - [TODO] Align LanceDB with Serial Executor Pattern

**Priority**: High  
**Status**: Open  
**Dependencies**: Completed serial executor refactoring (tickets/closed/refactor-database-serial-executor.md)

Refactor LanceDBProvider to inherit from SerialDatabaseProvider and use the same serial execution pattern as DuckDB for consistency and maintainability.

## Scope

### What Changes
1. LanceDBProvider will inherit from SerialDatabaseProvider
2. All database operations will go through SerialDatabaseExecutor
3. Connection management will be thread-safe with thread-local connections
4. Capability detection will use hasattr() pattern

### What Stays the Same
1. LanceDB's unique CWD management during connection
2. Schema recreation logic for embedding dimension changes
3. Data corruption recovery mechanisms
4. Automatic index management
5. No-op transaction methods (LanceDB handles internally)
6. All external APIs remain unchanged

## Requirements

### 1. Inherit from SerialDatabaseProvider
- Change class declaration to inherit from SerialDatabaseProvider
- Remove duplicate properties and methods already in base class
- Keep LanceDB-specific initialization (table references, CWD management)

### 2. Implement Required Abstract Methods
```python
def _create_connection(self) -> Any:
    """Create thread-local LanceDB connection"""
    # Handle CWD changes safely within executor thread
    # Return lancedb connection object
    
def _get_schema_sql(self) -> list[str] | None:
    """LanceDB doesn't use SQL - return None"""
    return None
```

### 3. Refactor Methods to Use Executor Pattern
Convert all database operations to _executor_* methods that run in DB thread:
- `_executor_connect()` - Initialize schema and tables
- `_executor_disconnect()` - Clean up connection
- `_executor_create_schema()` - Create files/chunks tables
- `_executor_search_semantic()` - Vector search operations
- `_executor_search_text()` - Text search operations
- `_executor_insert_file()` - File insertions
- `_executor_insert_chunk()` - Chunk insertions
- `_executor_insert_embeddings_batch()` - Bulk embedding updates
- All other database operations

### 4. Handle LanceDB-Specific Features
- **CWD Management**: Save/restore CWD within _create_connection()
- **Schema Recreation**: Preserve table recreation logic for embedding dimension changes
- **Data Corruption Recovery**: Keep optimize() calls and recovery mechanisms
- **No Transactions**: Keep begin/commit/rollback as no-ops

## Implementation Steps

### Phase 1: Update Class Declaration
```python
from providers.database.serial_database_provider import SerialDatabaseProvider

class LanceDBProvider(SerialDatabaseProvider):
    """LanceDB implementation using serial executor pattern."""
```

### Phase 2: Implement Abstract Methods
```python
def _create_connection(self) -> Any:
    import lancedb
    
    abs_db_path = self._db_path.absolute()
    
    # Save CWD (thread-safe in executor)
    original_cwd = os.getcwd()
    try:
        os.chdir(abs_db_path.parent)
        conn = lancedb.connect(abs_db_path.name)
        return conn
    finally:
        os.chdir(original_cwd)
```

### Phase 3: Convert Methods to Executor Pattern
Example transformation:
```python
# Before:
def search_semantic(self, query_embedding, ...):
    # Direct implementation
    
# After:
def _executor_search_semantic(self, conn, state, query_embedding, ...):
    # Implementation using conn parameter
```

### Phase 4: Remove Redundant Code
- Remove properties handled by base class (is_connected, db_path)
- Remove methods with default implementations in base
- Keep only LanceDB-specific logic

## Affected Components

### Direct Changes
- `/providers/database/lancedb_provider.py` - Main refactoring
- `/chunkhound/providers/database_factory.py` - No changes needed

### Indirect Impact
- All code using LanceDBProvider continues to work unchanged
- MCP server - No changes needed
- CLI tools - No changes needed
- Tests may need connection handling updates

## Testing Strategy

### Unit Tests
1. Connection creation in executor thread
2. CWD management correctness
3. Schema creation and table initialization
4. All search operations
5. Batch operations performance

### Integration Tests
1. Concurrent read operations still work
2. Write serialization prevents conflicts
3. Schema recreation handles dimension changes
4. Data corruption recovery works
5. File watching and incremental updates

### Performance Tests
1. Bulk insert performance maintained
2. Search latency acceptable
3. No thread contention issues

## Expected Benefits

1. **Consistency**: Same execution model as DuckDB
2. **Thread Safety**: Guaranteed serialization of writes
3. **Maintainability**: Less duplicate code
4. **Reliability**: Centralized error handling and timeouts
5. **Future-Proof**: Easy to add new providers

## Risks & Mitigations

### Risk 1: Performance Impact
- **Mitigation**: LanceDB already recommends batch operations; serial executor won't change this

### Risk 2: CWD Management Complexity
- **Mitigation**: Isolate CWD changes to _create_connection() only

### Risk 3: Breaking Existing Functionality
- **Mitigation**: Comprehensive test coverage before deployment

## Success Criteria

✅ All existing LanceDB tests pass  
✅ Thread safety verified with concurrent operations  
✅ No performance regression in benchmarks  
✅ CWD management works correctly  
✅ Schema recreation still functions  
✅ MCP integration unchanged