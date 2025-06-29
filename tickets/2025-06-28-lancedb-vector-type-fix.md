# LanceDB Vector Type Error Fix

**Date**: 2025-06-28  
**Priority**: High  
**Status**: Resolved  

## Issue
Semantic search was failing with the error:
```
lance error: LanceError(Index): Data type is not a vector (FixedSizeListArray or List<FixedSizeListArray>), but Float32
```

## Root Cause
LanceDB requires embeddings to be stored as fixed-size lists for vector search operations. The issue occurred during the `insert_embeddings_batch` method where:

1. **Schema Mismatch**: The PyArrow schema defined embeddings as variable-size lists `pa.list_(pa.float32())` instead of fixed-size lists `pa.list_(pa.float32(), dims)`
2. **Table Recreation Issue**: When updating embeddings, the table was recreated from pandas DataFrame which lost the proper list structure
3. **Type Conversion**: Pandas/numpy arrays weren't properly converted back to PyArrow's expected list format

## Investigation
1. Created test scripts to isolate the issue
2. Discovered that even fresh tables with variable-size lists fail vector search
3. Found that LanceDB requires fixed-size lists for vector operations
4. Identified the schema mismatch during table recreation in `insert_embeddings_batch`

## Solution Implemented

### 1. Updated Schema Function (lines 42-69)
```python
def get_chunks_schema(embedding_dims: int | None = None) -> pa.Schema:
    """Get PyArrow schema for chunks table.
    
    Args:
        embedding_dims: Number of dimensions for embedding vectors.
                       If None, uses variable-size list (which doesn't support vector search)
    """
    # Define embedding field based on whether we have fixed dimensions
    if embedding_dims is not None:
        embedding_field = pa.list_(pa.float32(), embedding_dims)  # Fixed-size list
    else:
        embedding_field = pa.list_(pa.float32())  # Variable-size list
```

### 2. Rewrote insert_embeddings_batch (lines 514-609)
- Detects embedding dimensions from first embedding
- Uses fixed-size schema when recreating table
- Properly converts numpy arrays to Python lists
- Creates vector index only when sufficient data exists (256+ rows)
- Better error handling with fallback approaches

### 3. Fixed Other Methods
- Updated `get_existing_embeddings` to handle list embeddings properly
- Fixed `get_stats` to check embeddings correctly
- Added proper numpy array handling throughout

## Key Changes
1. **Dynamic Schema**: Schema now adapts to actual embedding dimensions
2. **Proper Type Conversion**: Ensures embeddings are always Python lists
3. **Index Creation**: Only creates index with sufficient data (256+ rows minimum)
4. **Error Handling**: Better fallbacks and error messages

## Testing
Created comprehensive test script that:
- Creates files and chunks
- Inserts embeddings with proper dimensions
- Verifies semantic search works correctly
- All tests pass successfully

## Result
Semantic search now works correctly with LanceDB, returning proper results with distance metrics.

## Lessons Learned
1. **Vector Database Requirements**: Different vector databases have specific schema requirements
2. **Type Systems**: Careful attention needed when converting between pandas/numpy/PyArrow types
3. **Schema Evolution**: Vector databases may require schema recreation for updates
4. **Testing**: Direct testing with minimal examples helps isolate complex issues

## Related Files
- `providers/database/lancedb_provider.py` (main fix)
- Previous ticket: `2025-06-28-semantic-search-empty-results.md`