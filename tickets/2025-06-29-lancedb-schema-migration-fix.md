# LanceDB Initial Schema Creation Bug - Variable-Size List Prevents Vector Search

**Date**: 2025-06-29  
**Priority**: High  
**Status**: Open  

## Issue
Semantic search via MCP fails with:
```
Error: Semantic search failed: Semantic search failed: lance error: LanceError(Index): Data type is not a vector (FixedSizeListArray or 
     List<FixedSizeListArray>), but Float32, /Users/runner/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/lance-0.30.0/src/index/vector/utils.rs:101:23
```

## Root Cause
The chunks table is created with the wrong schema on initial database creation. In `create_schema()` (line 156):
```python
self._chunks_table = self.connection.create_table("chunks", schema=get_chunks_schema())
```

The `get_chunks_schema()` is called WITHOUT the `embedding_dims` parameter:
- `embedding_dims` defaults to `None`
- Creates a variable-size list: `pa.list_(pa.float32())` (line 53)
- LanceDB vector search requires fixed-size lists: `pa.list_(pa.float32(), dims)`

## Why Previous Fix Didn't Work
The fix in `insert_embeddings_batch()` only helps during embedding insertion, but the table is already created with the wrong schema during initial setup.

## Solution
Since users can delete and re-index, we don't need complex migrations. Instead:

1. **Fix Initial Table Creation**: Create chunks table with a default fixed-size embedding schema (e.g., 1536 dimensions for OpenAI)
2. **Handle Dimension Mismatch**: The existing logic in `insert_embeddings_batch()` will recreate the table if dimensions don't match

## Workaround for Existing Users
Delete the LanceDB directory and re-index:
```bash
rm -rf chunkhound.lancedb/
chunkhound index /path/to/codebase
```

## Fix Applied
**File**: `providers/database/lancedb_provider.py:156`  
**Change**: Pass default embedding dimensions (1536) to `get_chunks_schema()` during initial table creation:
```python
# Before:
self._chunks_table = self.connection.create_table("chunks", schema=get_chunks_schema())

# After:
self._chunks_table = self.connection.create_table("chunks", schema=get_chunks_schema(1536))
```

This ensures new databases create chunks table with fixed-size embedding vectors (1536 dimensions for OpenAI text-embedding-3-small) that support vector search operations.

## Related Issues
- Previous partial fix: `2025-06-28-lancedb-vector-type-fix.md`