#!/bin/bash

# Initialize MCP production crash test environment
set -e

echo "=== ChunkHound MCP Test Environment Setup ==="
echo "$(date): Setting up test environment"

# Clean up any existing test environment
rm -rf mcp-test-env test-logs
# Create test directory structure
mkdir -p mcp-test-env/test-data/source
mkdir -p mcp-test-env/mcp-workdir
mkdir -p test-logs

# Create test Python file
cat > mcp-test-env/test-data/source/calculator.py << 'EOF'
def calculate_sum(a, b):
    """Calculate the sum of two numbers"""
    return a + b

def calculate_product(a, b):
    """Calculate the product of two numbers"""
    return a * b

class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = calculate_sum(a, b)
        self.history.append(f"add({a}, {b}) = {result}")
        return result
    
    def multiply(self, a, b):
        result = calculate_product(a, b)
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result
    
    def get_history(self):
        return self.history
EOF

# Create test configuration with absolute paths
TEST_ROOT=$(pwd)/mcp-test-env
cat > mcp-test-env/mcp-workdir/chunkhound.json << EOF
{
    "index": {
        "path": "${TEST_ROOT}/test-data/source"
    },
    "embeddings": {
        "provider": "openai",
        "model": "all-minilm",
        "base_url": "http://localhost:11434/v1"
    },
    "database": {
        "path": "${TEST_ROOT}/mcp-workdir/.chunkhound/test.db"
    }
}
EOF

echo "$(date): Test environment created in mcp-test-env/"

# Test 1: Index from source directory
echo "$(date): Test 1 - Indexing from source directory"
cd mcp-test-env/test-data/source
uv run ../../../cli_wrapper.py index --config ../../mcp-workdir/chunkhound.json 2>&1 | tee ../../../test-logs/index.log
cd - > /dev/null

# Test 2: Start MCP server from different directory and test JSON-RPC
echo "$(date): Test 2 - Testing MCP server from different directory"
cd mcp-test-env/mcp-workdir

# Create a combined JSON-RPC test sequence
cat > test-sequence.json << 'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"roots":{"listChanged":true},"sampling":{}},"clientInfo":{"name":"test-client","version":"1.0.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_semantic","arguments":{"query":"calculator function"}}}
EOF

# Run MCP server with the test sequence
timeout 30 uv run ../../cli_wrapper.py mcp --config chunkhound.json --debug < test-sequence.json > ../../test-logs/mcp-session.log 2>&1 || echo "MCP session failed"

cd - > /dev/null

# Check for errors
echo "$(date): Checking for errors..."
if grep -q "Error\|Exception\|Traceback\|RuntimeError" test-logs/*.log; then
    echo "$(date): ERRORS DETECTED! Check test-logs/ for details"
    echo "=== ERROR SUMMARY ==="
    grep -A 3 -B 3 "Error\|Exception\|Traceback\|RuntimeError" test-logs/*.log | head -20
    echo "================="
else
    echo "$(date): No errors detected"
fi

echo "$(date): Test completed. Check test-logs/ for detailed logs"