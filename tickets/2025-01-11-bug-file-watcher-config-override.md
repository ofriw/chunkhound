# 2025-01-11 - [BUG] File Watcher Ignores Environment Variable Configuration
**Priority**: Medium

The file watcher in MCP server uses `Config(target_dir=project_root)` which can override environment variables with JSON config values, inconsistent with the fix applied elsewhere.

## Issue
Line 687 in `mcp_server.py` creates a new Config instance with target_dir:
```python
config = Config(target_dir=project_root)
```

This will load `.chunkhound.json` from the project root and potentially override environment variables set by the MCP launcher, which violates the configuration precedence rules.

## Expected Behavior
Environment variables should always take precedence over JSON config files, as fixed in the main initialization path.

## Current Code (line 687)
```python
# Create a new config instance with target_dir to detect .chunkhound.json
config = Config(target_dir=project_root)
exclude_patterns = config.indexing.exclude or []
```

## Suggested Fix
```python
# Use the global config or create without target_dir to respect env vars
config = Config()  # This respects environment variables
exclude_patterns = config.indexing.exclude or []
```

## Impact
- File watcher might use different exclude patterns than configured via environment
- Inconsistent behavior between main server config and file watcher config
- Could cause confusion when debugging why certain files are/aren't being watched

## Related Context
- The main server initialization was fixed to use `Config()` without target_dir
- This ensures environment variables take precedence as intended
- The file watcher code appears to have been missed in that fix

# History

## 2025-01-11
Initial documentation during investigation of MCP TaskGroup crash.

## 2025-01-11 - Investigation and Fix Applied
Investigated the bug and applied fix. Key findings:

### Investigation Results
1. **Config Behavior Analysis**: The Config class does attempt to preserve environment variables even with `target_dir` set (lines 87-88 in config.py restore env vars after loading .chunkhound.json)
2. **Deep Merge Issue**: The `_deep_merge` method only performs deep merging for nested dictionaries. For lists (like exclude patterns), it replaces rather than merges values
3. **Consistency Concern**: Creating a new Config instance in file watcher is inconsistent with main server pattern (line 178 uses `Config()` without target_dir)

### Testing Performed
- Created test scenarios to verify config precedence behavior
- Confirmed that while env vars are technically preserved, having separate Config instances could lead to future inconsistencies
- Verified that main server uses `Config()` pattern consistently

### Fix Applied
Changed `mcp_server.py` lines 693-696:
```python
# Before:
project_root = find_project_root()
config = Config(target_dir=project_root)

# After:
config = Config()  # Respects environment variables
```

Also removed unused `find_project_root` import.

### Verification
- Created tests showing both main server and file watcher now use identical configuration
- Environment variables are consistently respected
- No immediate issues found, but needs real-world testing

### Still To Do
- Test with actual MCP server running via Docker/Ubuntu setup
- Verify file watcher behavior with real file modifications
- Check if there are any edge cases where project root detection was needed