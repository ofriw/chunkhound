# ChunkHound Search Freshness Test Environment

This directory contains a dedicated testing environment for validating realtime incremental updates in ChunkHound's search functionality.

## Problem Being Investigated

The currently running chunkhound instance (via IDE, exposed as `search_semantic` and `search_regex`) fails with realtime, incremental updates. File modifications and deletions aren't properly reflected in search results.

**Bug Slug**: `realtime-search-cache-staleness`

## Test Environment Components

### 1. `minimal_mcp_server.py`
- Standalone MCP server for isolated testing
- Uses separate test database to avoid interference with running instance
- Comprehensive logging for debugging cache behavior
- Provides all search tools: `search_semantic`, `search_regex`, `get_stats`, `health_check`
- Additional tools for testing: `index_file`, `delete_file`

### 2. `test_client.py`
- External MCP client for independent validation
- Comprehensive search freshness test suite
- Tests file creation, modification, and deletion scenarios
- Validates search result staleness within 2-5 second windows

### 3. `run_test.sh`
- Automated test runner script
- Environment setup and cleanup
- Comprehensive logging and result reporting
- Requires `OPENAI_API_KEY` for semantic search testing

## Usage

### Prerequisites
```bash
# Set OpenAI API key for semantic search testing
export OPENAI_API_KEY="your-api-key-here"

# Navigate to test environment
cd chunkhound/test_env
```

### Run Test Suite
```bash
# Run complete search freshness test
./run_test.sh
```

### Manual Testing
```bash
# Start server manually (in one terminal)
python minimal_mcp_server.py

# Run client tests (in another terminal)
python test_client.py
```

## Test Scenarios

### Phase 1: Initial Indexing
- Create test files with unique markers
- Index files through MCP server
- Validate initial search results

### Phase 2: File Modification
- Modify file content with new unique markers
- Re-index through MCP server
- Validate that old content is removed from search
- Validate that new content appears in search

### Phase 3: File Deletion
- Delete file from filesystem and index
- Validate that deleted content is removed from search
- Ensure no stale results remain

### Phase 4: Search Result Freshness
- Test timing between file operations and search result updates
- Validate both regex and semantic search consistency
- Identify any caching layers causing staleness

## Expected Behavior

✅ **PASS Criteria:**
- New file content appears in search within 5 seconds
- Modified file content reflects changes within 5 seconds  
- Deleted file content disappears from search within 5 seconds
- No stale/cached results from previous file states

❌ **FAIL Criteria:**
- Search results show old content after file modification
- Search results show deleted content after file removal
- Inconsistency between regex and semantic search results
- Cache invalidation delays exceeding 5 seconds

## Debugging

### Log Files
- `test_mcp_server.log` - Server operations and timing
- `test_client.log` - Client operations and validation
- `test_chunks.duckdb` - Isolated test database

### Key Metrics to Monitor
- File indexing completion time
- Search query execution time
- Database update consistency
- Cache invalidation timing

### Common Issues
1. **Database Connection**: Verify test database is created and accessible
2. **Service Initialization**: Check embedding provider initialization
3. **File Processing**: Monitor incremental processing results
4. **Search Caching**: Identify caching layers in search pipeline

## Integration with Main Investigation

This test environment is designed to:
1. **Isolate the problem** from the running production instance
2. **Validate hypothesis** about search result cache staleness
3. **Identify specific caching layers** causing the issue
4. **Provide controlled environment** for testing fixes

Results from this testing will inform the fix for the main `realtime-search-cache-staleness` bug affecting the production chunkhound instance.

## Environment Variables

- `OPENAI_API_KEY` - Required for semantic search testing
- `TEST_DB_PATH` - Optional custom database path (default: `./test_chunks.duckdb`)
- `MCP_SERVER_CMD` - Optional custom server command (default: `python minimal_mcp_server.py`)

## Notes

- Test database is automatically cleaned up between runs
- Test files are created in `./test_data/` directory
- Server runs on stdio transport for simplicity
- All operations are logged with timestamps for timing analysis