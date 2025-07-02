# 2025-08-01 - [BUG] MCP Server Database Duplication
**Priority**: Urgent

MCP server duplicates database entries due to shared transaction state across concurrent async tasks. The `_in_transaction` instance variable in DuckDBProvider is shared between all async operations, breaking transaction isolation.

**Status**: FIXED

# History

## 2025-08-01 - Root Cause
- Instance `_in_transaction` shared across async tasks
- Task A and B use same connection during transactions
- Breaks atomicity, causes duplicate chunks

## 2025-08-01 - Fix Applied
**Solution**: Used `contextvars` for task-local transaction state

**Code changes in `providers/database/duckdb_provider.py`**:
```python
# Added at module level
import contextvars
_transaction_context = contextvars.ContextVar('transaction_active', default=False)

# Updated methods
_get_connection(): Check _transaction_context.get() instead of self._in_transaction
begin_transaction(): Set _transaction_context.set(True)
commit_transaction(): Set _transaction_context.set(False) in finally block
rollback_transaction(): Set _transaction_context.set(False) in finally block
```

**Removed**:
- All `self._in_transaction` references from DuckDBProvider
- No backward compatibility - old code will crash early

**Result**: Each async task has isolated transaction state. No more duplications.