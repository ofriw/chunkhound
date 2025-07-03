# CLI Info Command Implementation

**Date**: 2025-07-03  
**Priority**: Medium  
**Status**: Ready for Implementation  

## Problem Statement

Users need a way to inspect their current ChunkHound database and configuration without digging through files or running multiple commands. Currently, there's no unified way to see:

- Database location, type, and size
- Statistics (files, chunks, embeddings indexed)
- Embedding models and providers in use
- Vector dimensions and configuration
- Overall database health

## Solution

Add a new `chunkhound info` CLI command that provides a comprehensive overview of the current database and configuration state.

## Requirements

### Core Functionality
- **Database Information**: Path, type (DuckDB/LanceDB), file size, connection status
- **Statistics**: File count, chunk count, embedding count (reuse existing `get_stats()`)
- **Model Detection**: Scan embedding tables to show all provider/model/dimension combinations used
- **Configuration**: Current config without sensitive data (API keys)
- **Health Status**: Database connectivity, configuration completeness

### Command Behavior
- **Default**: Human-readable output for terminal use
- **JSON Option**: `--json` flag for programmatic consumption
- **Error Handling**: Graceful handling when no database exists
- **Path Override**: Support `--db` flag like other commands

### Example Output

```
ChunkHound Database Info
========================

Database
--------
Path: /project/.chunkhound.db
Type: DuckDB
Size: 15.2 MB
Status: Connected

Statistics
----------
Files: 1,247
Chunks: 8,934
Embeddings: 8,934

Models & Providers
------------------
openai/text-embedding-3-small (1536 dimensions): 8,934 embeddings
openai/text-embedding-ada-002 (1536 dimensions): 0 embeddings

Configuration
-------------
Provider: openai
Model: text-embedding-3-small
API Key: *** (configured)
Batch Size: 100
Database Provider: duckdb
```

## Technical Implementation

### File Structure
```
chunkhound/api/cli/
├── parsers/
│   └── info_parser.py          # New: argument parser for info command
├── commands/
│   └── info.py                 # New: info command implementation
└── main.py                     # Modified: add info command routing
```

### Key Components

1. **Parser** (`info_parser.py`):
   ```python
   def add_info_subparser(subparsers) -> argparse.ArgumentParser:
       info_parser = subparsers.add_parser("info", help="Show database info")
       add_common_arguments(info_parser)
       add_database_argument(info_parser)
       info_parser.add_argument("--json", action="store_true", help="JSON output")
       return info_parser
   ```

2. **Command Implementation** (`info.py`):
   - Use existing `get_stats()` for database statistics
   - Query embedding tables to detect models/dimensions
   - Load unified config with `ChunkHoundConfig.load_hierarchical()`
   - Format output using `OutputFormatter`

3. **Database Model Detection**:
   ```python
   def detect_embedding_models(database_provider):
       # Query all embedding_* tables
       # Extract unique provider/model/dims combinations
       # Return list of model info with embedding counts
   ```

4. **Main Integration**:
   - Add `add_info_subparser(subparsers)` to `create_parser()`
   - Add `"info"` case to command routing in `async_main()`
   - Add validation logic for info command

### Dependencies
- **Existing**: `get_stats()`, `ChunkHoundConfig`, `OutputFormatter`
- **New**: Model detection logic, formatted output functions
- **External**: None (uses existing database connection patterns)

## Implementation Plan

### Phase 1: Core Structure
1. Create `info_parser.py` with basic argument parsing
2. Create `info.py` with skeleton command structure
3. Wire into main CLI parser and routing
4. Basic database path and connection info

### Phase 2: Data Collection
1. Implement database statistics gathering (reuse `get_stats()`)
2. Add embedding model detection logic
3. Configuration loading and sanitization
4. Database file size calculation

### Phase 3: Output Formatting
1. Human-readable format with sections
2. JSON output option
3. Error handling for missing database
4. Configuration validation and warnings

### Phase 4: Polish & Testing
1. Edge case handling (corrupted DB, missing config)
2. Performance optimization for large databases
3. Output format refinement
4. Integration testing with different database types

## Edge Cases & Considerations

1. **No Database**: Show config info only, warn about missing database
2. **Multiple Models**: Handle databases with multiple embedding providers/models
3. **Large Databases**: Ensure info command is fast even with millions of embeddings
4. **Corrupted Data**: Graceful handling of database connection failures
5. **Legacy Databases**: Handle old database schemas gracefully

## Success Criteria

- [ ] `chunkhound info` shows comprehensive database overview
- [ ] Command works with both DuckDB and LanceDB providers
- [ ] JSON output option for automation
- [ ] Handles missing database gracefully
- [ ] Performance: <1 second for typical databases
- [ ] Consistent with existing CLI patterns and error handling

## Notes

- Reuse existing patterns from `index` and `mcp` commands
- Leverage MCP server's `get_stats()` and `health_check()` logic
- Consider future extensibility for additional database info
- Keep output concise but informative for daily development use