# 2025-01-09 - [BUG] MCP Server Import Structure Fix
**Priority**: High

Fix MCP server crash with "unhandled errors in a TaskGroup" caused by incorrect import paths and package structure issues.

# History

## 2025-01-09
Found root cause of MCP server crash when running `uv run chunkhound mcp /path/to/code`:

**Issue**: The error "unhandled errors in a TaskGroup (1 sub-exception)" was masking the real problem - import failures due to incorrect module paths.

**Root Causes**:
1. **Split package structure**: Code is split between root directory (`/core`, `/registry`, `/providers`, etc.) and package directory (`/chunkhound/core`, `/chunkhound/api`, etc.)
2. **Incorrect imports**: Many files used relative imports like `from core.types import` instead of `from chunkhound.core.types.common import`
3. **Module resolution failure**: When running from a different directory, Python couldn't resolve modules not under the `chunkhound` package

**Fixed Files**:
- `chunkhound/database_factory.py`: Changed `from registry import` to `from chunkhound.registry import`
- `registry/__init__.py`: Fixed all imports to use full paths (e.g., `from chunkhound.core.types.common import Language`)
- `chunkhound/database.py`: Fixed imports for core.types and registry
- `providers/database/duckdb_provider.py`: Fixed core and provider imports
- `providers/database/lancedb_provider.py`: Fixed core imports
- `providers/database/duckdb/*.py`: Fixed imports in repository files
- `providers/embeddings/openai_provider.py`: Fixed core.exceptions import
- `providers/parsing/*.py`: Fixed imports in all parser files (43 files total)
- `services/*.py`: Fixed imports in service files
- `interfaces/*.py`: Fixed imports in interface files
- `chunkhound/file_watcher.py`: Fixed core.types import
- `registry/__init__.py`: Fixed None config handling in `_register_embedding_provider`

**Additional Issues Found**:
- The registry was trying to call `model_dump()` on a None `embedding_config` object
- Fixed by adding null check: `embedding_config.model_dump() if embedding_config else {}`

**Fundamental Issue**: 
The package structure needs reorganization. Having modules split between the root directory and the package directory causes import resolution issues when the package is run from different locations. All code should be under the `chunkhound` package directory for proper packaging.

**Status**: Fixed all import paths. MCP server should now start correctly when run from any directory.