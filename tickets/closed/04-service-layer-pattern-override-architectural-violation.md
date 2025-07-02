# Service Layer Pattern Override Architectural Violation

**Date**: 2025-01-04  
**Priority**: High  
**Type**: Architecture Bug  
**Status**: Fixed  

## Problem

Service layer (`IndexingCoordinator._discover_files()`) violates architectural boundaries by overriding configuration decisions, creating inconsistent language support across execution paths.

## Root Cause

**Dual Pattern Systems**:
1. **Config Layer**: Limited patterns `['**/*.py', '**/*.md', '**/*.js', '**/*.ts', '**/*.tsx', '**/*.jsx']`
2. **Service Layer**: Complete patterns from `Language.get_all_extensions()` (all 16 languages)

**Inconsistent Activation**:
- **CLI Path**: Always provides config patterns → Service override never triggers → 5/16 languages fail
- **MCP Path**: Explicitly passes `patterns=None` → Service override triggers → All 16 languages work

## Code Evidence

**Service Layer Override** (`services/indexing_coordinator.py:848`):
```python
if not patterns:  # 🚨 ARCHITECTURAL VIOLATION
    patterns = []
    for ext in Language.get_all_extensions():
        patterns.append(f"*{ext}")
```

**CLI Always Provides Patterns** (`run.py:218`):
```python
if config.indexing.include_patterns:  # Always true (default_factory)
    include_patterns = config.indexing.include_patterns
```

**MCP Explicitly Passes None** (`periodic_indexer.py:282`):
```python
patterns=None,  # Triggers service override
```

## Architectural Violations

1. **Interface Contract Violation**: Service claims to process given patterns but secretly overrides them
2. **Separation of Concerns**: Service layer making configuration decisions
3. **Hidden Coupling**: Service depends on Language enum and config system
4. **Duplicate Responsibility**: Three layers all resolving patterns differently

## Impact

- **CLI Users**: 31% language failure rate (5/16 languages broken)
- **MCP Users**: 0% language failure rate (all languages work)
- **Debugging**: Unpredictable behavior based on execution path
- **Maintenance**: Multiple pattern resolution points out of sync

## Fix Strategy

1. **Remove service layer override** - service should only process given patterns
2. **Fix config layer** - include complete Language.get_all_extensions() in default patterns
3. **Centralize pattern resolution** - single source of truth for default patterns
4. **Enforce interface contracts** - service behavior must be predictable from interface

## Files Affected

- `services/indexing_coordinator.py` (remove override)
- `chunkhound/core/config/unified_config.py` (fix default patterns)
- `chunkhound/api/cli/commands/run.py` (rely on config layer)
- `chunkhound/periodic_indexer.py` (remove explicit None)

## Expected Outcome

Consistent 16/16 language support across all execution paths with proper architectural boundaries.

# History

## 2025-01-04

**Fixed** - Implemented complete architectural fix to remove service layer pattern override.

### Changes Made:

1. **Configuration Layer** (`chunkhound/core/config/unified_config.py`):
   - Added `_get_default_include_patterns()` function that uses `Language.get_all_extensions()`
   - Changed default patterns from hardcoded 6 languages to all 16 supported languages
   - Single source of truth for default file discovery patterns

2. **Service Layer** (`services/indexing_coordinator.py`):
   - Removed pattern override logic (lines 848-854)
   - Added validation to fail fast if patterns not provided
   - Service now respects interface contract and processes exactly what it's given

3. **MCP/Periodic Caller** (`chunkhound/periodic_indexer.py`):
   - Changed from `patterns=None` to `patterns=config.indexing.include_patterns`
   - No longer relies on service layer override

4. **CLI Layer** (`chunkhound/api/cli/commands/run.py`):
   - Removed duplicate pattern resolution logic
   - Simplified to trust config layer for complete patterns

### Result:
- Clean architectural boundaries restored
- Service layer no longer makes configuration decisions
- All execution paths use same pattern resolution
- Interface contracts are predictable and enforced

### Discovered Issue:
During testing, found unrelated foreign key constraint bug when updating chunks for modified files. This is tracked separately and doesn't affect the pattern resolution fix.