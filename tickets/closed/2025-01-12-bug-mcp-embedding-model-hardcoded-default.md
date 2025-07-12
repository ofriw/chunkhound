# 2025-01-12 - [BUG] MCP Server Hardcodes Embedding Model Default Instead of Using Config
**Priority**: High

## Issue Description

The MCP server hardcodes the embedding model default to `"text-embedding-3-small"` in the `search_semantic` function instead of using the model from the configuration system. This causes semantic search to fail when the index was created with a different model (e.g., `text-embedding-3-large`).

## Root Cause

**Location**: `chunkhound/mcp_server.py:925`
```python
model = arguments.get("model", "text-embedding-3-small")  # HARDCODED DEFAULT
```

The MCP server should use the configured model from `config.embedding.model` or `config.get_embedding_model()` instead of hardcoding a default.

## Symptom

When a user:
1. Indexes with `text-embedding-3-large` (via env vars or config)
2. Uses MCP server for semantic search without explicitly specifying model
3. Gets no search results because:
   - Query embedding generated with `text-embedding-3-small` (hardcoded default)
   - Stored embeddings generated with `text-embedding-3-large` (from indexing)
   - Different models = different vector spaces = no matches

## Evidence

1. **GitHub Issue**: https://github.com/ofriw/chunkhound/issues/3
2. **Database Schema**: Stores both `provider` and `model` with embeddings
3. **Config System**: Has `config.embedding.model` and `config.get_embedding_model()` available
4. **MCP Server**: Has access to `config` object at server startup (line 246)

## Expected Fix

Replace hardcoded default with config-based default:

```python
# WRONG (current)
model = arguments.get("model", "text-embedding-3-small")

# CORRECT (should be)
model = arguments.get("model", config.get_embedding_model())
```

## Impact

- **High**: Breaks semantic search when using non-default embedding models
- **User Experience**: Silent failure - no error, just no results
- **Workaround**: User must manually specify model in every search call

## Related Code

- MCP server startup: `chunkhound/mcp_server.py:245-256` (config available)
- Embedding config: `chunkhound/core/config/embedding_config.py:246-266`
- Database schema: Stores `provider` and `model` fields with embeddings

# History

## 2025-01-12T19:30:00-08:00
Issue identified from GitHub issue #3. User reported semantic search failing when using `text-embedding-3-large` for indexing but MCP server defaulting to `text-embedding-3-small` for queries. Root cause traced to hardcoded default in MCP server semantic search function.

## 2025-01-12T19:45:00-08:00
**FIXED**: Implemented solution to use embedding manager configuration instead of hardcoded defaults.

### Implementation Details
- **Location**: `chunkhound/mcp_server.py:925-940`
- **Change**: Replaced hardcoded defaults with dynamic lookup from `_embedding_manager.get_provider()`
- **Approach**: 
  - Get default provider and model from the configured embedding manager
  - Fall back to hardcoded defaults only if no embedding manager or provider configured
  - Preserves backward compatibility while fixing the core issue

### Code Changes
```python
# BEFORE (hardcoded)
provider = arguments.get("provider", "openai")
model = arguments.get("model", "text-embedding-3-small")

# AFTER (config-based with fallback)
default_provider = "openai"
default_model = "text-embedding-3-small"
if _embedding_manager:
    try:
        default_provider_obj = _embedding_manager.get_provider()
        default_provider = default_provider_obj.name
        default_model = default_provider_obj.model
    except ValueError:
        # No default provider configured, use fallback defaults
        pass

provider = arguments.get("provider", default_provider)
model = arguments.get("model", default_model)
```

### Testing
- **Manual Test**: Index with `text-embedding-3-large`, verify MCP semantic search uses same model
- **Verification**: Check that `arguments.get("model", default_model)` now returns configured model instead of hardcoded `"text-embedding-3-small"`

### Additional Fixes
Also fixed related issue in `EmbeddingConfig.get_provider_config()` to use `get_default_model()` instead of raw `self.model` which could be None.

**Location**: `chunkhound/core/config/embedding_config.py:213`
**Change**: `"model": self.get_default_model()` instead of `"model": self.model`

### Final Architecture Fix
Completely redesigned the default resolution to eliminate hardcoded defaults in operational code:

**MCP Server**: `chunkhound/mcp_server.py:925-946`
- Removed ALL hardcoded fallbacks
- Always gets model from configured embedding manager
- Fails fast if no provider configured (proper error handling)

**Config System**: `chunkhound/core/config/embedding_config.py:213`
- `get_provider_config()` always calls `get_default_model()` 
- Ensures factory always receives resolved model

**Factory**: `chunkhound/core/config/embedding_factory.py:94-95`  
- Expects model to always be present
- Fails fast with clear error if model missing

**Result**: Model is ALWAYS determined by provider configuration, never by hardcoded defaults in operational code. Provider-specific defaults remain centralized in `EmbeddingConfig.get_default_model()` for proper abstraction.

### Status
✅ **RESOLVED**: Embedding model is now strictly coupled to provider configuration. MCP server will use exactly the same model that was used during indexing.

## 2025-01-12T20:15:00-08:00
**TICKET CLOSED**: All fixes implemented and validated.

### Summary of Changes
1. **Root Cause Fixed**: MCP server hardcoded `"text-embedding-3-small"` default removed
2. **Architecture Improved**: All model resolution now flows through proper config system
3. **Provider Coupling**: Model selection is strictly tied to embedding provider configuration
4. **Error Handling**: Proper fail-fast behavior when no provider configured

### Validation
- ✅ MCP server uses embedding manager configuration instead of hardcoded defaults
- ✅ Factory expects resolved models and fails fast if missing
- ✅ Config system centralizes all default resolution logic
- ✅ No more vector space mismatches between indexing and search

### GitHub Issue Status
GitHub issue #3 (https://github.com/ofriw/chunkhound/issues/3) can now be closed - semantic search will work correctly when using non-default embedding models like `text-embedding-3-large`.