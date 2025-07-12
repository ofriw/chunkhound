# 2025-01-11 - [BUG] MCP TaskGroup Startup Crash
**Priority**: High

MCP server crashes with TaskGroup ClosedResourceError during startup when using openai-compatible embedding provider on Ubuntu.

## Symptoms
- Error: `unhandled errors in a TaskGroup (1 sub-exception)` with nested `ClosedResourceError`
- Occurs during MCP server initialization, not shutdown
- Happens specifically with openai-compatible provider configuration
- Reproducible on Ubuntu 20.04, not on macOS

## Error Details
```json
{
  "code": -32603,
  "message": "MCP server error",
  "data": {
    "details": "unhandled errors in a TaskGroup (1 sub-exception)",
    "error_type": "ExceptionGroup",
    "taskgroup_analysis": [
      "Level 0: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)",
      "Level 1: Exception: Failed to initialize database and embeddings: unhandled errors in a TaskGroup (1 sub-exception)",
      "Level 4: ClosedResourceError: "
    ]
  }
}
```

## Configuration
```json
{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "http://localhost:11434/v1",
    "api_key": "dummy",
    "model": "nomic-embed-text"
  }
}
```

## Known Issues Found
1. Line 587 in mcp_server.py calls non-existent method `_task_coordinator.wait_for_completion()` (should be `stop()`)
2. MCP server defaults to "openai" provider instead of using configured provider (fixed separately)

## To Investigate
- Why ClosedResourceError occurs during startup initialization
- What async resource is being closed prematurely
- Connection between openai-compatible provider and the crash

# History

## 2025-01-11
Initial ticket creation. Found missing method issue but need to investigate actual startup crash cause.

### Root Cause Analysis Complete

Found multiple issues:

1. **Missing Method Error**: Line 587 in `mcp_server.py` calls `_task_coordinator.wait_for_completion()` which doesn't exist. The TaskCoordinator class only has a `stop()` method. This causes an AttributeError during cleanup.

2. **MCP Default Provider Bug**: The `search_semantic` handler defaults to "openai" provider instead of using the configured provider. Fixed by storing `_configured_embedding_provider` and `_configured_embedding_model` during initialization.

3. **TaskGroup Crash Sequence**:
   - The crash is triggered when the MCP client closes stdin while operations are in progress
   - This causes the MCP library's stdio_server TaskGroup to begin shutdown
   - During shutdown, the missing `wait_for_completion()` method causes an AttributeError
   - This error gets wrapped in multiple ExceptionGroups along with the original ClosedResourceError
   - The result is the complex nested error: "unhandled errors in a TaskGroup (1 sub-exception)"

4. **Why It Appears as Startup Crash**:
   - When testing with simple scripts that send init and immediately exit, stdin closes right after initialization
   - This makes it appear as a "startup crash" when it's actually a shutdown crash
   - The error response is sent before the server fully shuts down

### Confirmed Issues:
- `_task_coordinator.wait_for_completion()` should be `_task_coordinator.stop()`
- MCP server should use configured embedding provider as default, not hardcoded "openai"
- The TaskGroup error is a symptom of the missing method, not the root cause

### Work Completed:

1. **Replicated the Crash**:
   - Created Docker container with Ubuntu 20.04 and Python 3.10
   - Configured ChunkHound with openai-compatible embedding provider
   - Successfully triggered the TaskGroup ClosedResourceError
   - Confirmed error matches tickets: `"unhandled errors in a TaskGroup (1 sub-exception)"`

2. **Root Cause Analysis**:
   - Traced through MCP server initialization and shutdown sequences
   - Identified missing method `wait_for_completion()` on TaskCoordinator (line 587)
   - Discovered the crash occurs during shutdown, not startup
   - Found that quick stdin closure in tests makes it appear as startup crash

3. **Fixed Secondary Issue**:
   - Added `_configured_embedding_provider` and `_configured_embedding_model` globals
   - Modified line 252-253 to store configured values during provider registration
   - Updated lines 912-914 to use configured provider instead of hardcoded "openai"
   - This ensures MCP respects the configured embedding provider

4. **Testing Performed**:
   - Created multiple test scripts to isolate crash conditions
   - Tested with various configurations (env vars, JSON config, different directories)
   - Verified config precedence is working correctly
   - Confirmed crash is reproducible and related to shutdown sequence

### Remaining Work:
- Fix line 587: Change `_task_coordinator.wait_for_completion()` to `_task_coordinator.stop()`
- Test the fix in the exact failing environment (Ubuntu 20.04 with MCP)

## 2025-01-11 - Update After Fixes

### Fixes Applied:
1. **Fixed missing method**: Changed line 587 from `_task_coordinator.wait_for_completion()` to `_task_coordinator.stop()`
2. **Provider defaults remain**: The configured provider globals are already in place from earlier work

### Testing Results:
1. **Clean shutdown confirmed**: With the fix, the server exits cleanly (exit code 0) when stdin closes
2. **TaskGroup crash still occurs**: However, when testing rapid command sequences, the same TaskGroup ClosedResourceError still appears
3. **Timing sensitivity**: The crash seems related to sending multiple commands in rapid succession

### Current Status:
- The `wait_for_completion()` fix prevents one crash during shutdown
- But the TaskGroup ClosedResourceError still occurs during initialization in some scenarios
- This suggests there may be multiple issues or a deeper race condition

### Next Steps:
- The crash now appears to be related to rapid command sequences rather than just shutdown
- May need to investigate the MCP library's stdio handling or asyncio task management
- Consider if there's a race condition during initialization when commands arrive quickly

## ⚠️ IMPORTANT: Bug Not Fully Resolved

While the `wait_for_completion()` fix prevents the shutdown crash, **the TaskGroup ClosedResourceError still occurs** under certain conditions:

1. **Rapid Command Sequences**: Sending multiple JSON-RPC commands quickly still triggers the crash
2. **Race Condition**: There appears to be a race condition during server initialization
3. **Same Error Signature**: The error message is identical to the original crash

**See ticket #2025-01-11-bug-mcp-rapid-commands-crash for the remaining issue.**

### Summary of Current State:
- ✅ Fixed: `wait_for_completion()` method error
- ✅ Fixed: Server shuts down cleanly with normal stdin closure
- ✅ Fixed: MCP uses configured embedding provider instead of defaulting to "openai"
- ❌ Not Fixed: TaskGroup crash with rapid command sequences
- ❌ Not Fixed: Race condition during initialization

Future investigators should test with both:
1. Normal usage patterns (with delays between commands)
2. Rapid command sequences (piped or scripted without delays)