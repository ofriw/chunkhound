# 2025-07-13T17:15:00+03:00 - [BUG] MCP Server TaskGroup ClosedResourceError on Initialization
**Priority**: High

ChunkHound MCP server encounters TaskGroup ClosedResourceError during initialization, preventing proper startup and tool execution. This issue was discovered while fixing the self-deadlock bug but is unrelated to database locking.

## Symptoms

1. MCP server starts and responds to `initialize` method successfully
2. An error notification is sent shortly after with TaskGroup exception details
3. Tool calls may fail or return error status
4. Multiple nested ExceptionGroup errors with ClosedResourceError at the core

## Error Message

```json
{
  "jsonrpc": "2.0", 
  "id": null, 
  "error": {
    "code": -32603, 
    "message": "MCP server error", 
    "data": {
      "details": "unhandled errors in a TaskGroup (1 sub-exception)", 
      "suggestion": "Check that the database path is accessible and environment variables are correct.", 
      "taskgroup_analysis": [
        "Level 0: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)",
        "Level 1: Exception: Failed to initialize database and embeddings: unhandled errors in a TaskGroup (1 sub-exception)",
        "Level 2: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)",
        "Level 3: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)",
        "TaskGroup exception 1:",
        "Level 4: ClosedResourceError: "
      ],
      "error_type": "ExceptionGroup"
    }
  }
}
```

## Exact Reproduction Steps

### Prerequisites
1. ChunkHound latest version with self-deadlock fix applied
2. Docker with Ubuntu 20.04 test environment
3. Ollama SHOULD be running on host Mac (the error occurs even with valid Ollama connection)
4. The error appears to be related to async initialization timing, not embedding config

### Method 1: Docker Environment (Confirmed)

1. **Build the test container**:
   ```bash
   cd /path/to/chunkhound
   docker-compose -f docker-compose.mcp-test.yml build
   ```

2. **Create and run the test script**:
   ```bash
   cat > test-taskgroup-error.sh << 'EOF'
   #!/bin/bash
   docker run --rm \
     --name chunkhound-taskgroup-test \
     chunkhound-mcp-test \
     bash -c "
       export PYTHONPATH=/chunkhound
       export CHUNKHOUND_CONFIG=/mcp-workdir/chunkhound.json
       export OPENAI_API_KEY=sk-test-local-ollama
       
       # Index first
       cd /mcp-workdir && /chunkhound/.venv/bin/chunkhound index
       
       # Run MCP server
       (
         echo '{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"initialize\", \"params\": {\"protocolVersion\": \"2024-11-05\", \"capabilities\": {}, \"clientInfo\": {\"name\": \"test\", \"version\": \"1.0\"}}}'
         sleep 1
         echo '{\"jsonrpc\": \"2.0\", \"method\": \"notifications/initialized\"}'
         sleep 3
       ) | /chunkhound/.venv/bin/chunkhound mcp 2>&1
     "
   EOF
   chmod +x test-taskgroup-error.sh
   ./test-taskgroup-error.sh
   ```

### Method 2: Local Environment (Not Reproduced)

**Note**: The TaskGroup error has NOT been reliably reproduced on macOS locally. It appears to be specific to the Docker environment or related to resource constraints/timing differences.

## Expected vs Actual Behavior

**Expected**: 
- MCP server initializes successfully
- No error notifications sent
- Server ready to handle tool calls

**Actual**: 
- MCP server sends error notification with TaskGroup/ClosedResourceError
- Initialization appears to fail internally
- Tool calls may not work properly

## Technical Analysis

### Observations
1. The error occurs during the deferred initialization phase
2. Multiple nested TaskGroups suggest async/await context issues
3. ClosedResourceError typically indicates attempting to use a closed async resource
4. The error mentions "Failed to initialize database and embeddings"
5. Occurs even with valid Ollama connection (embedding config is not the root cause)
6. Appears specific to Docker environment - not reproduced on macOS locally

### Potential Causes
1. **Async Context Management**: TaskGroup being closed prematurely
2. **Deferred Initialization Race**: Timing issue between MCP handshake and database init
3. **Embedding Service Failure**: Failed embedding setup cascading to TaskGroup error
4. **Resource Cleanup**: Premature cleanup of async resources during initialization

### Related Code Areas
- `mcp_server.py`: `_deferred_database_initialization()` function
- `mcp_server.py`: `server_lifespan()` context manager
- Task coordinator initialization and lifecycle
- Embedding manager setup in deferred init

## Environment Details

- **ChunkHound Version**: Latest (post self-deadlock fix)
- **Python**: 3.10+ 
- **Async Framework**: asyncio with anyio TaskGroups
- **Error Context**: MCP server stdio transport
- **Platforms Affected**: Ubuntu 20.04 (Docker), macOS

## Impact

- **Severity**: High - Prevents proper MCP server initialization
- **Scope**: Affects all MCP integrations when embedding config has issues
- **User Experience**: Server appears to start but sends error notifications
- **Functionality**: Tool calls may fail or behave unexpectedly

## Workaround

Currently no reliable workaround. The error is intermittent and may depend on:
- Timing of initialization steps
- Availability of embedding services
- System resources and load

## Additional Notes

1. This issue was discovered while fixing the self-deadlock bug but is unrelated
2. The error occurs in Docker but not locally on macOS, suggesting environment-specific timing/resource issues
3. The nested ExceptionGroups make debugging challenging
4. May be related to the deferred initialization pattern introduced to fix MCP hanging
5. The actual error output shows the MCP server does respond to initialize but sends an error notification

# History

## 2025-07-13T17:15:00+03:00
Initial bug documentation. Discovered during self-deadlock fix testing in Docker environment.

## 2025-07-13T17:25:00+03:00
Updated with testing results:
- Confirmed the error occurs in Docker Ubuntu 20 environment
- Could NOT reproduce on macOS locally
- Ollama connection status doesn't affect the error (occurs even with valid connection)
- The error appears to be timing/resource related rather than configuration related

## 2025-07-13T18:00:00+03:00
Root cause identified and fix implemented:
- **Root Cause**: Background asyncio tasks (`deferred_init_task` and `handshake_tracker`) were not properly managed
- When these tasks failed or weren't awaited, they became "unhandled errors in a TaskGroup"
- The `ClosedResourceError` likely came from tasks trying to use resources after context manager exit

**Fix Applied**:
1. Added proper cleanup for `deferred_init_task` in server_lifespan finally block
2. Added done callback to handle exceptions from deferred initialization
3. Made deferred init re-raise exceptions so task fails properly  
4. Added cleanup for `handshake_tracker` task with proper cancellation
5. Improved error messages to show exception types and causes

**Key Changes**:
- Store task references globally for cleanup
- Cancel tasks if still running during shutdown
- Properly await cancelled tasks to handle CancelledError
- Re-raise exceptions in deferred init so task state is correct
- Add done callbacks to catch task exceptions early

This ensures all background tasks are properly managed and don't cause TaskGroup errors.