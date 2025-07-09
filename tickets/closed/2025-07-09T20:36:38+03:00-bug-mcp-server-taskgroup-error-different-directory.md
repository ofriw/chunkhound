# 2025-07-09T20:36:38+03:00 - [BUG] MCP Server TaskGroup Error When Running from Different Directory

**Priority**: High

## Description

When running the MCP server in Ubuntu pointing it at a directory other than the current working directory, it fails with a TaskGroup error:

```json
{
  "jsonrpc": "2.0", 
  "id": null, 
  "error": {
    "code": -32603, 
    "message": "MCP server error", 
    "data": {
      "details": "unhandled errors in a TaskGroup (1 sub-exception)", 
      "suggestion": "Check that the database path is accessible and environment variables are correct."
    }
  }
}
```

## Root Cause

**Path Resolution Mismatch**: The issue occurs due to inconsistent path resolution between different MCP server components when launched from a directory other than the project root.

### Technical Details

1. **Directory Change in Launcher**: `mcp_launcher.py:109` changes CWD to watch path: `os.chdir(watch_path)`

2. **Hardcoded CWD Usage**: `mcp_server.py:389` hardcodes periodic indexer base directory:
   ```python
   base_directory = Path(os.getcwd())
   ```

3. **Environment Variable Mismatch**: 
   - `FileWatcherManager` correctly uses `CHUNKHOUND_WATCH_PATHS` environment variable
   - `PeriodicIndexManager` ignores environment and uses `os.getcwd()` directly

4. **TaskGroup Synchronization Failure**: Creates scenario where:
   - Database initialized for project root
   - File watcher monitors correct paths from `CHUNKHOUND_WATCH_PATHS`
   - Periodic indexer scans wrong directory (`os.getcwd()`)
   - Async tasks fail due to path mismatches

## Affected Components

- `mcp_launcher.py:105-109` - Directory change logic
- `mcp_server.py:389` - Hardcoded `Path(os.getcwd())`
- `PeriodicIndexManager.from_environment()` - Path resolution
- `FileWatcherManager` - Works correctly with environment variables

## Impact

- MCP server fails when launched from different directory
- Ubuntu deployment affected
- TaskGroup async coordination breaks
- Server unusable in non-root directory scenarios

## Solution Requirements

Make `PeriodicIndexManager.from_environment()` respect the same path resolution logic as `FileWatcherManager`:

1. Use `CHUNKHOUND_WATCH_PATHS` environment variable
2. Fall back to project root detection if not set
3. Ensure all components operate on same directory structure
4. Maintain consistency with existing file watcher behavior

## Files to Modify

- `chunkhound/mcp_server.py` - Line 389 path resolution
- `chunkhound/periodic_indexer.py` - `from_environment()` method
- Test with different directory launch scenarios

# History

## 2025-07-09T20:36:38+03:00

Issue identified through investigation of TaskGroup error. Root cause traced to path resolution mismatch between periodic indexer and file watcher components. Solution requires making periodic indexer respect same environment variable path resolution as file watcher.

## 2025-07-09T21:08:00+03:00

**FIXED**: Updated `PeriodicIndexManager.from_environment()` to use the same path resolution logic as `FileWatcherManager`:

1. **Made base_directory optional** - Now defaults to `None` and gets resolved using environment variables
2. **Added CHUNKHOUND_WATCH_PATHS support** - Uses same environment variable as file watcher
3. **Removed hardcoded Path(os.getcwd())** - From mcp_server.py initialization
4. **Uses project_detection utility** - Falls back to proper project root detection

**Changes Made**:
- `chunkhound/periodic_indexer.py`: Updated `from_environment()` method to use same path resolution as FileWatcherManager
- `chunkhound/mcp_server.py`: Removed hardcoded `base_directory = Path(os.getcwd())` 

**Testing**: Verified both default behavior (project root detection) and environment variable override work correctly.

**Status**: RESOLVED - Both components now use consistent path resolution logic, fixing TaskGroup error.