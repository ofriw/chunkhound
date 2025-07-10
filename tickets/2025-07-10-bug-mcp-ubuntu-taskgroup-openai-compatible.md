# 2025-07-10 - [BUG] MCP Server TaskGroup Error on Ubuntu with OpenAI-Compatible Provider

**Priority**: High

## Description

MCP server crashes with TaskGroup error -32603 when running from a different directory on Ubuntu with OpenAI-compatible embedding provider configuration. The error persists despite previous fixes to the OpenAI provider's lazy initialization.

## Current Behavior

When running `chunkhound mcp /test-project` from a different directory on Ubuntu 20.04 with this config:
```json
{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "https://pdc-llm-srv1:4000",
    "api_key": "sk-pdc-llm-05-2025",
    "model": "bge-en-icl"
  },
  "database": {
    "provider": "lancedb",
    "path": ".chunkhound.lance"
  }
}
```

Server crashes with:
```json
{
  "jsonrpc": "2.0", 
  "id": null, 
  "error": {
    "code": -32603, 
    "message": "MCP server error", 
    "data": {
      "details": "unhandled errors in a TaskGroup (1 sub-exception)", 
      "suggestion": "Check that the database path is accessible and environment variables are correct."
    }
  }
}
```

## Investigation Results

1. **OpenAI Provider Fixed**: The `OpenAIEmbeddingProvider` in `chunkhound/providers/embeddings/openai_provider.py` now properly uses lazy initialization
2. **OpenAI-Compatible Provider OK**: The `OpenAICompatibleProvider` doesn't create any async resources in `__init__`
3. **Issue Still Occurs**: The TaskGroup error happens during MCP server startup, likely in the lifespan context

## Root Cause Analysis

The error appears to be happening during:
1. MCP server startup lifespan
2. Database factory initialization (`create_database_with_dependencies`)
3. Registry creates embedding service via `create_embedding_service()`
4. Registry gets embedding provider via `get_provider("embedding")`
5. This triggers `FactoryEmbeddingProvider.__new__` which calls `EmbeddingProviderFactory.create_provider()`

All of this happens in a synchronous context during server initialization, but the actual providers don't create async resources. The TaskGroup error suggests something else is trying to run async code in the wrong context.

## Possible Causes

1. **LanceDB initialization**: The user has `"provider": "lancedb"` - there might be async initialization in the LanceDB provider
2. **MCP SDK issue**: The error comes from the MCP SDK itself, possibly due to how the server lifespan is managed
3. **Ubuntu-specific asyncio behavior**: Ubuntu's stricter asyncio implementation might be catching an issue that macOS doesn't

## Next Steps

1. Check LanceDB provider initialization for async resource creation
2. Review MCP server lifespan management
3. Add better error logging to identify the exact location of the TaskGroup error
4. Test with DuckDB provider to isolate if it's LanceDB-specific

# History

## 2025-07-10

Initial investigation identified that the issue persists despite fixing the OpenAI provider's lazy initialization. The error occurs with OpenAI-compatible provider configuration on Ubuntu when running MCP from a different directory.