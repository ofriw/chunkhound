# 2025-07-13T11:34:12+03:00 - [BUG] MCP Server Only Discovering 2 Tools Instead of 4

**Priority**: High

ChunkHound MCP server is only discovering 2 tools when it should be discovering 4 tools. This significantly limits the functionality available to VS Code users through the MCP integration.

## Observed Behavior

In VS Code with MCP integration, the output panel shows:
```
2025-07-13 11:54:06.873 [info] Starting server from Remote extension host
2025-07-13 11:54:06.882 [info] Connection state: Starting  
2025-07-13 11:54:06.882 [info] Connection state: Running
2025-07-13 11:54:06.873 [info] Discovered 2 tools
```

**Screenshot Evidence**: VS Code MCP output panel clearly shows "Discovered 2 tools" instead of the expected 4.

## Expected Behavior

ChunkHound MCP server should discover 4 tools:
1. `search_semantic` - Semantic search using embeddings
2. `search_regex` - Regex pattern search  
3. `get_stats` - Database statistics (files, chunks, embeddings)
4. `health_check` - Server health status

## Environment Details

- **VS Code**: code-server 4.101.2 (web interface)
- **ChunkHound**: v2.7.0
- **MCP Config**: `/home/coder/project/.vscode/mcp.json`
- **Container**: chunkhound-mcp-test (Docker)
- **Database**: DuckDB at `/test-data/source/.chunkhound/db`

## MCP Configuration

```json
{
  "servers": {
    "chunkhound": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory", 
        "/chunkhound",
        "chunkhound",
        "mcp"
      ],
      "env": {
        "OPENAI_API_KEY": "sk-test-local-ollama",
        "CHUNKHOUND_CONFIG": "/test-data/source/.chunkhound.json"
      }
    }
  }
}
```

## Impact

- **Reduced Functionality**: Users only have access to 2 out of 4 available tools
- **Limited Search Capabilities**: May be missing either semantic search or regex search
- **No Health Monitoring**: Cannot check server status or database statistics
- **Poor User Experience**: Incomplete MCP integration reduces utility

## Investigation Needed

1. **Tool Registration**: Check if all 4 tools are properly registered in MCP server code
2. **Tool Discovery**: Verify MCP tool discovery mechanism is working correctly
3. **Error Handling**: Look for any silent failures during tool registration
4. **Schema Validation**: Ensure all tool schemas are valid and properly formatted
5. **Configuration Issues**: Check if environment or config affects tool availability

## Related Files

- `chunkhound/mcp_server.py` - Main MCP server implementation
- `chunkhound/api/mcp/` - MCP-specific API handlers
- `chunkhound/providers/` - Search and database providers
- `.vscode/mcp.json` - VS Code MCP configuration

# History

## 2025-07-13T11:34:12+03:00

Initial bug discovery during VS Code MCP integration testing. Screenshot evidence captured showing "Discovered 2 tools" in VS Code output panel. Need to investigate root cause and identify which 2 tools are being discovered vs which 2 are missing.

Next steps: Examine MCP server code, check tool registration, and test tool availability through MCP protocol.

## 2025-07-13T11:45:22+03:00

**ROOT CAUSE IDENTIFIED**: The issue is in `chunkhound/mcp_server.py` at lines 1349 and 1326-1328.

### Technical Analysis

1. **Database Initialization Failure**: The `list_tools()` function waits for `_initialization_complete` event (line 1326) with a 30-second timeout
2. **Silent Timeout**: When timeout occurs, the function continues with `pass` (line 1328) instead of handling the failure
3. **Provider Check Fails**: The condition `if _database and hasattr(_database, "_provider"):` (line 1349) evaluates to `False` because `_database` is `None`
4. **Limited Tool Registration**: Only the 2 "always available" tools are returned (lines 1333-1346):
   - `get_stats` 
   - `health_check`

### Missing Tools

The DuckDB provider supports 3 search methods:
- `_executor_search_semantic` (line 1701 in duckdb_provider.py) → `search_semantic` tool
- `_executor_search_regex` (line 1838 in duckdb_provider.py) → `search_regex` tool  
- `_executor_search_text` (line 1931 in duckdb_provider.py) → **NOT** `search_fuzzy` tool

**Expected Tools**: 4 total (2 always + 2 search)
**Actual Tools**: 2 total (2 always + 0 search)

### Database Initialization Issue

The underlying problem is that database initialization is failing during the deferred initialization process (lines 508-519). From previous investigation, the file indexing is failing with "no files found" which prevents database connection completion.

### Solution Strategy

Two-part fix needed:
1. **Immediate**: Fix `list_tools()` to handle initialization timeout gracefully and provide fallback tools
2. **Long-term**: Fix the file indexing issue that's preventing database initialization

This ensures MCP functionality is available even when database initialization is delayed or problematic.

### Proposed Fix

**File**: `chunkhound/mcp_server.py`, lines 1326-1350

Replace the current logic with:

```python
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List tools with fallback support when database is unavailable."""
    tools = []

    # Always available tools
    tools.extend([
        types.Tool(
            name="get_stats",
            description="Get database statistics including file, chunk, and embedding counts",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="health_check", 
            description="Check server health status",
            inputSchema={"type": "object", "properties": {}},
        ),
    ])

    # Try to get provider capabilities with fallback
    provider_available = False
    try:
        # Wait briefly for initialization
        await asyncio.wait_for(_initialization_complete.wait(), timeout=5.0)
        if _database and hasattr(_database, "_provider"):
            provider = _database._provider
            provider_available = True
    except (asyncio.TimeoutError, AttributeError):
        # Provide fallback tools when database is not ready
        provider_available = False

    if provider_available:
        # Add actual provider-supported tools
        if provider.supports_semantic_search():
            tools.append(create_semantic_search_tool())
        if provider.supports_regex_search():
            tools.append(create_regex_search_tool())
        if provider.supports_fuzzy_search():
            tools.append(create_fuzzy_search_tool())
    else:
        # Fallback: Add expected tools that will show "initializing" message when called
        tools.extend([
            create_semantic_search_tool(),
            create_regex_search_tool(),
        ])

    return tools
```

This ensures users always see the expected 4 tools, with proper error messages when database is not ready.

## 2025-07-13T20:35:00+03:00

**REFINED FIX APPROACH**: After further analysis, a simpler solution is preferred that:
1. Always shows search tools based on provider capabilities 
2. Removes the initialization timeout from `list_tools()`
3. Lets individual tool handlers deal with initialization state

### Key Insights

1. **Provider Support**: DuckDB provider implements:
   - `_executor_search_semantic` → `search_semantic` tool
   - `_executor_search_regex` → `search_regex` tool  
   - `_executor_search_text` → NOT exposed as MCP tool (MCP checks for `fuzzy` not `text`)

2. **Better Approach**: Instead of complex fallback logic in `list_tools()`, we should:
   - Always attempt to detect provider capabilities immediately
   - Use default provider knowledge if database isn't initialized
   - Let tool handlers check initialization state when actually invoked

### Improved Fix

**File**: `chunkhound/mcp_server.py`, lines 1321-1480

```python
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List tools based on provider capabilities, with graceful fallback."""
    tools = []

    # Always available tools
    tools.extend([
        types.Tool(
            name="get_stats",
            description="Get database statistics including file, chunk, and embedding counts",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="health_check", 
            description="Check server health status",
            inputSchema={"type": "object", "properties": {}},
        ),
    ])

    # Check provider capabilities without waiting for initialization
    provider_supports_semantic = True  # Default assumption for DuckDB
    provider_supports_regex = True     # Default assumption for DuckDB
    
    if _database and hasattr(_database, "_provider"):
        # Use actual provider capabilities if available
        provider = _database._provider
        provider_supports_semantic = provider.supports_semantic_search()
        provider_supports_regex = provider.supports_regex_search()
    
    # Add search tools based on provider support
    if provider_supports_semantic:
        tools.append(
            types.Tool(
                name="search_semantic",
                description="Search code using semantic similarity with pagination support.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "provider": {
                            "type": "string",
                            "description": "Embedding provider to use",
                            "default": "openai",
                        },
                        "model": {
                            "type": "string", 
                            "description": "Embedding model to use",
                            "default": "text-embedding-3-small",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Distance threshold for filtering results (optional)",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of results per page (1-100)",
                            "default": 10,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting position for pagination",
                            "default": 0,
                        },
                        "max_response_tokens": {
                            "type": "integer",
                            "description": "Maximum response size in tokens (1000-25000)",
                            "default": 20000,
                        },
                        "path": {
                            "type": "string",
                            "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                        },
                    },
                    "required": ["query"],
                },
            )
        )
    
    if provider_supports_regex:
        tools.append(
            types.Tool(
                name="search_regex",
                description="Search code chunks using regex patterns with pagination support.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression pattern to search for",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Number of results per page (1-100)",
                            "default": 10,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting position for pagination",
                            "default": 0,
                        },
                        "max_response_tokens": {
                            "type": "integer",
                            "description": "Maximum response size in tokens (1000-25000)",
                            "default": 20000,
                        },
                        "path": {
                            "type": "string",
                            "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                        },
                    },
                    "required": ["pattern"],
                },
            )
        )

    return tools
```

### Benefits

1. **Immediate Tool Discovery**: VS Code sees all 4 tools immediately on startup
2. **Provider-Aware**: Respects actual provider capabilities when available
3. **Graceful Degradation**: Falls back to default DuckDB capabilities if database not ready
4. **Simpler Code**: No complex timeout/retry logic in tool discovery
5. **Better UX**: Users see consistent tool set, initialization handled at invocation time

### Next Steps

1. Implement the simplified `list_tools()` function
2. Ensure tool handlers (`search_semantic`, `search_regex`) properly check initialization state
3. Test with VS Code MCP to verify all 4 tools appear immediately

## 2025-07-13T20:45:00+03:00

**CORRECTED UNDERSTANDING**: The dynamic tool discovery mechanism is provider-dependent:

### Provider Capabilities

1. **DuckDB Provider**:
   - `_executor_search_semantic` → `search_semantic` tool
   - `_executor_search_regex` → `search_regex` tool
   - Total with always-available: 4 tools

2. **LanceDB Provider**:
   - `_executor_search_semantic` → `search_semantic` tool
   - `_executor_search_fuzzy` → `search_fuzzy` tool  
   - Total with always-available: 4 tools

3. **Future Providers**: May support different combinations of search methods

### The Real Problem

The initialization timeout prevents provider detection, so the code can't determine which search tools to expose. We need a solution that:
1. Respects provider-specific capabilities
2. Handles initialization delays gracefully
3. Doesn't hardcode assumptions about specific providers

### Better Fix Strategy

Instead of assuming DuckDB capabilities, we should:

1. **Option A: Wait briefly with better error handling**
   - Reduce timeout to 5 seconds
   - Log warnings when timeout occurs
   - Return only guaranteed tools if provider unavailable

2. **Option B: Defer tool discovery**
   - Cache the tool list after first successful initialization
   - Return cached list on subsequent calls
   - Update VS Code with new tools when ready

3. **Option C: Configuration-based fallback**
   - Read provider type from config
   - Use known capabilities for that provider type
   - Fall back to actual provider when initialized

### Recommended Solution: Option A with Logging

```python
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List tools based on provider capabilities."""
    tools = []

    # Always available tools
    tools.extend([
        types.Tool(
            name="get_stats",
            description="Get database statistics including file, chunk, and embedding counts",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="health_check", 
            description="Check server health status",
            inputSchema={"type": "object", "properties": {}},
        ),
    ])

    # Wait briefly for initialization with better error handling
    provider_available = False
    try:
        await asyncio.wait_for(_initialization_complete.wait(), timeout=5.0)
        if _database and hasattr(_database, "_provider"):
            provider = _database._provider
            provider_available = True
    except asyncio.TimeoutError:
        logger.warning("Database initialization timeout in list_tools - returning base tools only")
    except Exception as e:
        logger.error(f"Error checking provider availability: {e}")

    if provider_available:
        # Add tools based on actual provider capabilities
        if provider.supports_semantic_search():
            tools.append(create_semantic_search_tool())
        
        if provider.supports_regex_search():
            tools.append(create_regex_search_tool())
        
        if provider.supports_fuzzy_search():
            tools.append(create_fuzzy_search_tool())
    else:
        # Log the issue for debugging
        logger.info("Provider not available during tool discovery - search tools will not be available")

    return tools
```

This approach:
- Reduces timeout to 5 seconds (more responsive)
- Adds proper logging for debugging
- Respects actual provider capabilities
- Doesn't make assumptions about which provider is in use
- Provides clear feedback when tools are limited

### Root Cause Summary

The issue isn't about hardcoding provider assumptions, but about the 30-second timeout during initialization that prevents proper provider detection. The fix should focus on better timeout handling and logging, not bypassing the provider detection mechanism.