# 2025-07-10 - [BUG] MCP Embedding Provider Not Loaded from Config
**Priority**: High

## Description

MCP server fails to detect OpenAI embedding provider from `.chunkhound.json` configuration file when running from a different directory than the target project. This results in "No embedding providers available" error when attempting semantic search, even though valid OpenAI configuration exists in the target directory.

## Environment

- ChunkHound version: 2.6.1 (PyPI)
- Error location: `chunkhound/mcp_server.py` lines 907-910
- Scenario: Running `chunkhound mcp <target>` from different directory

## Error Details

```python
# chunkhound/mcp_server.py:907-910
if not _embedding_manager or not _embedding_manager.list_providers():
    raise Exception(
        "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
    )
```

## Root Cause

The MCP server is not loading the embedding configuration from `.chunkhound.json` in the target directory when invoked from a different working directory. The embedding manager remains uninitialized despite valid configuration.

## Test Case

Created Docker test to reproduce:

1. Create target directory with `.chunkhound.json`:
```json
{
  "embedding": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "openai_api_key": "sk-proj-test-key-123456"
  }
}
```

2. Run MCP server from different directory:
```bash
cd /working_dir
chunkhound mcp /target_dir
```

3. Send semantic search request via JSON-RPC
4. Result: "No embedding providers available" error

## Docker Test Files

- `Dockerfile.simple-bug-test` - Basic reproduction test
- `Dockerfile.bug-test-final` - Inline test script
- `Dockerfile.provider-bug` - Python-based test
- `Dockerfile.mcp-bug-final` - Shell-based MCP test

All tests confirm the bug exists in version 2.6.1.

## Impact

- Semantic search functionality broken when MCP server runs from different directory
- Affects AI assistant integrations relying on semantic search
- Forces users to run MCP from project directory or use environment variables

# History

## 2025-07-10T18:20:00-07:00

**BUG CONFIRMED**: Successfully replicated the issue with ChunkHound 2.6.1.

### Investigation Summary:
1. **MCP Protocol Testing** - Tested with correct JSON-RPC format after researching MCP specification
2. **Source Code Analysis** - Located error at `chunkhound/mcp_server.py:907-910` in `search_semantic` handler
3. **Docker Tests Created** - Multiple test configurations to isolate and reproduce the bug
4. **Root Cause Identified** - Embedding manager not initialized with config from target directory

### Technical Details:
- MCP server initializes successfully (returns version 2.6.1)
- Server responds to `initialize` requests properly
- Fails specifically on `tools/call` with `search_semantic` when embedding provider not loaded
- The `.chunkhound.json` file exists with valid OpenAI config but is not being read

### Test Results:
- Created comprehensive Docker tests that install chunkhound 2.6.1 from PyPI
- Tests confirm MCP server starts but semantic search fails with "No embedding providers available"
- Issue occurs specifically when running from different directory than target

### Next Steps:
1. Check if issue was already fixed in a commit after 2.6.1 release
2. If not fixed, implement proper config loading in MCP server initialization
3. Ensure `CHUNKHOUND_PROJECT_ROOT` is properly used for config file discovery
4. Add tests to prevent regression

## 2025-07-10T19:00:00-07:00

**FIX IMPLEMENTED**: Fixed MCP server config loading issue.

### Root Cause Analysis:
The bug was in `chunkhound/mcp_server.py` at line 174 where the Config was initialized without passing the `target_dir` parameter:
```python
config = Config()  # Missing target_dir parameter
```

This caused the Config class to not load the `.chunkhound.json` file from the target directory, even though `CHUNKHOUND_PROJECT_ROOT` was set correctly by the CLI command.

### Fix Applied:
Updated line 174 in `chunkhound/mcp_server.py` to:
```python
config = Config(target_dir=project_root)
```

This ensures that the Config class looks for `.chunkhound.json` in the target directory specified by the user when running `chunkhound mcp <path>`.

### How the Fix Works:
1. The `mcp.py` CLI command sets `CHUNKHOUND_PROJECT_ROOT` environment variable when a path is provided
2. The MCP server reads this environment variable and sets `project_root` accordingly
3. The Config class now receives the `target_dir` parameter and loads `.chunkhound.json` from that directory
4. The embedding configuration is properly loaded and the EmbeddingManager is initialized with the correct provider

### Testing:
- Created test directory with `.chunkhound.json` containing OpenAI embedding configuration
- Verified that the fix allows MCP server to properly detect and load embedding providers
- Docker test configurations created: `Dockerfile.fix-test` and `test_fix.sh`

### Files Modified:
- `chunkhound/mcp_server.py`: Line 174 - Added `target_dir=project_root` parameter to Config initialization

This fix ensures that the MCP server respects the target directory's configuration file when running from a different working directory, resolving the "No embedding providers available" error.