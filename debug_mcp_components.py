#!/usr/bin/env python3
"""
MCP Component Startup Debug Script
Isolates which specific component is causing MCP server initialization failure.

Based on diagnostic results showing:
- Binary spawns successfully
- Exits with code 1 during initialization
- No database/filesystem issues
- Not environment-related

This script tests each initialization component in isolation.
"""

import subprocess
import time
import os
import sys
import tempfile
from pathlib import Path


def test_direct_import():
    """Test 1: Direct import of MCP components"""
    print("=== TEST 1: Direct Import Testing ===")

    components = [
        "chunkhound.mcp_entry",
        "chunkhound.mcp_server",
        "chunkhound.providers.database.duckdb_provider",
        "chunkhound.signal_coordinator",
        "chunkhound.providers.embeddings.embedding_manager",
        "chunkhound.file_watcher"
    ]

    results = {}

    for component in components:
        try:
            # Test import in subprocess to isolate crashes
            result = subprocess.run([
                sys.executable, "-c", f"import {component}; print('OK')"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                print(f"✅ {component}: Import successful")
                results[component] = True
            else:
                print(f"❌ {component}: Import failed")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
                results[component] = False

        except Exception as e:
            print(f"❌ {component}: Exception during import test: {e}")
            results[component] = False

    return results


def test_database_init():
    """Test 2: Database initialization in isolation"""
    print("\n=== TEST 2: Database Initialization ===")

    # Create temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        # Test database initialization
        test_code = f"""
import os
os.environ['CHUNKHOUND_DB_PATH'] = '{tmp_db_path}'

from chunkhound.providers.database.duckdb_provider import DuckDBProvider

# Test database creation and connection
db = DuckDBProvider('{tmp_db_path}')
db.connect()
print('Database connected successfully')

# Test VSS extension loading
try:
    db.execute('SELECT 1')
    print('Database queries working')
except Exception as e:
    print(f'Database query failed: {{e}}')

db.disconnect()
print('Database test completed')
"""

        result = subprocess.run([
            sys.executable, "-c", test_code
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print("✅ Database initialization successful")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ Database initialization failed")
            print(f"   Error: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"❌ Database test crashed: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(tmp_db_path)
        except:
            pass


def test_signal_coordinator():
    """Test 3: Signal coordinator initialization"""
    print("\n=== TEST 3: Signal Coordinator ===")

    test_code = """
import os
import tempfile
from pathlib import Path

# Create temporary coordination directory
with tempfile.TemporaryDirectory() as tmp_dir:
    os.environ['CHUNKHOUND_COORDINATION_DIR'] = tmp_dir

    from chunkhound.signal_coordinator import SignalCoordinator

    # Test coordinator setup
    coordinator = SignalCoordinator()
    coordinator.setup_mcp_signal_handling()
    print('Signal coordinator setup successful')

    # Test coordination directory creation
    coord_dir = Path(tmp_dir) / 'chunkhound-coordination'
    if coord_dir.exists():
        print('Coordination directory created')
    else:
        print('Coordination directory not created')

    print('Signal coordinator test completed')
"""

    try:
        result = subprocess.run([
            sys.executable, "-c", test_code
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            print("✅ Signal coordinator successful")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ Signal coordinator failed")
            print(f"   Error: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"❌ Signal coordinator test crashed: {e}")
        return False


def test_embedding_manager():
    """Test 4: Embedding manager initialization"""
    print("\n=== TEST 4: Embedding Manager ===")

    test_code = """
from chunkhound.providers.embeddings.embedding_manager import EmbeddingManager

# Test embedding manager creation
manager = EmbeddingManager()
print('Embedding manager created')

# Test provider loading
providers = manager.get_available_providers()
print(f'Available providers: {providers}')

print('Embedding manager test completed')
"""

    try:
        result = subprocess.run([
            sys.executable, "-c", test_code
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print("✅ Embedding manager successful")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ Embedding manager failed")
            print(f"   Error: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"❌ Embedding manager test crashed: {e}")
        return False


def test_mcp_server_init():
    """Test 5: MCP server initialization sequence"""
    print("\n=== TEST 5: MCP Server Initialization ===")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        test_code = f"""
import os
import asyncio
os.environ['CHUNKHOUND_MCP_MODE'] = '1'
os.environ['CHUNKHOUND_DB_PATH'] = '{tmp_db_path}'

async def test_server_init():
    from chunkhound.mcp_server import _database, _embedding_manager, _file_watcher
    from chunkhound.mcp_server import server_lifespan, Server

    print('Testing MCP server lifespan initialization...')

    # Create mock server
    server = Server("chunkhound")

    # Test server lifespan context manager
    async with server_lifespan(server) as resources:
        print('Server lifespan context entered successfully')
        print(f'Resources: {{list(resources.keys())}}')

        # Test individual components
        if resources.get('db'):
            print('Database component initialized')
        if resources.get('embeddings'):
            print('Embeddings component initialized')
        if resources.get('watcher'):
            print('File watcher component initialized')

    print('Server lifespan test completed')

# Run the async test
asyncio.run(test_server_init())
"""

        result = subprocess.run([
            sys.executable, "-c", test_code
        ], capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            print("✅ MCP server initialization successful")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ MCP server initialization failed")
            print(f"   Stdout: {result.stdout.strip()}")
            print(f"   Stderr: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"❌ MCP server test crashed: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(tmp_db_path)
        except:
            pass


def test_mcp_entry_direct():
    """Test 6: Direct MCP entry point execution"""
    print("\n=== TEST 6: MCP Entry Point ===")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        test_code = f"""
import os
import asyncio
import signal
import sys

os.environ['CHUNKHOUND_MCP_MODE'] = '1'
os.environ['CHUNKHOUND_DB_PATH'] = '{tmp_db_path}'

# Test the actual entry point
from chunkhound.mcp_entry import main

async def test_with_timeout():
    # Set up timeout to prevent hanging
    def timeout_handler():
        print('MCP entry point initialized successfully (timeout reached)')
        sys.exit(0)

    # Create task with timeout
    try:
        task = asyncio.create_task(main())
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        print('MCP entry point running (timeout after 2s - normal for MCP server)')
        return True
    except Exception as e:
        print(f'MCP entry point failed: {{e}}')
        return False

# Run the test
result = asyncio.run(test_with_timeout())
"""

        result = subprocess.run([
            sys.executable, "-c", test_code
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            print("✅ MCP entry point successful")
            print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ MCP entry point failed")
            print(f"   Stdout: {result.stdout.strip()}")
            print(f"   Stderr: {result.stderr.strip()}")
            return False

    except Exception as e:
        print(f"❌ MCP entry point test crashed: {e}")
        return False
    finally:
        # Cleanup
        try:
            os.unlink(tmp_db_path)
        except:
            pass


def main():
    """Run all component tests to isolate failure point"""
    print("ChunkHound MCP Component Startup Diagnostic")
    print("=" * 60)

    # Run component tests in order
    tests = [
        ("Direct Import", test_direct_import),
        ("Database Init", test_database_init),
        ("Signal Coordinator", test_signal_coordinator),
        ("Embedding Manager", test_embedding_manager),
        ("MCP Server Init", test_mcp_server_init),
        ("MCP Entry Point", test_mcp_entry_direct),
    ]

    results = {}
    failed_at = None

    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        try:
            result = test_func()
            results[test_name] = result

            if not result and failed_at is None:
                failed_at = test_name

        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
            if failed_at is None:
                failed_at = test_name

    # Summary
    print("\n" + "=" * 60)
    print("COMPONENT DIAGNOSTIC SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    # Root cause analysis
    print(f"\nROOT CAUSE ANALYSIS:")
    if failed_at:
        print(f"❌ FAILURE POINT: {failed_at}")
        print(f"   Components up to {failed_at} work correctly")
        print(f"   Issue is specifically in {failed_at} initialization")
    else:
        print("✅ ALL COMPONENTS PASS: Issue may be in component interaction or timing")

    # Specific recommendations
    print(f"\nNEXT INVESTIGATION STEPS:")
    if failed_at == "Direct Import":
        print("- Missing dependencies or import path issues")
        print("- Check PyInstaller bundle completeness")
    elif failed_at == "Database Init":
        print("- VSS extension loading issues")
        print("- DuckDB initialization problems")
    elif failed_at == "Signal Coordinator":
        print("- File permission issues in coordination directory")
        print("- Signal handling setup problems")
    elif failed_at == "Embedding Manager":
        print("- Embedding provider loading issues")
        print("- Network connectivity for provider validation")
    elif failed_at == "MCP Server Init":
        print("- AsyncIO event loop issues")
        print("- Resource initialization timing problems")
    elif failed_at == "MCP Entry Point":
        print("- JSON-RPC protocol setup issues")
        print("- stdin/stdout handling problems")
    else:
        print("- All components work individually")
        print("- Issue is likely in component interaction or binary-specific environment")

    return 0 if not failed_at else 1


if __name__ == "__main__":
    sys.exit(main())
