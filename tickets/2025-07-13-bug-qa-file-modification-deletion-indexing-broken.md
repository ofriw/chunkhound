# 2025-07-13T19:30:00+03:00 - [BUG] QA Testing Reveals Critical File Modification and Deletion Indexing Bugs
**Priority**: Urgent

Comprehensive QA testing of MCP search tools revealed critical bugs in file modification and deletion indexing. Both old and new content remain searchable after file edits, and deleted files persist in search index indefinitely.

## QA Test Evidence

### File Modification Bug
- **Created**: `test_qa_new_file.py` with `unique_qa_test_function` - indexed successfully
- **Modified**: Changed function name to `unique_qa_test_function_modified` and updated content
- **Result**: ❌ **Both old AND new content remain searchable**
- **Expected**: Old content removed, new content indexed
- **Actual**: Duplicate chunks persist indefinitely

### File Deletion Bug
- **Deleted**: Test files using `rm` command
- **Result**: ❌ **Deleted file content still returns in search results**
- **Expected**: All chunks and embeddings removed from index
- **Actual**: Ghost data persists pointing to non-existent files

### Search Examples
```bash
# After editing file function name:
search_regex("unique_qa_test_function")          # ❌ Still returns results (should be empty)
search_regex("unique_qa_test_function_modified") # ✅ Returns new content (correct)

# After deleting file:
search_regex("qa_unique_method_updated")         # ❌ Still returns results from deleted file
```

## Technical Analysis

### Root Cause: Chunk Cleanup Failure
1. **File Modification**: System adds new chunks but fails to remove old ones
2. **File Deletion**: System removes file records but leaves orphaned chunks
3. **Index Pollution**: Search results contain stale and duplicate data

### Impact Assessment
- **Development Workflow**: Misleading search results during active coding
- **Data Integrity**: Index becomes increasingly inconsistent over time  
- **User Experience**: Confusing results showing non-existent or outdated code
- **Performance**: Growing database with orphaned chunks

## Working Functionality
✅ **New file creation** - Works correctly (3-7 second indexing)
✅ **Multi-language support** - All 23+ languages index properly
✅ **Search performance** - Sub-second response times
✅ **Pagination** - Offset/limit controls work correctly
✅ **Concurrent operations** - Non-blocking search during edits

## Testing Methodology
- **Languages Tested**: Python, Java, C#, TypeScript, JavaScript, Go, Rust, Markdown
- **File Operations**: Create, edit (add/modify/delete content), delete files
- **Search Verification**: Both semantic and regex search tested
- **Timing**: 3-7 second waits between operations for indexing
- **Cleanup**: All test files removed after testing

## Required Fix
The system needs proper chunk cleanup logic that:
1. **During file modification**: Removes old chunks before adding new ones
2. **During file deletion**: Removes all chunks and embeddings for deleted files
3. **Ensures consistency**: Search results reflect actual filesystem state

## Workarounds
- **Manual cleanup**: Restart MCP server periodically to clear stale data
- **Fresh databases**: Delete database and re-index for clean state
- **Search validation**: Cross-check search results with filesystem

# History

## 2025-07-13T19:30:00+03:00
Created ticket based on comprehensive QA testing results. Both file modification and deletion indexing are broken, causing search index pollution with stale data.