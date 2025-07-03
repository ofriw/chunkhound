# Version Management

## Overview

ChunkHound uses a centralized version management approach where the version is defined in a single location and automatically synchronized across all files that need it.

## Single Source of Truth

The version is defined in `chunkhound/version.py`:

```python
__version__ = "2.1.0"
```

## Files That Use the Version

The following files automatically import and use the version from `version.py`:

1. **`chunkhound/__init__.py`** - Main package version
2. **`chunkhound/api/cli/parsers/main_parser.py`** - CLI `--version` flag
3. **`chunkhound/api/cli/commands/run.py`** - Displayed during CLI startup
4. **`chunkhound/mcp_server.py`** - MCP server version (health check and initialization)

## Updating the Version

To update the version for a new release:

```bash
# Update to a new version (e.g., 2.2.0)
uv run scripts/update_version.py 2.2.0

# This will:
# 1. Update chunkhound/version.py
# 2. Update pyproject.toml
# 3. Show next steps for committing and tagging
```

## Version Sync Script

The `scripts/sync_version.py` script ensures `pyproject.toml` stays in sync with `version.py`:

```bash
# Run manually to verify versions are in sync
uv run scripts/sync_version.py
```

## Version Format

Versions follow semantic versioning: `MAJOR.MINOR.PATCH` (e.g., `2.1.0`)

Optional pre-release suffixes are supported: `MAJOR.MINOR.PATCH-suffix` (e.g., `2.1.0-beta1`)

## Benefits

1. **Single source of truth** - Only one place to update the version
2. **Automatic synchronization** - All components use the same version
3. **Build consistency** - PyInstaller builds will always have the correct version
4. **Reduced errors** - No more forgetting to update version in multiple places