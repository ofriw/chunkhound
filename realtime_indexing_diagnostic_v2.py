#!/usr/bin/env python3
"""
Real-time Indexing Diagnostic Script v2
=====================================

This script tests the current hypothesis about why real-time incremental indexing
isn't working, focusing on file watcher initialization status in the MCP server.

Based on investigation notes, all previous hypotheses have been disproven:
- Database path divergence: Fixed but issue persists
- Callback chain failure: Systematically disproven
- Database operations failure: Proven working perfectly
- Environment isolation: Investigated but inconclusive

New Hypothesis: File watcher is disabled or not properly initialized in MCP server
due to IDE timeout prevention measures.
"""

import os
import sys
import time
import asyncio
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

# Add chunkhound to path
sys.path.insert(0, str(Path(__file__).parent))

def log_with_timestamp(message: str, level: str = "INFO"):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {level}: {message}")

def test_mcp_process_status():
    """Test 1: Check if MCP server is running and with what parameters."""
    log_with_timestamp("=== TEST 1: MCP Process Status ===")

    try:
        result = subprocess.run([
            "ps", "aux"
        ], capture_output=True, text=True, timeout=10)

        mcp_processes = []
        for line in result.stdout.split('\n'):
            if 'chunkhound' in line and 'mcp' in line and 'grep' not in line:
                mcp_processes.append(line.strip())

        if mcp_processes:
            log_with_timestamp(f"Found {len(mcp_processes)} MCP process(es):", "SUCCESS")
            for i, process in enumerate(mcp_processes, 1):
                log_with_timestamp(f"  Process {i}: {process}")

                # Check if --watch parameter is present
                if '--watch' in process:
                    log_with_timestamp("  ✅ --watch parameter detected", "SUCCESS")
                else:
                    log_with_timestamp("  ❌ --watch parameter MISSING", "ERROR")
            return True
        else:
            log_with_timestamp("❌ No MCP processes found", "ERROR")
            return False

    except Exception as e:
        log_with_timestamp(f"❌ Process check failed: {e}", "ERROR")
        return False

def test_database_paths():
    """Test 2: Verify database path configuration."""
    log_with_timestamp("=== TEST 2: Database Path Configuration ===")

    try:
        # Check environment variable
        chunkhound_db_path = os.environ.get("CHUNKHOUND_DB_PATH")
        log_with_timestamp(f"CHUNKHOUND_DB_PATH env var: {chunkhound_db_path}")

        # Default CLI path
        default_cli_path = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"
        log_with_timestamp(f"Default CLI path: {default_cli_path}")
        log_with_timestamp(f"CLI database exists: {default_cli_path.exists()}")
        if default_cli_path.exists():
            stat = default_cli_path.stat()
            log_with_timestamp(f"CLI database size: {stat.st_size} bytes")
            log_with_timestamp(f"CLI database modified: {datetime.fromtimestamp(stat.st_mtime)}")

        # Project database path
        project_db_path = Path.cwd() / ".chunkhound.db"
        log_with_timestamp(f"Project database path: {project_db_path}")
        log_with_timestamp(f"Project database exists: {project_db_path.exists()}")
        if project_db_path.exists():
            stat = project_db_path.stat()
            log_with_timestamp(f"Project database size: {stat.st_size} bytes")
            log_with_timestamp(f"Project database modified: {datetime.fromtimestamp(stat.st_mtime)}")

        # Determine which database should be active
        active_db_path = chunkhound_db_path or str(default_cli_path)
        log_with_timestamp(f"Active database path: {active_db_path}")

        return True

    except Exception as e:
        log_with_timestamp(f"❌ Database path check failed: {e}", "ERROR")
        return False

def test_file_watcher_initialization():
    """Test 3: Check if file watcher is properly initialized."""
    log_with_timestamp("=== TEST 3: File Watcher Initialization Status ===")

    try:
        # Try to import and check file watcher components
        from chunkhound.file_watcher import FileWatcherManager, is_filesystem_watching_enabled
        from chunkhound.file_watcher import get_watch_paths_from_env

        log_with_timestamp("✅ File watcher imports successful")

        # Check if filesystem watching is enabled
        fs_enabled = is_filesystem_watching_enabled()
        log_with_timestamp(f"Filesystem watching enabled: {fs_enabled}")

        # Check watch paths configuration
        watch_paths = get_watch_paths_from_env()
        log_with_timestamp(f"Watch paths from env: {watch_paths}")

        # Check current working directory
        cwd = Path.cwd()
        log_with_timestamp(f"Current working directory: {cwd}")

        # Check if watchdog is available
        try:
            import watchdog
            log_with_timestamp("✅ Watchdog library available")
        except ImportError:
            log_with_timestamp("❌ Watchdog library NOT available", "ERROR")
            return False

        return fs_enabled and watch_paths

    except Exception as e:
        log_with_timestamp(f"❌ File watcher check failed: {e}", "ERROR")
        return False

def test_mcp_server_debug_logs():
    """Test 4: Check MCP server debug output for file watcher status."""
    log_with_timestamp("=== TEST 4: MCP Server Debug Status ===")

    try:
        # Create a test script to check MCP server internals
        test_script = '''
import sys
sys.path.insert(0, ".")

# Try to access MCP server globals
try:
    from chunkhound import mcp_server
    print(f"MCP server module loaded: {hasattr(mcp_server, '_file_watcher')}")

    if hasattr(mcp_server, '_file_watcher'):
        file_watcher = getattr(mcp_server, '_file_watcher')
        print(f"File watcher exists: {file_watcher is not None}")
        if file_watcher:
            print(f"File watcher active: {getattr(file_watcher, 'is_active', lambda: 'unknown')()}")
    else:
        print("File watcher global variable not found")

except Exception as e:
    print(f"Error accessing MCP server internals: {e}")
'''

        result = subprocess.run([
            sys.executable, "-c", test_script
        ], capture_output=True, text=True, timeout=10, cwd=Path.cwd())

        if result.returncode == 0:
            log_with_timestamp("MCP server debug output:", "SUCCESS")
            for line in result.stdout.strip().split('\n'):
                log_with_timestamp(f"  {line}")
            return True
        else:
            log_with_timestamp("❌ MCP server debug failed", "ERROR")
            log_with_timestamp(f"  Error: {result.stderr.strip()}")
            return False

    except Exception as e:
        log_with_timestamp(f"❌ MCP debug test failed: {e}", "ERROR")
        return False

def test_realtime_functionality():
    """Test 5: End-to-end realtime indexing test."""
    log_with_timestamp("=== TEST 5: Real-time Indexing End-to-End Test ===")

    try:
        # Create a unique test file
        unique_id = f"realtime_diagnostic_v2_{int(time.time())}"
        test_file = Path.cwd() / f"{unique_id}.py"
        unique_content = f'''# Real-time indexing test file
# Created at: {datetime.now()}
# Unique identifier: {unique_id}

def {unique_id}_function():
    """Test function for real-time indexing validation."""
    return "{unique_id}"

# Unique markers for search validation
UNIQUE_MARKER_{unique_id.upper()} = "test_marker_value"
'''

        log_with_timestamp(f"Creating test file: {test_file}")
        test_file.write_text(unique_content)

        # Wait for indexing
        log_with_timestamp("Waiting 15 seconds for real-time indexing...")
        time.sleep(15)

        # Test search functionality
        search_terms = [
            unique_id,
            f"{unique_id}_function",
            f"UNIQUE_MARKER_{unique_id.upper()}"
        ]

        search_results = {}
        for term in search_terms:
            try:
                # Test with chunkhound search
                result = subprocess.run([
                    sys.executable, "-m", "chunkhound.api.cli.main",
                    "search", "--regex", term
                ], capture_output=True, text=True, timeout=10, cwd=Path.cwd())

                search_results[term] = {
                    'found': term in result.stdout if result.returncode == 0 else False,
                    'output': result.stdout[:200] if result.returncode == 0 else result.stderr[:200]
                }

            except Exception as e:
                search_results[term] = {'found': False, 'error': str(e)}

        # Report results
        found_any = any(r.get('found', False) for r in search_results.values())

        if found_any:
            log_with_timestamp("✅ Real-time indexing IS WORKING", "SUCCESS")
            for term, result in search_results.items():
                if result.get('found'):
                    log_with_timestamp(f"  ✅ Found: {term}")
        else:
            log_with_timestamp("❌ Real-time indexing NOT WORKING", "ERROR")
            for term, result in search_results.items():
                log_with_timestamp(f"  ❌ Not found: {term}")
                if 'error' in result:
                    log_with_timestamp(f"    Error: {result['error']}")

        # Cleanup
        try:
            test_file.unlink()
            log_with_timestamp(f"Cleaned up test file: {test_file}")
        except:
            pass

        return found_any

    except Exception as e:
        log_with_timestamp(f"❌ Real-time test failed: {e}", "ERROR")
        return False

def main():
    """Run all diagnostic tests."""
    log_with_timestamp("Starting Real-time Indexing Diagnostic v2")
    log_with_timestamp("=" * 60)

    # Run all tests
    tests = [
        ("MCP Process Status", test_mcp_process_status),
        ("Database Path Configuration", test_database_paths),
        ("File Watcher Initialization", test_file_watcher_initialization),
        ("MCP Server Debug Status", test_mcp_server_debug_logs),
        ("Real-time Functionality", test_realtime_functionality)
    ]

    results = {}
    for test_name, test_func in tests:
        log_with_timestamp(f"Running {test_name}...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            log_with_timestamp(f"❌ {test_name} crashed: {e}", "ERROR")
            results[test_name] = False

        log_with_timestamp("")  # Empty line for readability

    # Summary
    log_with_timestamp("=" * 60)
    log_with_timestamp("DIAGNOSTIC SUMMARY")
    log_with_timestamp("=" * 60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log_with_timestamp(f"{status}: {test_name}")

    log_with_timestamp("")
    log_with_timestamp(f"Overall: {passed}/{total} tests passed")

    # Hypothesis evaluation
    if not results.get("File Watcher Initialization", False):
        log_with_timestamp("🎯 HYPOTHESIS CONFIRMED: File watcher not properly initialized", "CRITICAL")
    elif not results.get("Real-time Functionality", False):
        log_with_timestamp("🎯 HYPOTHESIS PARTIALLY CONFIRMED: File watcher initialized but not working", "CRITICAL")
    else:
        log_with_timestamp("🎯 HYPOTHESIS DISPROVEN: Real-time indexing appears to be working", "SUCCESS")

    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log_with_timestamp("Diagnostic interrupted by user", "WARNING")
        sys.exit(130)
    except Exception as e:
        log_with_timestamp(f"Diagnostic crashed: {e}", "ERROR")
        sys.exit(1)
