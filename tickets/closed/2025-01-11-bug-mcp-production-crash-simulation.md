# 2025-01-11 - BUG MCP Production Crash Simulation
**Priority**: High

ChunkHound MCP server crashes in production environment with specific configuration. Need to build Docker-based simulation to reproduce and fix.

## Production Environment Details
- Ubuntu 20
- Single source file directory
- OpenAI-compatible embeddings server
- MCP server run from different directory than indexed
- Semantic search query via JSON-RPC after handshake

## Root Cause Hypothesis
- Likely related to TaskGroup race condition (see ticket #2025-01-11-bug-mcp-taskgroup-startup-crash)
- Path resolution issues when MCP server runs from different directory
- Embedding provider initialization failure

## Execution Plan

### Phase 1: Ollama Setup (Local Mac)
1. Install minimal embedding model: `ollama pull all-minilm`
2. Verify Ollama API endpoint: `http://localhost:11434/v1`
3. Test embeddings API: `curl http://localhost:11434/api/embeddings -d '{"model":"all-minilm","prompt":"test"}'`

### Phase 2: Docker Test Environment
1. Create `Dockerfile.ubuntu20-mcp-test`:
   - Base: Ubuntu 20.04
   - Install Python 3.8, uv
   - Copy ChunkHound source
   - Configure for OpenAI-compatible embeddings
2. Create test directory structure:
   - `/test-data/source/` - Single Python file
   - `/mcp-workdir/` - MCP server run location
3. Build test container with embedded config

### Phase 3: Simulation Scripts
1. `docker-compose.mcp-test.yml` - Orchestrate test environment
2. `test-mcp-scenario.sh` - Full test scenario:
   - Start Ollama on host
   - Run indexing from source directory
   - Start MCP server from different directory
   - Send JSON-RPC commands
3. Capture crash logs and stack traces

### Phase 4: Debug & Fix
1. Add debug logging to MCP server initialization
2. Fix path resolution for cross-directory operation
3. Handle embedding provider connection failures gracefully
4. Test fix in simulation environment

## Requirements
- Docker with Ubuntu 20.04 base image
- Ollama running on host Mac
- Network bridge for Docker->Host communication
- JSON-RPC test client

## Expected Outcomes
1. Reproducible crash scenario in Docker
2. Detailed error logs and stack trace
3. Fix for production crash
4. Regression test suite

## Implementation Tasks
- [x] Setup Ollama with all-minilm model
- [x] Create Ubuntu 20 test container
- [x] Write MCP test scenario script
- [x] Configure Docker networking for Ollama access
- [x] Implement chunkhound.json config for test
- [x] Create single-file test repository
- [x] Reproduce crash condition
- [x] Implement fix
- [x] Add regression tests

# History

## 2025-01-11T17:25:00+03:00
**RESOLVED**: Successfully reproduced and fixed the MCP production crash.

### Root Cause
TaskGroup race condition where MCP server accepts tool calls before initialization is complete:
1. MCP server starts and accepts JSON-RPC requests immediately
2. Database/embedding initialization happens asynchronously in server_lifespan
3. Client sends tool calls before initialization completes
4. Server throws "RuntimeError: Received request before initialization was complete"

### Fix Applied
Added initialization state tracking in `chunkhound/mcp_server.py`:
- Global `_initialization_complete` flag
- Check in `@server.call_tool()` handler prevents early requests
- Clear error message: "Server is still initializing, please wait and try again"
- Flag set to True after all components initialized, reset to False during cleanup

### Test Results
- ✅ Reproduced original crash pattern with TaskGroup exception
- ✅ Fix prevents crash with graceful error handling
- ✅ Server works correctly after initialization completes
- ✅ Test suite created: `test-mcp-init.sh` for regression testing

### Files Modified
- `chunkhound/mcp_server.py` - Added initialization state checking
- `test-mcp-init.sh` - Test script for crash reproduction/regression testing

The fix prevents the production crash while maintaining server functionality. Ready for deployment.

## 2025-01-12T07:50:00+03:00
**FINAL RESOLUTION**: Implemented complete asyncio.Event-based synchronization fix.

### Final Implementation Applied
The root cause identified in ticket #2025-01-11-bug-mcp-rapid-commands-crash has been completely resolved:

1. **Replaced Boolean Flag**: `_initialization_complete: bool = False` → `_initialization_complete: asyncio.Event = asyncio.Event()`
2. **Added Handler Synchronization**: All MCP handlers now properly wait with `await asyncio.wait_for(_initialization_complete.wait(), timeout=30.0)`
3. **Event Lifecycle Management**: Proper `.set()` after init and `.clear()` during cleanup

### Code Changes Made
- `chunkhound/mcp_server.py:71` - Global event declaration
- `chunkhound/mcp_server.py:842-847` - call_tool() synchronization  
- `chunkhound/mcp_server.py:1118-1122` - list_tools() synchronization
- `chunkhound/mcp_server.py:671-676` - process_file_change() synchronization
- `chunkhound/mcp_server.py:454` - Event set after initialization
- `chunkhound/mcp_server.py:474` - Event clear during cleanup

### Test Results
✅ **Race condition eliminated**: No more TaskGroup crashes with rapid command sequences
✅ **Graceful waiting**: Commands now wait for initialization instead of failing immediately  
✅ **Timeout protection**: 30-second timeout prevents infinite waits
✅ **Production ready**: Fix addresses original production crash scenario

**Status: COMPLETELY RESOLVED** - The asyncio.Event pattern successfully eliminates the MCP TaskGroup race condition crash.