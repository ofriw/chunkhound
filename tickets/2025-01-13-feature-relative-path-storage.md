# 2025-01-13 - [FEATURE] Relative Path Storage for Database Portability
**Priority**: High

Implemented relative path storage to make ChunkHound databases portable across machines, Docker containers, and team environments. Previously, ChunkHound stored absolute paths which made databases non-portable.

# History

## 2025-01-13T18:30:00+03:00

**FEATURE IMPLEMENTED - Relative Path Storage**

### Changes Made

1. **Added `base_dir` parameter to `IndexingCoordinator`**:
   - Defaults to current working directory or project root
   - Used for converting between absolute and relative paths
   - Passed through from registry configuration

2. **Updated path storage logic**:
   - `_store_file_record`: Converts absolute paths to relative before database storage
   - Files outside base directory store absolute paths with warning
   - Backwards compatibility: checks both relative and absolute paths during lookups

3. **Updated file operations**:
   - `remove_file`: Handles relative path lookups with fallback to absolute
   - `_cleanup_orphaned_files`: Works with both relative and absolute paths in database
   - File modifications now work correctly with relative paths

4. **Registry and factory updates**:
   - `create_indexing_coordinator`: Automatically determines base directory from config or project root
   - Base directory passed through all initialization paths (CLI, MCP, tests)

5. **MCP server enhancements**:
   - Added global `_base_directory` tracking
   - Added `convert_relative_paths_in_results()` function
   - Search results convert relative paths back to absolute for display
   - Both `search_regex` and `search_semantic` handle path conversion

### Benefits Achieved

- ✅ **Database portability**: Can share `.chunkhound/db` between team members
- ✅ **Docker support**: Database works correctly with volume mounts
- ✅ **CI/CD compatible**: Can cache and reuse databases across builds
- ✅ **Project relocation**: Move projects without re-indexing
- ✅ **Backwards compatible**: Existing databases with absolute paths continue to work

### Testing Results

Created comprehensive test (`test/test-relative-paths.py`) that confirms:
- Paths stored as relative (e.g., `src/file.py` instead of `/full/path/src/file.py`)
- Search functionality works with relative paths
- File modifications handled correctly
- Database remains portable

### Known Issues Discovered

1. **Chunk cleanup bug** (separate issue):
   - When files are modified, old chunks are not removed
   - New chunks are added alongside old ones
   - Results in duplicate/stale content in search results
   - This is NOT related to relative paths - it's a chunk diffing issue
   - Tracked in ticket: `2025-01-13-bug-chunk-cleanup-on-modification.md`

2. **File modification indexing** (partially fixed):
   - Original bug where files disappeared after modification is fixed
   - Files now remain in database with correct relative paths
   - However, chunk cleanup issue means old content persists

### Implementation Details

**Path Conversion Logic**:
```python
# Storage (absolute → relative)
try:
    relative_path = file_path.relative_to(self._base_dir)
    path_to_store = str(relative_path)
except ValueError:
    # File outside base directory
    path_to_store = str(file_path)

# Display (relative → absolute)
if not file_path.is_absolute():
    result['file_path'] = str(base_dir / file_path)
```

**Backwards Compatibility**:
- Database lookups try relative path first, then absolute
- Allows gradual migration of existing databases
- No breaking changes for existing installations

### Next Steps

1. Fix chunk cleanup bug (separate ticket)
2. Add migration tool for converting existing databases to relative paths
3. Update documentation to explain portable database benefits
4. Consider adding base directory override in configuration