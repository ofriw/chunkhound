# 2025-06-29 - CRITICAL: DuckDB Checkpoint Failure Due to Disk Space

**Priority**: CRITICAL
**Status**: OPEN

## Summary
DuckDB checkpoint operation failed during embedding generation with "No space left on device" error. The database file has grown to 3.2GB and the disk is at 99-100% capacity. This causes a cascade failure where the database becomes permanently invalidated and all subsequent operations fail.

## Error Details
```
19:23:32 | WARNING  | Checkpoint failed: FATAL Error: Failed to create checkpoint because of error: Could not write file "/Users/ofri/Documents/GitHub/chunkhound/.chunkhound.db": No space left on device
19:23:32 | ERROR    | Failed to get all chunks with metadata: FATAL Error: Failed: database has been invalidated because of a previous fatal error. The database must be restarted prior to being used again.
```

## Root Cause Analysis

### 1. Disk Space Exhaustion
- System disk at 99-100% capacity (466Gi used, 279Mi available)
- Database file: 3.2GB
- WAL file: 605KB
- Corrupted WAL file marker: 0 bytes

### 2. DuckDB Checkpoint Behavior
- DuckDB uses Write-Ahead Logging (WAL) for durability
- Checkpoint operation writes WAL changes to main database file
- WAL typically triggers checkpoint at 16MB by default
- Checkpoint can reclaim space from deleted rows (requires ~25% adjacent deleted rows)
- No specific disk space requirement documented, but depends on database state
- When checkpoint fails due to fatal error, database becomes invalidated
- Database invalidation after fatal error requires restart to recover

### 3. Triggering Context
- Error occurred during bulk embedding generation (96% complete, ~10,200/10,606 chunks)
- Recent DuckDB provider refactoring (commit 908f1ce) extracted checkpoint logic to `connection_manager.py`
- Architecture fix (ticket 2025-06-29-architecture-db-provider-mismatch.md) may have changed initialization timing

### 4. Checkpoint Configuration
From `connection_manager.py`:
- Checkpoint threshold: 100 operations
- Time-based checkpoint: 300 seconds (5 minutes)
- Checkpoint called on disconnect and periodically during operations

## Impact
1. **Database Invalidation**: Once checkpoint fails, all subsequent operations fail
2. **Data Loss Risk**: Uncommitted changes in WAL may be lost
3. **Service Disruption**: ChunkHound becomes unusable until database is recovered
4. **Cascading Failures**: All database operations return "database has been invalidated" error

## Related Issues
- **DuckDB Provider Refactoring** (2025-06-29): Major refactor to repository pattern
- **Architecture DB Provider Mismatch** (2025-06-29): Fixed registry configuration timing
- **Thread Safety Fix** (2025-06-29): Fixed FileWatcher thread safety issues
- **Real-Time Indexing Failure** (2025-06-29): Fixed file watching initialization

## Immediate Actions Required
1. Free disk space (target: at least 10GB free)
2. Implement checkpoint size estimation before operations
3. Add disk space checks before bulk operations
4. Implement WAL size monitoring and alerts
5. Consider database size optimization strategies

## Long-term Solutions
1. **Implement Database Size Management**:
   - Periodic cleanup of old/unused embeddings
   - Compression strategies for embeddings table
   - Partitioning by date/project

2. **Checkpoint Strategy Improvements**:
   - Pre-flight disk space checks
   - Incremental checkpoints for large operations
   - Graceful degradation when disk space is low

3. **Monitoring & Alerts**:
   - Database size tracking
   - WAL size monitoring
   - Disk space alerts before critical threshold

4. **Configuration Options**:
   - Max database size limits
   - Configurable checkpoint frequency
   - Option to use external storage for embeddings

## Technical Details
- Database grows during bulk embedding operations
- Each embedding: ~1536-3072 dimensions (float32) = 6-12KB per vector
- 10,000 embeddings ≈ 60-120MB of raw data
- DuckDB overhead and indexes multiply actual storage requirements
- Checkpoint requires temporary space for atomic write operation