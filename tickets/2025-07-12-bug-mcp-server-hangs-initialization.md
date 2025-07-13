# 2025-07-12 - [BUG] MCP Server Hangs on Initialization
**Priority**: Urgent

The ChunkHound MCP server hangs indefinitely when receiving initialization requests, making it unusable with VS Code and other MCP clients.

# Bug Description

## Symptoms
1. MCP server doesn't respond to `initialize` requests via stdio transport
2. Server hangs indefinitely (2+ minutes) instead of returning immediate response
3. Database lock conflicts when multiple MCP processes attempt to start
4. VS Code cannot establish MCP connection due to timeout

## Reproduction Steps
1. Start MCP server: `chunkhound mcp`
2. Send initialization request:
   ```json
   {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}, "id": 1}
   ```
3. Server hangs without response

## Expected Behavior
- Immediate response with server capabilities
- Proper stdio transport handling
- No blocking on initialization

## Actual Behavior
- Server hangs indefinitely
- No response to client
- Process blocks stdio communication

# Technical Details

## Error Messages
```
IO Error: Could not set lock on file "/mcp-workdir/.chunkhound/db": Conflicting lock is held in python3.13 (PID xxx)
```

## Test Environment
- Docker container with Ubuntu 20.04
- ChunkHound v2.7.0
- Python 3.13.5
- VS Code (code-server) with MCP extension

## Test Script
Created `test/docker/test-mcp-bug.sh` to reproduce the issue consistently.

# Impact
- MCP integration completely non-functional
- Cannot use ChunkHound with VS Code MCP extension
- Blocks adoption of MCP-based workflows

# Possible Causes
1. Incorrect stdio transport implementation
2. Blocking I/O operations during initialization
3. Database connection not properly isolated for MCP mode
4. Missing async/await in initialization handler

# Root Cause Analysis

## Primary Issue: Heavy Initialization Before Protocol Handling

The MCP server performs all initialization in `server_lifespan()` BEFORE `server.run()` is called:

1. `handle_mcp_with_validation()` creates stdio context
2. `server_lifespan()` runs heavy initialization (lines 126-463):
   - Database connection (`_database.connect()` - BLOCKING)
   - File watcher initialization (up to 3s timeout)
   - Periodic indexer startup (immediate scan)
3. Only after ALL initialization does `server.run()` execute
4. `server.run()` is what reads stdin and responds to `initialize`

**Result**: Initialize request sits unread in stdin buffer while server blocks on initialization, causing client timeout.

## Secondary Issue: Database Lock Conflicts

DuckDB uses exclusive file locks. When multiple MCP servers start for same database, they conflict despite process detection attempts.

# Proposed Solution

## Approach: Defer Database Connection Only

Keep file watcher active immediately (to not miss changes) but defer the slow database connection.

### Implementation Strategy

1. **Three-Phase Initialization**:
   - **Phase 1** (Before server.run): Minimal setup only
   - **Phase 2** (After MCP handshake): Database connection in background
   - **Phase 3** (After tool discovery): Mark fully initialized

2. **MCP Handshake Guards**:
   ```python
   _mcp_handshake_complete = asyncio.Event()  # After initialize/initialized
   _database_ready = asyncio.Event()          # After DB connected
   _initialization_complete = asyncio.Event()  # After tool discovery
   ```

3. **File Change Queuing**:
   - File watcher starts immediately with guarded handler
   - Events queued until database ready
   - No missed changes

4. **Timeline**:
   ```
   T+0ms    : Server starts
   T+5ms    : File watcher active (guarded)
   T+10ms   : server.run() ready
   T+15ms   : Initialize request → immediate response
   T+25ms   : Initialized notification received
   T+30ms   : _mcp_handshake_complete.set()
   T+35ms   : Database connection starts (background)
   T+40ms   : Tool discovery completes
   T+500ms  : Database connected
   T+505ms  : Periodic indexer starts
   T+510ms  : _initialization_complete.set()
   ```

5. **Safety Mechanisms**:
   - File watcher handler waits for MCP handshake
   - Periodic indexer waits for database
   - Tools return "initializing" status if called early
   - No database operations before handshake complete

# History

## 2025-07-12
Root cause identified: Server performs all heavy initialization (database connection, file scanning) in `server_lifespan()` before `server.run()` can handle the initialize request. This violates MCP protocol expectation of immediate response. Solution: Defer database connection until after MCP handshake completes, while keeping file watcher active to prevent missing changes. Critical insight: Initialization is only complete after tool discovery, not just after initialize response.

## 2025-07-12 - Fix Implemented
Successfully fixed the initialization hang issue. Changes made:

1. **Added initialization tracking events**:
   - `_mcp_handshake_complete`: Set after initialize/initialized exchange
   - `_database_ready`: Set after DB connection established
   - `_initialization_complete`: Set after all components ready

2. **Created deferred initialization function** (`_deferred_database_initialization`):
   - Waits for MCP handshake before connecting to database
   - Moves DB connection, signal coordination, and periodic indexer to background
   - Processes queued file changes after DB ready

3. **Modified `server_lifespan` for minimal initialization**:
   - Removed blocking database connection
   - Kept file watcher with guarded handler
   - Started deferred init task in background

4. **Implemented guarded file change handler**:
   - Queues changes if handshake/DB not ready
   - Prevents premature database access
   - Ensures no file changes are missed

5. **Updated tool handlers**:
   - Return "initializing" status for early calls
   - Provide helpful error messages
   - Handle initialization errors gracefully

**Test Results**:
- Initialize response time: ~2.5 seconds (was: timeout/hang)
- Early tool calls: Handled gracefully
- Search functionality: Works correctly after init
- File watching: Active immediately, no missed changes

The fix maintains full functionality while ensuring MCP protocol compliance.