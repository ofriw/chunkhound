# 2025-06-29 - [BUG] LanceDB Real-time Indexing Performance Fix
**Priority**: High

Fixed slow real-time indexing with LanceDB where file changes took 20+ seconds to become searchable.

# History

## 2025-06-29
Root cause identified: LanceDB provider was calling non-existent `process_file_incremental` method on IndexingCoordinator, which caused a silent failure. This meant embeddings were never generated during real-time file updates, only during batch processing.

### What was done:
1. Fixed LanceDB provider to call `process_file(file_path, skip_embeddings=False)` instead of the non-existent `process_file_incremental` method
2. This ensures embeddings are generated immediately when files are modified
3. The bulk insert optimization using `merge_insert` with 10k batch sizes is already optimal per LanceDB docs

### Why it didn't work before:
- The code was trying to call a method that doesn't exist on IndexingCoordinator
- No embeddings were generated during real-time updates
- Files had to wait for batch `generate_missing_embeddings` to be searchable

### What we learned:
- LanceDB bulk insert is already optimized with proper batch sizes (10k)
- The issue was not with bulk inserts but with missing real-time embedding generation
- File changes are processed as LOW priority which may contribute to delays

### What work is still left:
- Consider raising file change priority from LOW to MEDIUM for better responsiveness
- Add configuration option for real-time embedding batch size (currently uses same as bulk)
- Monitor performance to ensure the fix resolves the 20+ second delays