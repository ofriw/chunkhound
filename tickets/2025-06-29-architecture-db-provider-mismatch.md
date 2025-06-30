# 2025-06-29 - Architecture Issue: DB Provider Instantiation Mismatch Between Index and MCP Flows

## Summary
DB-related bugs fixed in `index` flow reappear in `mcp` flow. Root cause: registry configuration timing issue.

## Root Cause
MCP flow had a race condition where:
1. Config loading could fail inside try-except
2. Registry configuration was skipped on config failure
3. Database created without proper registry config
4. Provider initialized with defaults, not unified config

## Fix Applied
Restructured MCP server initialization in `mcp_server.py`:

```python
# BEFORE: Registry config inside try-except (could be skipped)
try:
    unified_config = ChunkHoundConfig.load_hierarchical()
    # ... embedding setup ...
    registry_config = _build_mcp_registry_config(unified_config, db_path)
    configure_registry(registry_config)
except:
    # Registry never configured!
    pass
_database = Database(db_path)  # Uses defaults

# AFTER: Registry ALWAYS configured before Database
try:
    unified_config = ChunkHoundConfig.load_hierarchical()
except:
    unified_config = ChunkHoundConfig()  # Fallback

# Registry configured OUTSIDE try-except
registry_config = _build_mcp_registry_config(unified_config, db_path)
configure_registry(registry_config)

# Database created with proper config
_database = Database(db_path, embedding_manager=_embedding_manager, config=unified_config.database)
```

## Key Changes
1. Config loading separated from registry configuration
2. Registry ALWAYS configured before Database creation
3. Database receives explicit config parameter
4. No race condition possible

## Status
✅ FIXED - Both flows now use identical initialization order

## Related Issues
- **2025-06-29-critical-duckdb-disk-space-checkpoint-failure.md**: This fix may have exposed checkpoint timing issues during bulk operations. The proper configuration now ensures checkpoints are triggered correctly, but this revealed disk space constraints that cause checkpoint failures.