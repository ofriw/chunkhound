# Python Parser CLI/MCP Divergence Issue

**Status**: ✅ RESOLVED  
**Priority**: High  
**Type**: Architecture Bug

## Problem

Python parser works in CLI mode but has bugs in MCP mode, despite using identical `PythonParser` class.

## Root Cause

**Duplicate Responsibility**: Both registry and `Database.__init__()` manage parser lifecycle, creating divergent initialization paths.

### Code Paths
- **CLI**: `configure_registry() → create_indexing_coordinator()` (direct)
- **MCP**: `configure_registry() → Database.__init__() → create_indexing_coordinator()` (indirect)

### Issue Location
`Database.__init__()` creates IndexingCoordinators in both exception branches:
```python
try:
    existing_provider = registry.get_provider("database")
    self._indexing_coordinator = create_indexing_coordinator()  # Path 1
except ValueError:
    # create new provider...
    self._indexing_coordinator = create_indexing_coordinator()  # Path 2
```

## Impact

Same parser code behaves differently due to:
- Different initialization timing
- Different registry states
- Different configuration contexts

## Solution

**Dependency Injection Cleanup**: Remove coordinator creation from `Database.__init__()`

### Approach
1. Create unified factory pattern for both CLI/MCP
2. Move all component creation to registry/factory
3. Make Database a pure consumer of injected dependencies
4. Eliminate dual initialization paths

### Implementation
```python
# Replace Database.__init__() creation logic with:
def create_database_with_dependencies(config) -> Database:
    configure_registry(config)
    coordinator = create_indexing_coordinator()  # Single creation point
    return Database(coordinator)  # Inject dependency
```

## Files Affected
- `chunkhound/database.py:50-116` (Database.__init__)
- `chunkhound/api/cli/commands/run.py:92` (CLI path)
- `chunkhound/mcp_server.py:234` (MCP path)
- `registry/__init__.py:165-187` (create_indexing_coordinator)

# History

## 2025-01-02T15:30:00-08:00
**Fixed design flaw** by eliminating circular dependency through proper separation of concerns.

### Design Problem Identified:
- **Circular dependency**: `registry` ↔ `chunkhound.database`
- **Misplaced responsibility**: Registry was creating Database instances
- **Runtime import hacks**: Required workarounds that indicated architectural issues

### Proper Solution Applied:

1. **Created dedicated factory module** (`chunkhound/database_factory.py`):
   - Single-purpose module for Database creation
   - Imports both registry and database without circular dependency
   - Serves as composition root for dependency injection

2. **Updated import paths**:
   - CLI: `chunkhound/api/cli/commands/run.py:20`
   - MCP: `chunkhound/mcp_server.py:46,60`
   - Both now import from `chunkhound.database_factory`

3. **Cleaned registry** (`registry/__init__.py`):
   - Removed factory function that caused circular dependency
   - Eliminated runtime imports and TYPE_CHECKING workarounds
   - Restored registry to its proper responsibility scope

### Result:
- ✅ **Eliminates circular dependency** - Clean module separation
- ✅ **Proper separation of concerns** - Registry manages providers, factory creates Database
- ✅ **Identical initialization paths** - Both CLI and MCP use same factory
- ✅ **Consistent parser behavior** - Same parsers, same configuration, same timing
- ✅ **Better architecture** - No runtime import hacks, proper composition root pattern