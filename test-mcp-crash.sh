#!/bin/bash

# Test script to reproduce MCP production crash
set -e

echo "=== ChunkHound MCP Production Crash Simulation ==="
echo "$(date): Starting test scenario"

# Create logs directory
mkdir -p test-logs

# Ensure Ollama is running
echo "$(date): Checking Ollama status..."
if ! curl -s http://localhost:11434/api/version > /dev/null; then
    echo "ERROR: Ollama is not running on localhost:11434"
    echo "Please start Ollama with: ollama serve"
    exit 1
fi

# Build test container
echo "$(date): Building test container..."
docker-compose -f docker-compose.mcp-test.yml build

# Start container
echo "$(date): Starting test container..."
docker-compose -f docker-compose.mcp-test.yml up -d

# Wait for container to be ready
echo "$(date): Waiting for container to be ready..."
sleep 5

# Step 1: Index the test data from source directory
echo "$(date): Step 1 - Indexing test data..."
docker-compose -f docker-compose.mcp-test.yml exec -T mcp-test bash -c "
    cd /test-data/source && \
    /root/.cargo/bin/uv run /chunkhound/chunkhound index --config /mcp-workdir/chunkhound.json
" 2>&1 | tee test-logs/index.log

# Step 2: Start MCP server from different directory
echo "$(date): Step 2 - Starting MCP server from /mcp-workdir..."
docker-compose -f docker-compose.mcp-test.yml exec -d mcp-test bash -c "
    cd /mcp-workdir && \
    /root/.cargo/bin/uv run /chunkhound/chunkhound mcp --config /mcp-workdir/chunkhound.json --debug
" 2>&1 | tee test-logs/mcp-server.log &

# Wait for MCP server to start
sleep 10

# Step 3: Send JSON-RPC commands to trigger crash
echo "$(date): Step 3 - Sending JSON-RPC commands..."
docker-compose -f docker-compose.mcp-test.yml exec -T mcp-test bash -c '
    cd /mcp-workdir
    
    # MCP handshake
    echo "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{\"roots\":{\"listChanged\":true},\"sampling\":{}},\"clientInfo\":{\"name\":\"test-client\",\"version\":\"1.0.0\"}}}" | /root/.cargo/bin/uv run /chunkhound/chunkhound mcp --config /mcp-workdir/chunkhound.json 2>&1
    
    # Wait a bit
    sleep 2
    
    # Try semantic search
    echo "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"search_semantic\",\"arguments\":{\"query\":\"calculator function\"}}}" | /root/.cargo/bin/uv run /chunkhound/chunkhound mcp --config /mcp-workdir/chunkhound.json 2>&1
' 2>&1 | tee test-logs/jsonrpc.log

# Capture any crash logs
echo "$(date): Capturing crash logs..."
docker-compose -f docker-compose.mcp-test.yml logs > test-logs/docker-logs.log 2>&1

# Check for crash indicators
if grep -q "Error\|Exception\|Traceback" test-logs/docker-logs.log; then
    echo "$(date): CRASH DETECTED! Check test-logs/ for details"
    echo "=== CRASH SUMMARY ==="
    grep -A 5 -B 5 "Error\|Exception\|Traceback" test-logs/docker-logs.log | head -20
    echo "======================"
else
    echo "$(date): No crash detected in this run"
fi

# Cleanup
echo "$(date): Cleaning up..."
docker-compose -f docker-compose.mcp-test.yml down

echo "$(date): Test completed. Check test-logs/ for detailed logs"