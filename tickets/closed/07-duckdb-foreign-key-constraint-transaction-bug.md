# 2025-01-07 - [BUG] DuckDB Foreign Key Constraint Transaction Bug
**Priority**: High

DuckDB foreign key constraints fail within transactions even when referenced records are deleted, causing "Constraint Error: Violates foreign key constraint" errors during chunk updates.

## Problem

When updating existing files, the indexing coordinator wraps operations in a transaction for atomicity. During smart diff processing, it attempts to delete modified/removed chunks that have associated embeddings. Despite `_executor_delete_chunk` correctly deleting embeddings before chunks, DuckDB throws a foreign key constraint violation.

## Root Cause

1. **DuckDB Limitation**: DuckDB doesn't support CASCADE DELETE or deferred constraint checking
2. **Transaction Visibility Issue**: Within a transaction, DuckDB's FK constraint check doesn't recognize deletions made earlier in the same transaction
3. **Test Results**:
   - ✅ Delete embeddings → delete chunk **succeeds without transaction**
   - ❌ Delete embeddings → delete chunk **fails within transaction** (FK violation despite embeddings being deleted)

## Current Implementation

The code correctly handles deletion order:
```python
# providers/database/duckdb_provider.py:1150-1166
def _executor_delete_chunk(self, conn: Any, state: dict[str, Any], chunk_id: int) -> None:
    # Delete embeddings first to avoid foreign key constraint
    result = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE 'embeddings_%'
    """).fetchall()
    
    for (table_name,) in result:
        conn.execute(f"DELETE FROM {table_name} WHERE chunk_id = ?", [chunk_id])
    
    # Then delete the chunk
    conn.execute("DELETE FROM chunks WHERE id = ?", [chunk_id])
```

## Error Location

services/indexing_coordinator.py:263 - During smart diff processing of existing files:
```python
self._db.begin_transaction()
# ... smart diff logic ...
for chunk_id in chunk_ids_to_delete:
    self._db.delete_chunk(chunk_id)  # Fails here with FK constraint
```

## Research Findings

- DuckDB doesn't support `ON DELETE CASCADE` for automatic cascade deletions
- DuckDB doesn't support `DEFERRABLE INITIALLY DEFERRED` for deferred constraint checking
- This appears to be a DuckDB limitation/bug with FK constraint visibility within transactions

## Proposed Solution

Remove foreign key constraints from embedding tables since:
1. DuckDB can't cascade deletes automatically
2. Application already handles referential integrity correctly
3. Constraint checking within transactions is unreliable

Alternative solutions:
1. Execute chunk deletions outside of transactions (breaks atomicity)
2. Use raw SQL to drop/recreate constraints within transaction (complex)
3. Wait for DuckDB to add CASCADE DELETE support (not viable short-term)

## History

### 2025-01-07
- Discovered issue during CLI indexing with modified files
- Created test scripts confirming transaction visibility problem
- Research revealed DuckDB lacks CASCADE DELETE and deferred constraints
- Documented findings and proposed removing FK constraints as solution