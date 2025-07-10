# 2025-07-10 - [BUG] MCP Config Loading ChunkHound.json

**Priority**: High

## Description

MCP server starts successfully but semantic search fails with "No embedding providers available" when running from Ubuntu 20 from a different directory, despite having valid .chunkhound.json configuration file with OpenAI API key and provider settings. This is a follow-up bug to the recently resolved TaskGroup crash issue.

## Environment

- Ubuntu 20.04 
- Running `uv run chunkhound mcp ./path/to/target` from outside target directory
- Valid .chunkhound.json exists in target directory with proper OpenAI configuration
- Same environment as previously fixed TaskGroup comprehensive fix

## Error Details

```
No embedding providers available. Set OPENAI_API_KEY to enable semantic search.
```

## Root Cause Analysis

After comprehensive investigation:

1. **MCP Server Config Loading Flow**:
   - MCP server finds project root correctly (`chunkhound/mcp_server.py:155`)
   - Sets `CHUNKHOUND_PROJECT_ROOT` environment variable (`chunkhound/mcp_server.py:158`)
   - Creates Config() instance without target_dir parameter (`chunkhound/mcp_server.py:172`)

2. **Config Class Loading Logic**:
   - Config.__init__() checks for `CHUNKHOUND_PROJECT_ROOT` env var
   - Should find .chunkhound.json in that directory
   - But Config class may not be reading the environment variable correctly

3. **Embedding Provider Registration**:
   - MCP server calls `EmbeddingProviderFactory.create_provider(config.embedding)` (`chunkhound/mcp_server.py:241-244`)
   - If config.embedding is None/empty, provider creation fails
   - Results in empty provider list, causing "No embedding providers available" error

## Technical Analysis

The issue appears to be in the Config class not properly loading .chunkhound.json when:
1. MCP server runs from different directory than target
2. Environment variable `CHUNKHOUND_PROJECT_ROOT` is set but not read correctly
3. Config() constructor called without target_dir parameter

Critical code locations:
- `chunkhound/mcp_server.py:155-172` - Project root detection and Config creation
- `chunkhound/core/config/config.py:46-56` - Environment variable reading in Config.__init__()
- `chunkhound/mcp_server.py:241-244` - Embedding provider registration

## Execution Plan

### Phase 1: Diagnostic (1-2 hours)
1. **Reproduce the exact issue** - Set up Ubuntu 20 environment with .chunkhound.json
2. **Debug Config loading** - Add logging to Config.__init__() to trace environment variable reading
3. **Verify project root detection** - Confirm `CHUNKHOUND_PROJECT_ROOT` is set correctly
4. **Test .chunkhound.json loading** - Check if Config finds and loads the JSON file

### Phase 2: Root Cause Identification (1 hour)
1. **Environment variable timing** - Check if CHUNKHOUND_PROJECT_ROOT is set before Config() creation
2. **Working directory issues** - Verify if relative paths affect .chunkhound.json loading
3. **Config class logic** - Test Config constructor with and without target_dir parameter

### Phase 3: Implementation (1-2 hours)
1. **Fix Config loading** - Ensure .chunkhound.json is properly loaded from CHUNKHOUND_PROJECT_ROOT
2. **Preserve Ubuntu fix** - Maintain compatibility with database path resolution fix
3. **Add error handling** - Provide clear error messages when config loading fails

### Phase 4: Testing (1 hour)
1. **Test Ubuntu 20 environment** - Verify fix works in original failing environment
2. **Test different directory scenarios** - Running from various working directories
3. **Verify no regression** - Ensure TaskGroup fix still works
4. **Test embedding provider registration** - Confirm semantic search works with .chunkhound.json

## Success Criteria

- MCP server loads .chunkhound.json configuration correctly when running from different directory
- Semantic search works with embedding providers from .chunkhound.json
- No regression in TaskGroup crash fix
- Clear error messages when configuration issues occur

## Files to Investigate

- `chunkhound/mcp_server.py` - MCP server configuration loading (lines 155-172, 241-244)
- `chunkhound/core/config/config.py` - Config class constructor and environment variable handling
- `chunkhound/providers/embedding/factory.py` - Embedding provider creation logic

## Risk Assessment

- **Medium impact**: Semantic search functionality broken in specific deployment scenarios
- **Low complexity**: Config loading issue with clear debugging path
- **Low regression risk**: Well-isolated to configuration loading logic

# History

## 2025-07-10T15:30:00-07:00

**ISSUE IDENTIFIED**: Created ticket after comprehensive codebase analysis.

### Root cause analysis completed:
1. **MCP server flow understood** - Server correctly finds project root and sets environment variable
2. **Config class logic analyzed** - Config.__init__() should read CHUNKHOUND_PROJECT_ROOT but may not be working
3. **Error pathway traced** - Empty config.embedding leads to no providers, causing semantic search failure
4. **Previous fix preserved** - Must maintain compatibility with database path resolution fix

### Technical findings:
- Error occurs in `chunkhound/mcp_server.py:241-244` when config.embedding is None/empty
- Config class has logic to read `CHUNKHOUND_PROJECT_ROOT` but may not be executing correctly
- MCP server sets environment variable at line 158 but Config() called at line 172

### Next steps:
1. Set up reproduction environment with Ubuntu 20 and .chunkhound.json
2. Add debugging to Config.__init__() to trace environment variable reading
3. Test Config loading with and without target_dir parameter
4. Implement fix while preserving database path resolution logic

## 2025-07-10T17:45:00-07:00

**CRITICAL BUG FIXED**: Root cause identified and resolved.

### Root Cause Confirmed:
The issue was in `chunkhound/mcp_server.py` lines 155-158:
```python
# BROKEN CODE:
project_root = find_project_root()
os.environ["CHUNKHOUND_PROJECT_ROOT"] = str(project_root)
```

**Problem**: MCP server was calling `find_project_root()` and overwriting the CLI-provided `CHUNKHOUND_PROJECT_ROOT` environment variable, causing Config to look for `.chunkhound.json` in the wrong directory.

### Fix Implemented:
```python
# FIXED CODE:
project_root_env = os.environ.get("CHUNKHOUND_PROJECT_ROOT")
if project_root_env:
    project_root = Path(project_root_env)
else:
    project_root = find_project_root()
    os.environ["CHUNKHOUND_PROJECT_ROOT"] = str(project_root)
```

### Validation Results:
1. **Fix confirmed working**: Config now properly loads `.chunkhound.json` when `CHUNKHOUND_PROJECT_ROOT` is set
2. **Backward compatibility**: Falls back to `find_project_root()` when environment variable not set
3. **Test results**: Config loading test shows embedding config properly loaded with fix
4. **No regression**: Database path resolution logic preserved

### Technical Details:
- **Before fix**: CLI sets `CHUNKHOUND_PROJECT_ROOT=/path/to/target`, MCP server overwrites it with `find_project_root()` result
- **After fix**: MCP server respects existing `CHUNKHOUND_PROJECT_ROOT`, only calls `find_project_root()` as fallback
- **Impact**: Enables semantic search when running `uv run chunkhound mcp ./target` from different directory

**ISSUE RESOLVED**: MCP server now correctly loads `.chunkhound.json` configuration from target directory, enabling semantic search functionality.