# 2025-07-10T09:41:00+03:00 - [FEATURE] Configurable Periodic Background Indexing

**Priority**: Medium

## Description
Make periodic background indexing in the MCP server configurable through the config file. Users need to control the indexing interval (in minutes) and the ability to completely disable it. This is an advanced config that should be supported only from the config file (`.chunkhound.json`), not from CLI args.

## Requirements

### Functional Requirements
1. Add periodic indexing configuration to centralized config system
2. Support the following settings:
   - `periodic_enabled` (bool): Enable/disable periodic indexing entirely
   - `periodic_interval_minutes` (int): Interval between scans in minutes (default: 5)
   - `periodic_batch_size` (int): Files to process per batch (default: 10)
   - `periodic_quiet_minutes` (int): Minutes of inactivity before database optimization (default: 5)

### Implementation Scope
1. Add periodic indexing settings to `IndexingConfig` class
2. Update `Config` class to load these settings from config file
3. Maintain backward compatibility with existing environment variables:
   - `CHUNKHOUND_PERIODIC_INDEX_ENABLED`
   - `CHUNKHOUND_PERIODIC_INDEX_INTERVAL` (convert from seconds to minutes)
   - `CHUNKHOUND_PERIODIC_BATCH_SIZE`
4. Update `PeriodicIndexManager.from_environment()` to use centralized config
5. Configuration hierarchy (highest to lowest priority):
   - Config file (`.chunkhound.json`)
   - Environment variables (for backward compatibility)
   - Default values

### Example Configuration
```json
{
  "indexing": {
    "periodic_enabled": true,
    "periodic_interval_minutes": 10,
    "periodic_batch_size": 20,
    "periodic_quiet_minutes": 15
  }
}
```

### Affected Components
- `/chunkhound/core/config/indexing_config.py` - Add periodic fields
- `/chunkhound/core/config/config.py` - Update env var loading
- `/chunkhound/periodic_indexer.py` - Use centralized config
- `/chunkhound/mcp_server.py` - Pass config to PeriodicIndexManager

### Testing Requirements
1. Config file loading with periodic settings
2. Environment variable backward compatibility
3. Disable periodic indexing when `periodic_enabled=false`
4. Verify interval conversion (minutes to seconds)

### Non-Goals
- CLI argument support (config file only)
- UI/UX changes
- Breaking existing environment variable behavior