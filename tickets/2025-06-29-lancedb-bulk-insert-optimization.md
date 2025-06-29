# LanceDB Bulk Insert Performance Optimization

## Issue
Embedding generation using LanceDB was taking an extremely long time due to inefficient bulk insert implementation.

## Root Cause
The `insert_embeddings_batch` method in `providers/database/lancedb_provider.py` was:
1. Reading the entire chunks table into memory
2. Updating records in Python
3. Dropping the entire table
4. Recreating the table with all data

This approach doesn't scale - for large tables, every embedding update required rewriting the entire dataset.

## Solution
Refactored to use LanceDB's `merge_insert` API:
- Uses efficient merge operations to update only the necessary records
- Maintains existing data and indexes
- Processes updates in configurable batches (default 10,000 records)
- Automatically adds embedding columns if they don't exist

## Implementation Details
```python
# Old approach - O(n) where n is total table size
all_data = self._chunks_table.search().limit(self._chunks_table.count_rows()).to_list()
# ... update in memory ...
self.connection.drop_table('chunks')
self._chunks_table = self.connection.create_table('chunks', data=pa_table)

# New approach - O(m) where m is update size
(
    self._chunks_table
    .merge_insert("id")
    .when_matched_update_all()
    .execute(merge_data)
)
```

## Performance Impact
- **Before**: Bulk insert time grows linearly with total table size
- **After**: Bulk insert time only depends on number of records being updated
- **Memory**: Reduced memory usage from O(n) to O(batch_size)

## Testing
The new implementation includes:
- Batch processing for very large updates (10k records per batch)
- Proper error handling and logging
- Automatic vector index creation when threshold is met (256+ embeddings)

## Status
Fixed - The bulk insert now uses LanceDB's native merge capabilities for efficient updates.