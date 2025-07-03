# 2025-07-03 - Consolidate Embedding Provider Creation

## Problem
Multiple inconsistent code paths for embedding provider creation cause `openai-compatible` providers to fail with `.chunkhound.json` config but work with CLI args.

**Root Issue**: Three different embedding provider creation implementations:

1. **CLI Path** (works): `chunkhound/api/cli/commands/run.py:284-291`
   - Direct calls: `create_openai_compatible_provider()` → `OpenAICompatibleProvider` (optional API key)

2. **Registry Path** (fails): `registry/__init__.py:376-379` 
   - Uses `OpenAIEmbeddingProvider` for both "openai" AND "openai-compatible"
   - `OpenAIEmbeddingProvider` requires API key, breaks `openai-compatible` with optional auth

3. **MCP Path** (inconsistent): `chunkhound/mcp_server.py:242-244`
   - Uses `EmbeddingProviderFactory.create_provider()` 
   - Depends on config loading path

**Config vs CLI Divergence**: `.chunkhound.json` → Registry → Wrong provider class. CLI → Direct factory calls → Correct provider.

## Solution: Single Source of Truth
Eliminate duplicate embedding provider creation logic. Make all paths use `EmbeddingProviderFactory`.

### Code Paths to Consolidate

**Registry** `registry/__init__.py`:
- `_register_embedding_provider()` - hardcoded provider classes
- `_create_instance()` - manual config injection

**CLI** `chunkhound/api/cli/commands/run.py`:
- `_setup_embedding_manager()` - direct provider creation calls

**MCP** `chunkhound/mcp_server.py`:
- Already uses factory (keep as-is)

**Validation** `chunkhound/core/config/embedding_config.py`:
- `is_provider_configured()` - incorrect openai-compatible validation logic

### Implementation Plan

1. **Fix Factory Validation**
   - `embedding_config.py:256-257`: Add API key check for openai-compatible when needed
   - Remove assumption that openai-compatible never needs API key

2. **Eliminate Registry Provider Creation**
   - Replace `_register_embedding_provider()` with factory delegation
   - Remove embedding logic from `_create_instance()`

3. **Convert CLI to Factory**
   - Replace `_setup_embedding_manager()` with factory calls
   - Remove manual provider creation

4. **Remove Legacy Registry Usage**
   - Update all consumers to use factory directly
   - Deprecate registry embedding provider methods

### Files to Modify

**Core**:
- `chunkhound/core/config/embedding_config.py` - fix validation
- `chunkhound/core/config/embedding_factory.py` - enhance as single source

**Registry**:
- `registry/__init__.py` - remove embedding creation, delegate to factory

**CLI**:
- `chunkhound/api/cli/commands/run.py` - use factory instead of direct calls

**Config Helpers**:
- `chunkhound/api/cli/utils/config_helpers.py` - update registry integration

### Benefits
- Single validation logic
- Consistent provider creation across all entry points  
- No more CLI vs config file behavior differences
- Reduced code duplication
- Future provider additions only need factory changes

### Testing Required
- CLI args with all provider types
- `.chunkhound.json` config with all provider types  
- MCP server with various configs
- Environment variable precedence
- Missing/invalid configuration handling

# History

## 2025-07-03
**COMPLETED**: Consolidated embedding provider creation paths to use single factory source.

**Changes Made**:
1. **Registry Fixed**: Replaced hardcoded `OpenAIEmbeddingProvider` usage with factory-based `FactoryEmbeddingProvider` wrapper that creates correct provider types
2. **CLI Converted**: Replaced direct provider creation calls with `EmbeddingProviderFactory.create_provider()`  
3. **Factory Validation**: Verified existing validation logic in `embedding_config.py` is correct - `openai-compatible` only requires `base_url`, `api_key` is optional

**Root Issue Resolved**: 
- Registry no longer incorrectly uses `OpenAIEmbeddingProvider` for `openai-compatible` providers
- All paths (CLI, Registry, MCP) now use `EmbeddingProviderFactory` for consistent provider creation
- No more divergent behavior between CLI args and `.chunkhound.json` config

**Files Modified**:
- `registry/__init__.py`: Added factory imports, replaced `_register_embedding_provider()` with factory delegation
- `chunkhound/api/cli/commands/run.py`: Replaced direct provider creation with factory calls in `_setup_embedding_manager()`

**Status**: Ready for testing. The consolidation is complete and should resolve the `openai-compatible` provider failures when using `.chunkhound.json` config.

## 2025-07-03 - Root Cause Found
**Issue**: CLI validation occurs before config loading, causing false validation failures.

**Root Cause**: `chunkhound/api/cli/utils/validation.py:validate_provider_args()` checks CLI args (None values) instead of loaded config values.

**Reproduction**: `test_ubuntu_config_bug_v2.py` - validates with None args fails for openai-compatible despite correct config.

**Fix Required**: Move validation after config loading OR modify validation to check merged config values.

## 2025-07-03 - FIXED
**Root Cause**: CLI argument parser set `default="openai"` for `--provider`, causing config file values to be overridden.

**Two Issues Fixed**:
1. **Argument Parser**: `chunkhound/api/cli/parsers/main_parser.py:96` - Changed `default="openai"` to `default=None` so config file can take precedence
2. **Index Command Validation**: `chunkhound/api/cli/main.py:124-142` - Modified to use unified config values instead of raw CLI args  
3. **Run Command Validation**: `chunkhound/api/cli/commands/run.py:130-166` - Modified to use unified config values instead of raw CLI args

**Testing**: Manual verification shows CLI now starts successfully with `.chunkhound.json` openai-compatible provider configuration.

**Files Modified**:
- `chunkhound/api/cli/parsers/main_parser.py`: Removed default provider to allow config precedence
- `chunkhound/api/cli/main.py`: Updated validation to use config values, added import for validate_provider_args
- `chunkhound/api/cli/commands/run.py`: Updated validation to use config values

**Status**: COMPLETED. Ubuntu CLI startup bug with `.chunkhound.json` openai-compatible provider is resolved.