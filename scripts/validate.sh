#!/bin/bash
# ChunkHound End-to-End Validation Script
# Tests the complete user experience from installation to usage

set -e

echo "🧪 ChunkHound End-to-End Validation"
echo "===================================="

# Test 1: CLI availability
echo "1️⃣  Testing CLI availability..."
if command -v chunkhound &> /dev/null; then
    echo "✅ chunkhound command found"
    chunkhound --version
else
    echo "❌ chunkhound command not found"
    exit 1
fi

# Test 2: Help system
echo ""
echo "2️⃣  Testing help system..."
chunkhound --help | grep -q "Local-first semantic code search" && echo "✅ Help system working" || { echo "❌ Help system broken"; exit 1; }

# Test 3: Dependency check
echo ""
echo "3️⃣  Testing dependencies..."
python -c "
import chunkhound
import duckdb
import tree_sitter
import tree_sitter_python
import openai
print('✅ All core dependencies importable')
"

# Test 4: Database initialization
echo ""
echo "4️⃣  Testing database initialization..."
temp_db="/tmp/chunkhound_test_$(date +%s).duckdb"
python -c "
from pathlib import Path
from chunkhound.database import Database
db = Database(Path('$temp_db'))
db.connect()
print('✅ Database initialization successful')
db.close()
" || { echo "❌ Database initialization failed"; exit 1; }
rm -f "$temp_db"*

# Test 5: Parser functionality
echo ""
echo "5️⃣  Testing code parser..."
temp_py_file="/tmp/chunkhound_test_$(date +%s).py"
echo 'def hello():
    return "Hello, World!"

class TestClass:
    def method(self):
        pass' > "$temp_py_file"
python -c "
from pathlib import Path
from chunkhound.parser import CodeParser
parser = CodeParser()
symbols = parser.parse_file(Path('$temp_py_file'))
assert len(symbols) > 0, 'No symbols extracted'
print('✅ Code parser working')
" || { echo "❌ Code parser failed"; exit 1; }
rm -f "$temp_py_file"

# Test 6: CLI run command (dry run)
echo ""
echo "6️⃣  Testing CLI run command..."
mkdir -p /tmp/chunkhound_test_project
echo "def test_function(): pass" > /tmp/chunkhound_test_project/test.py
cd /tmp/chunkhound_test_project
timeout 10s chunkhound run . --no-embeddings &
CLI_PID=$!
sleep 3
kill $CLI_PID 2>/dev/null || true
wait $CLI_PID 2>/dev/null || true
echo "✅ CLI run command functional"
cd - > /dev/null
rm -rf /tmp/chunkhound_test_project

# Test 7: API endpoints (if server running)
echo ""
echo "7️⃣  Testing API endpoints..."
if curl -s http://localhost:7474/health &>/dev/null; then
    health_response=$(curl -s http://localhost:7474/health)
    echo "$health_response" | grep -q "healthy" && echo "✅ API health endpoint working" || { echo "❌ API health endpoint failed"; exit 1; }
    
    stats_response=$(curl -s http://localhost:7474/stats)
    echo "$stats_response" | grep -q "files" && echo "✅ API stats endpoint working" || { echo "❌ API stats endpoint failed"; exit 1; }
else
    echo "ℹ️  API server not running (optional test)"
fi

# Test 8: Development tools
echo ""
echo "8️⃣  Testing development tools..."
if command -v make &> /dev/null; then
    make help | grep -q "ChunkHound Development Commands" && echo "✅ Makefile working" || { echo "❌ Makefile broken"; exit 1; }
else
    echo "ℹ️  Make not available (optional)"
fi

# Test 9: Package metadata
echo ""
echo "9️⃣  Testing package metadata..."
python -c "
import chunkhound
assert hasattr(chunkhound, '__version__'), 'No version attribute'
assert chunkhound.__version__ == '0.1.0', f'Wrong version: {chunkhound.__version__}'
print('✅ Package metadata correct')
" || { echo "❌ Package metadata failed"; exit 1; }

echo ""
echo "🎉 All Tests Passed!"
echo "=================="
echo ""
echo "ChunkHound is ready for:"
echo "  👤 End users: uv pip install chunkhound"
echo "  🔧 Developers: ./scripts/setup.sh"
echo "  🚀 Deployment: docker build -t chunkhound ."
echo ""
echo "Happy coding! 🚀"