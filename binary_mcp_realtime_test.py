#!/usr/bin/env python3
"""
Binary MCP Real-time Indexing Test

Based on investigation findings:
- MCP server binary is running: chunkhound-macos-universal with --watch flag
- Python module inspection shows uninitialized state (not relevant to binary)
- Need to test actual real-time functionality with the running binary

This test creates files and verifies they are indexed by the running MCP server.
"""

import os
import sys
import time
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime

def log_with_timestamp(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {level}: {message}")

def create_test_file(content, filename=None):
    """Create a test file with unique content"""
    if filename is None:
        unique_id = str(uuid.uuid4())[:8]
        filename = f"realtime_test_{unique_id}_{int(time.time())}.py"

    test_file = Path(filename)
    test_file.write_text(content)
    log_with_timestamp(f"Created test file: {test_file}")
    return test_file

def search_via_mcp(query, timeout=30):
    """Search using Python CLI"""
    try:
        # Use Python CLI to search
        cmd = [sys.executable, "-m", "chunkhound.cli", "search", query]
        log_with_timestamp(f"Running search command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            return result.stdout
        else:
            log_with_timestamp(f"Search failed: {result.stderr}", "ERROR")
            return None

    except subprocess.TimeoutExpired:
        log_with_timestamp(f"Search timed out after {timeout}s", "ERROR")
        return None
    except Exception as e:
        log_with_timestamp(f"Search error: {e}", "ERROR")
        return None

def test_realtime_indexing():
    """Test real-time indexing functionality"""

    log_with_timestamp("=== Binary MCP Real-time Indexing Test ===")

    # Check if binary exists
    binary_path = Path("./dist/chunkhound-macos-universal/chunkhound-optimized")
    if not binary_path.exists():
        log_with_timestamp(f"❌ Binary not found at {binary_path}", "ERROR")
        return False

    # Check if MCP server is running
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )

        if "chunkhound-macos-universal" in result.stdout:
            log_with_timestamp("✅ MCP server binary is running", "SUCCESS")
        else:
            log_with_timestamp("❌ MCP server binary not found in processes", "ERROR")
            return False

    except Exception as e:
        log_with_timestamp(f"Process check failed: {e}", "ERROR")
        return False

    # Create unique test markers
    test_marker_1 = f"REALTIME_TEST_MARKER_{uuid.uuid4().hex[:16]}"
    test_marker_2 = f"REALTIME_TEST_FUNCTION_{uuid.uuid4().hex[:16]}"
    test_marker_3 = f"REALTIME_TEST_CLASS_{uuid.uuid4().hex[:16]}"

    log_with_timestamp(f"Test markers: {test_marker_1}, {test_marker_2}, {test_marker_3}")

    # Test file content
    test_content = f'''
"""Test file for real-time indexing verification"""

def {test_marker_2}():
    """Test function with unique marker"""
    marker_value = "{test_marker_1}"
    return marker_value

class {test_marker_3}:
    """Test class with unique marker"""

    def __init__(self):
        self.marker = "{test_marker_1}"

    def get_marker(self):
        return self.marker

# Comment with marker: {test_marker_1}
'''

    # Create test file
    test_file = create_test_file(test_content)

    try:
        # Wait for potential indexing
        log_with_timestamp("Waiting 10 seconds for indexing...")
        time.sleep(10)

        # Test searches
        results = {}

        # Search for each marker
        for i, marker in enumerate([test_marker_1, test_marker_2, test_marker_3], 1):
            log_with_timestamp(f"Searching for marker {i}: {marker}")
            search_result = search_via_mcp(marker)

            if search_result:
                # Check if marker appears in results
                found = marker in search_result
                results[marker] = found
                log_with_timestamp(f"Marker {i} found: {found}")
                if found:
                    # Count occurrences
                    occurrences = search_result.count(marker)
                    log_with_timestamp(f"Marker {i} occurrences: {occurrences}")
            else:
                results[marker] = False
                log_with_timestamp(f"Marker {i} search failed")

        # Evaluate results
        found_count = sum(results.values())
        total_count = len(results)

        log_with_timestamp(f"=== RESULTS ===")
        log_with_timestamp(f"Found {found_count}/{total_count} markers")

        if found_count == total_count:
            log_with_timestamp("✅ HYPOTHESIS DISPROVEN: Real-time indexing is working", "SUCCESS")
            log_with_timestamp("   → All test markers found in search results", "SUCCESS")
            return True
        elif found_count == 0:
            log_with_timestamp("🎯 HYPOTHESIS CONFIRMED: Real-time indexing is broken", "CRITICAL")
            log_with_timestamp("   → No test markers found in search results", "CRITICAL")
            return False
        else:
            log_with_timestamp("⚠️  PARTIAL RESULTS: Real-time indexing partially working", "WARNING")
            log_with_timestamp(f"   → Only {found_count}/{total_count} markers found", "WARNING")
            return False

    finally:
        # Cleanup
        try:
            if test_file.exists():
                test_file.unlink()
                log_with_timestamp(f"Cleaned up test file: {test_file}")
        except Exception as e:
            log_with_timestamp(f"Cleanup failed: {e}", "ERROR")

def main():
    """Run the real-time indexing test"""

    try:
        # Change to chunkhound directory
        os.chdir(Path(__file__).parent)

        success = test_realtime_indexing()

        if success:
            log_with_timestamp("🎉 TEST PASSED: Real-time indexing is working")
        else:
            log_with_timestamp("💥 TEST FAILED: Real-time indexing is not working")

        return success

    except KeyboardInterrupt:
        log_with_timestamp("⚠️  Test interrupted by user", "WARNING")
        return False
    except Exception as e:
        log_with_timestamp(f"💥 Test crashed: {e}", "ERROR")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
