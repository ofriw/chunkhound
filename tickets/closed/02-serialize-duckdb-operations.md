# 2025-08-02 - [COMPLETED] Serialize DuckDB Operations

**Status**: Completed  
**Problem**: MCP server had database duplication due to concurrent thread-local cursors  
**Solution**: Implemented single-threaded executor pattern for all DuckDB operations

## Changes Made

### DuckDBProvider (`/providers/database/duckdb_provider.py`)
1. Added `ThreadPoolExecutor(max_workers=1)` for single-threaded execution
2. Implemented thread-local storage with `_executor_local` for connection state
3. Created `_execute_in_db_thread()` and `_execute_in_db_thread_sync()` wrapper methods
4. Converted all database operations to use executor pattern:
   - All search methods: `search_semantic`, `search_regex`, `search_text`
   - Index operations: `create_vector_index`, `drop_vector_index`, `get_existing_vector_indexes`
   - Transaction methods: `begin_transaction`, `commit_transaction`, `rollback_transaction`
   - Stats and queries: `get_stats`, `execute_query`
   - Schema operations: `connect`, `disconnect`, `create_schema`, `create_indexes`

### ConnectionManager (`/providers/database/duckdb/connection_manager.py`)
1. Removed thread-local cursor code and connection locks
2. Deprecated `get_thread_safe_connection()` method
3. Removed `_connect_with_mcp_safety()` method
4. Simplified to basic connection management only

## Key Implementation Details
- Connection created lazily in executor thread via `_get_thread_local_connection()`
- Complete state isolation - no connection objects exist outside executor
- Repository classes unchanged - all operations delegated through provider
- Maintains backward compatibility with existing API

## Additional Changes

### CLI Warning Fix
Converted direct repository delegations to use executor pattern:
- File operations: `insert_file`, `get_file_by_path`, `update_file`
- Chunk operations: `insert_chunks_batch`, `get_chunks_by_file_id`, `delete_file_chunks`
- Embedding operations: `get_existing_embeddings`, `insert_embeddings_batch`, `get_all_chunks_with_metadata`

This eliminates "_get_connection called - should use executor methods" warnings during CLI operations.

### Model Compatibility Fixes
- **File Model**: Updated `_executor_insert_file` to handle attributes correctly (`size_bytes` not `size`)
- **Chunk Model**: Fixed `_executor_insert_chunks_batch` to calculate size from code length
- Added logic to check for existing files and update instead of insert
- Fixed timestamp conversion using `to_timestamp()` for `modified_time` field
- Used `getattr()` for optional attributes like `signature`

## Verification
- Tested with 5 concurrent file processing tasks
- No duplicate chunks detected in database
- All operations properly serialized through executor
- CLI operations run without warnings

## History

### 2025-07-02
**Fixed KeyError 'id' in embedding generation**
- Root cause: DuckDB returns `chunk_id`, embedding service expected `id`
- Fix: Updated `services/embedding_service.py`:
  - `_get_chunk_ids_without_embeddings` (L499): `chunk.get('chunk_id', chunk.get('id'))`
  - `_get_chunks_by_ids` (L609-613): Same pattern for compatibility
- Result: Works with both DuckDB (`chunk_id`) and other providers (`id`)

**Fixed TypeError 'size' in Chunk model (2nd run only)**
- Root cause: Divergent code path - 1st run returns empty list, 2nd run loads DB data
- DB schema has `size` and `signature` columns, but Chunk model doesn't have these fields
- Temporary fix: Removed `size` and `signature` from Chunk constructor in `_executor_get_chunks_by_file_id`

**Implemented proper fix: Schema-Model alignment**
- Removed unused columns from schema definition:
  - `connection_manager.py` (L393-408): Updated CREATE TABLE chunks
  - `duckdb_provider.py` (L487-502): Updated CREATE TABLE chunks
  - `duckdb_provider.py` (L1044-1067): Updated SELECT statement and row mapping
- Added migration for existing databases:
  - `connection_manager.py` (L454-525): `_migrate_schema()` drops unused columns
  - Recreates table without `size` and `signature` columns
  - Preserves existing data and recreates indexes
- Benefits: Single source of truth, no divergent code paths, prevents future bugs

**Fixed INSERT statement crash**
- Found INSERT still using removed columns in `_executor_insert_chunks_batch`
- Updated bulk insert to match new schema:
  - Removed `size` and `signature` from chunk_data tuple (L979-992)
  - Updated temp table schema (L994-1007) 
  - Fixed placeholder count in INSERT (L1011)
  - Updated INSERT column list (L1016-1017)
- Now works for both initial indexing and re-indexing

### 2025-07-02 - WAL Corruption "Catalog 'chunkhound' does not exist"

**Root Cause**: DuckDB infers catalog name from filename during corrupted WAL replay
- Not from code - only 1 ATTACH site with explicit alias `recovery_db`
- Happens when process killed during transaction, WAL contains partial references

**Fixes Applied**:
1. **Connection Order** (`duckdb_provider.py`):
   - Changed: Connection manager validates WAL BEFORE executor creates connection
   - Fixed: `_get_thread_local_connection()` now reuses validated connection
   
2. **Delete Operations** (`duckdb_provider.py`):
   - Added: `_executor_delete_chunk()` - deletes embeddings first, then chunk
   - Fixed: Foreign key constraint errors (DuckDB doesn't support CASCADE)
   
3. **Call Sites Updated**:
   - `delete_chunk()` now uses executor pattern
   - No more direct `_get_connection()` calls

**Results**:
- ✅ WAL corruption handled gracefully
- ✅ No "_get_connection" warnings  
- ✅ No foreign key errors
- ✅ All files process successfully

**Architecture Debt**: Duplicate connection logic between provider and connection manager needs refactoring.