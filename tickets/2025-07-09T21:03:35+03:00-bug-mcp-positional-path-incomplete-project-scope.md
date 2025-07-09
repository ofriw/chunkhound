# 2025-07-09T21:03:35+03:00 - [BUG] MCP Positional Path Argument Incomplete Project Scope Control

**Priority**: High

## Description

The MCP command positional path argument `chunkhound mcp <path>` only controls watch paths but fails to set the complete project scope. This is a critical design flaw that breaks the user's expectation of project-wide control.

## Current Behavior

When running `chunkhound mcp /some/project`, only the watch paths are set to `/some/project`. The system still:
- Uses default database path (not `/some/project/.chunkhound/db`)
- Searches for config files in current directory (not `/some/project/.chunkhound.json`)
- Uses current directory for project root detection in other components

## Expected Behavior

`chunkhound mcp <path>` should control the **entire project scope**:
- Database location: `<path>/.chunkhound/db`
- Config file search: `<path>/.chunkhound.json`
- Watch paths: `<path>`
- Project root for all operations: `<path>`

## Root Cause

### Technical Issues

1. **Parser Conflict**: Two different `add_mcp_subparser` functions exist:
   - `chunkhound/api/cli/parsers/mcp_parser.py` - Has path argument ✅
   - `chunkhound/api/cli/commands/mcp.py` - Missing path argument ❌

2. **Limited Implementation**: In `mcp.py:28-30`, path only converts to `--watch-path`:
   ```python
   if hasattr(args, 'path') and args.path != Path("."):
       cmd.extend(["--watch-path", str(args.path.resolve())])
   ```

3. **No Project Scope Control**: Missing logic to set:
   - `CHUNKHOUND_DB_PATH` environment variable
   - Config file search directory
   - Project root context

## Impact

- User confusion: `chunkhound mcp /project` doesn't work as expected
- Inconsistent behavior: Database and config remain in current directory
- Broken deployment scenarios: Can't properly isolate project scopes

## Solution Requirements

1. **Unified Project Scope**: Make `<path>` argument control all project aspects
2. **Environment Variables**: Set both `CHUNKHOUND_DB_PATH` and `CHUNKHOUND_WATCH_PATHS`
3. **Config Search**: Update config system to search in `<path>` directory
4. **Working Directory**: Change to `<path>` for consistent project context

## Files to Modify

- `chunkhound/api/cli/commands/mcp.py` - Add complete project scope control
- `chunkhound/core/config/config.py` - Update config file search logic
- `mcp_launcher.py` - Handle project scope environment variables

# History

## 2025-07-09T21:03:35+03:00

Issue identified during investigation of CLI argument handling. The positional path argument exists but only controls watch paths, not the complete project scope as users expect.

## 2025-07-09T21:06:14+03:00

**FIXED**: Implemented complete project scope control for positional path argument.

**Changes Made**:

1. **Updated `mcp.py`** - Enhanced positional path argument handling:
   - Sets database path to `<path>/.chunkhound/db` if not explicitly provided
   - Sets watch path to `<path>` 
   - Sets `CHUNKHOUND_PROJECT_ROOT` environment variable for config search
   - Maintains backward compatibility with explicit `--db` argument

2. **Updated `config.py`** - Enhanced config file search:
   - Checks `CHUNKHOUND_PROJECT_ROOT` environment variable first
   - Falls back to existing `target_dir` logic
   - Searches for `.chunkhound.json` in project directory

**Testing Results**:
- ✅ `chunkhound mcp /tmp/test-project` sets database to `/tmp/test-project/.chunkhound/db`
- ✅ Config file search works in project directory
- ✅ Watch paths set correctly to project directory
- ✅ Complete project scope control achieved

**Resolution**: The positional path argument now controls the entire project scope as expected. Users can run `chunkhound mcp <path>` and everything (database, config, watch paths) will be scoped to that directory.