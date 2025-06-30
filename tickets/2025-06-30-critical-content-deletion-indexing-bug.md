# 2025-06-30 - [CRITICAL] Content Deletion Not Reflected in Search Index

**Status**: Open  
**Priority**: Critical  
**Component**: Incremental Indexing  
**Discovered**: 2025-06-30 during QA testing  

## Issue Summary

When content is deleted from within existing files (functions, classes, methods), the deleted chunks persist in search results indefinitely. The incremental indexing system fails to remove stale chunks during file updates.

## Technical Details

### Reproduction Steps
1. Create file with function `test_function()`
2. Verify function appears in search results
3. Delete function from file, save
4. Wait 15+ seconds for indexing
5. Search for `test_function` - **still appears in results**

### Root Cause Analysis

Based on related tickets, this appears to be a **regression** in the chunk cleanup logic:

- **2025-06-22**: Fixed duplicate chunks with `delete_file_chunks()` cleanup
- **Current Issue**: Cleanup logic may not be triggered properly for file modifications

### Expected vs Actual Behavior

**Expected**: Deleted content disappears from search results within ~5 seconds  
**Actual**: Deleted content persists indefinitely in search results

### Related Issues

- **2025-06-22**: Similar issue with duplicate chunks - fixed with `IndexingCoordinator.process_file()` cleanup
- **2025-06-29**: Real-time indexing failures (resolved)
- **2025-06-27**: LanceDB chunk deletion performance issues

## Impact Assessment

**Severity**: Critical - Search results contain stale/deleted content  
**User Impact**: Misleading search results, code references to non-existent functions  
**Development Impact**: Unreliable for active development workflows

## Proposed Solution

1. **Investigate** `services/indexing_coordinator.py:156-193` cleanup logic 
2. **Verify** file modification detection triggers `delete_file_chunks()`
3. **Add** test coverage for content deletion scenarios
4. **Monitor** timing between file save and search index cleanup

## Test Cases Required

- [ ] Delete function from file - verify removal from search
- [ ] Delete class from file - verify removal from search  
- [ ] Delete multiple chunks from file - verify all removed
- [ ] Modify existing function - verify old version removed
- [ ] Performance test - measure cleanup timing

## Notes

This is a **regression** from previously working functionality. The existing `delete_file_chunks()` logic should handle this case but appears to not be triggered or working correctly for in-file content deletions.