# 2025-06-29 - [BUG] LanceDB Path Corruption Fix
**Priority**: Critical

Fixed a critical issue where LanceDB was storing internal file references as relative paths, causing database corruption when accessed from different working directories.

## Problem

When running queries against LanceDB, users would see errors like:
```
RuntimeError: lance error: LanceError(IO): Execution error: Not found: Users/ofri/Documents/GitHub/chunkhound/chunkhound.lancedb/files.lance/data/5f8e92ad-e90a-4fe7-b435-4baaa5b98b9f.lance
```

Note the missing leading slash - LanceDB was looking for "Users/ofri/..." as a relative path instead of "/Users/ofri/..." as an absolute path.

## Root Cause

LanceDB internally stores references to its data files. If the database is created when the working directory is different from where it's later accessed, these internal references become invalid. This happened when:

1. The database was created with a certain working directory (possibly "/")
2. LanceDB stored internal data file paths relative to that directory
3. When accessed from a different working directory, the relative paths no longer resolved correctly

## Solution Implemented

1. **Ensure absolute paths**: Modified the LanceDB provider to always use `.absolute()` when constructing database paths
2. **Consistent working directory**: When connecting to LanceDB, temporarily change to the database's parent directory to ensure consistent relative path resolution
3. **Immediate restoration**: Restore the original working directory after connection to avoid affecting other code

### Code Changes

In `providers/database/lancedb_provider.py`:

1. Database path construction now ensures absolute paths:
```python
self._db_path = (Path(db_path).parent / f"{Path(db_path).stem}.lancedb").absolute()
```

2. Connection process manages working directory:
```python
# Save current directory
self._original_cwd = os.getcwd()

# Change to database parent for consistent paths
os.chdir(abs_db_path.parent)

# Connect using relative name
self.connection = lancedb.connect(abs_db_path.name)

# Restore original directory
os.chdir(self._original_cwd)
```

## Impact

- Prevents future database corruption from working directory changes
- Existing corrupted databases cannot be recovered and need to be re-indexed
- The fix ensures consistent behavior regardless of where ChunkHound is run from

## Lessons Learned

1. LanceDB's internal file management is sensitive to working directory context
2. Always use absolute paths when dealing with database locations
3. Consider the working directory context when using libraries that manage their own file structures
4. Database corruption can occur from seemingly innocent operations like changing directories

## Follow-up Actions

1. Users with corrupted databases need to re-index their codebases
2. Consider adding a database integrity check on startup
3. Document this behavior in LanceDB usage guidelines