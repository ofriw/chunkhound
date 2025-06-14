#!/bin/bash
set -e

# Test runner script for realtime search freshness validation
# This script sets up the test environment and runs the search freshness test

echo "=== ChunkHound Search Freshness Test Runner ==="
echo "Testing realtime incremental updates with isolated MCP server"
echo ""

# Check if we're in the right directory
if [ ! -f "minimal_mcp_server.py" ]; then
    echo "Error: Must be run from chunkhound/test_env directory"
    exit 1
fi

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable not set"
    echo "Semantic search tests will be disabled"
    echo "Set OPENAI_API_KEY to enable full testing"
    exit 1
fi

# Clean up any existing test database
TEST_DB_PATH="./test_chunks.duckdb"
if [ -f "$TEST_DB_PATH" ]; then
    echo "Removing existing test database: $TEST_DB_PATH"
    rm -f "$TEST_DB_PATH"
fi

# Clean up any existing test data
if [ -d "./test_data" ]; then
    echo "Removing existing test data directory"
    rm -rf "./test_data"
fi

# Clean up any existing log files
if [ -f "test_mcp_server.log" ]; then
    rm -f "test_mcp_server.log"
fi

if [ -f "test_client.log" ]; then
    rm -f "test_client.log"
fi

echo "Environment cleaned up"
echo ""

# Export environment variables for the test
export TEST_DB_PATH="$TEST_DB_PATH"
export MCP_SERVER_CMD="python minimal_mcp_server.py"

# Run the test
echo "Starting search freshness test..."
echo "Database: $TEST_DB_PATH"
echo "Server command: $MCP_SERVER_CMD"
echo ""

# Run the client test
python test_client.py

TEST_EXIT_CODE=$?

echo ""
echo "=== Test Results ==="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ SEARCH FRESHNESS TEST PASSED"
    echo "   Realtime incremental updates are working correctly"
else
    echo "❌ SEARCH FRESHNESS TEST FAILED"
    echo "   Realtime incremental updates have issues"
fi

echo ""
echo "=== Log Files ==="
echo "Server log: test_mcp_server.log"
echo "Client log: test_client.log"

if [ -f "test_mcp_server.log" ]; then
    echo ""
    echo "=== Server Log Tail ==="
    tail -20 test_mcp_server.log
fi

if [ -f "test_client.log" ]; then
    echo ""
    echo "=== Client Log Tail ==="
    tail -10 test_client.log
fi

echo ""
echo "=== Test Database ==="
if [ -f "$TEST_DB_PATH" ]; then
    echo "Test database created: $TEST_DB_PATH"
    echo "Database size: $(du -h "$TEST_DB_PATH" | cut -f1)"
else
    echo "No test database found (may indicate initialization failure)"
fi

echo ""
echo "=== Next Steps ==="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "1. Review logs to understand timing characteristics"
    echo "2. Compare with production MCP server behavior"
    echo "3. Run additional edge case tests if needed"
else
    echo "1. Review server and client logs for error details"
    echo "2. Check database initialization and connection"
    echo "3. Verify search result freshness timing"
    echo "4. Test with different file types and patterns"
fi

echo ""
echo "Test completed with exit code: $TEST_EXIT_CODE"

exit $TEST_EXIT_CODE
