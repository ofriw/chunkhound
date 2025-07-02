# Parser Limitations - QA Findings

**Date**: 2025-07-02  
**Type**: Bug Report  
**Priority**: Low  

## Issue
Three parsers have limited functionality affecting search results during QA testing.

## Affected Parsers

### C Parser (`c_parser.py`)
- **Files indexed**: ✅ 
- **Functions parsed**: ❌
- **Impact**: Function content not searchable
- **Test case**: `char* test_method()` not found in regex search

### Bash Parser (`bash_parser.py`) 
- **Files indexed**: ✅
- **Basic structure**: ✅ 
- **Function content**: ❌
- **Impact**: Function bodies not searchable
- **Test case**: `function test_method() { echo "content"; }` content not found

### Makefile Parser (`makefile_parser.py`)
- **Files indexed**: ❌
- **Content searchable**: ❌ 
- **Impact**: Complete lack of makefile indexing
- **Test case**: No makefile content found in searches

## Expected vs Actual

```
Expected: All supported file types fully searchable
Actual: 16/19 languages fully functional, 3 with limitations
```

## Impact Assessment
- **Severity**: Low (doesn't affect core functionality)
- **Workaround**: Use file-level search or manual inspection
- **User impact**: Minor - affects specialized file types

## Root Cause
Tree-sitter parsing limitations or incomplete parser implementations for these specific languages.

## Next Steps
1. Investigate tree-sitter grammar support for C functions
2. Review bash function extraction logic
3. Verify makefile parser integration with indexing system