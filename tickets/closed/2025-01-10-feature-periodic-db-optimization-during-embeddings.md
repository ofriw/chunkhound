# 2025-01-10 - [FEATURE] Periodic DB Optimization During Embeddings Stage
**Priority**: High

Currently, DB optimization (compaction for LanceDB) only happens once at the end of the indexing process. For very large databases with millions of embeddings, this doesn't scale well and can lead to performance degradation during the embedding generation phase.

## Problem
- `optimize_tables()` is only called in `indexing_coordinator.py` after bulk directory processing
- During embedding generation, thousands of batches are inserted without any intermediate optimization
- LanceDB performance degrades with too many fragments (recommended: ~100 fragments until 1B rows)
- Large embedding operations can create thousands of fragments before optimization

## Proposed Solution
Add periodic optimization during the embeddings stage:
1. Track number of embedding batches inserted
2. Trigger optimization every N batches (configurable, default ~1000)
3. Ensure optimization doesn't interfere with batch processing

## Implementation Requirements
1. Add batch counter to `EmbeddingService._generate_embeddings_streaming()`
2. Add configurable threshold for optimization frequency
3. Call `optimize_tables()` periodically during embedding generation
4. Consider performance impact of optimization during processing
5. Make it provider-aware (LanceDB needs it, DuckDB doesn't)

## Affected Components
- `chunkhound/services/embedding_service.py`: Main implementation site
- `chunkhound/services/indexing_coordinator.py`: Current optimization call site
- `chunkhound/providers/database/lancedb_provider.py`: LanceDB optimization implementation
- Configuration: Add optimization frequency setting

## Expected Outcome
- Better performance for large-scale embedding operations
- Prevent excessive fragment accumulation
- Maintain query performance during long-running operations
- Configurable optimization frequency based on workload

## History

### 2025-07-10
Implemented periodic database optimization during embedding generation:

1. **Added batch tracking to EmbeddingService**: 
   - Added `optimization_batch_frequency` parameter (default: 1000 batches)
   - Tracks batch count in both `_generate_embeddings_streaming` and `_generate_embeddings_in_batches`
   - Calls `optimize_tables()` when batch count reaches frequency threshold

2. **Made it provider-aware**:
   - Only runs optimization if database provider has `optimize_tables()` method
   - LanceDB benefits from this optimization (compaction)
   - DuckDB doesn't require it but method exists as no-op

3. **Added configuration support**:
   - Added `optimization_batch_frequency` to `EmbeddingConfig` (0-10000, default 1000)
   - Updated registry to pass configuration to EmbeddingService
   - Can be configured via environment variable: `CHUNKHOUND_EMBEDDING_OPTIMIZATION_BATCH_FREQUENCY`

4. **Tested the implementation**:
   - Verified optimization is called at correct intervals
   - Confirmed it can be disabled by setting frequency to 0
   - Works correctly with concurrent batch processing

The feature is now ready for use and will improve performance for large-scale embedding operations by preventing excessive fragment accumulation in LanceDB.