# LanceDB Premature Vector Index Creation

**Date**: 2025-06-28T20:04:24+03:00  
**Status**: Open  
**Priority**: High  
**Component**: LanceDB Provider  

## Issue
`chunkhound index` fails with repeated IVF PQ index creation errors:
```
Failed to create vector index for openai/text-embedding-3-small: Invalid input, An IVF PQ index cannot be created on the column `embedding` which has data type List(Field { name: "item", data_type: Float32, nullable: true, dict_id: 0, dict_is_ordered: false, metadata: {} })
```

## Root Cause
- **Insufficient data**: IVF PQ index requires adequate vectors for k-means clustering during training
- **Premature creation**: Index attempted after every batch (~100-300 chunks) in `insert_embeddings_batch:546`
- **Data type**: Nullable Float32 embedding column may not meet LanceDB requirements

## Location
`providers/database/lancedb_provider.py:546`

## Solution
Defer vector index creation until minimum data threshold (e.g., 1000+ embeddings) or completion of embedding generation phase.

## Impact
Prevents successful indexing, blocks semantic search functionality.