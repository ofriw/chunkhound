#!/usr/bin/env python3
"""Test script for file modification detection in ChunkHound.

This script tests the realtime file watching and modification detection by:
1. Creating test files with specific content
2. Verifying they appear in search results
3. Modifying the files with new content
4. Verifying the new content appears in search results
5. Deleting the files
6. Verifying they no longer appear in search results
"""

import os
import sys
import time
import random
import string
import argparse
import subprocess
from pathlib import Path


# Test configuration
TEST_DIR = Path("/tmp/chunkhound_modification_test")
WAIT_TIME = 5  # seconds to wait for file processing
UNIQUE_MARKER = f"CHUNKHOUND_TEST_{random.randint(10000, 99999)}"
CHUNKHOUND_CMD = "uv run chunkhound"  # use 'python -m chunkhound' when installed as a module


def run_command(cmd, silent=False):
    """Run a command and return its output."""
    if not silent:
        print(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if not silent:
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
    return result


def create_test_file(name, content):
    """Create a test file with specified content."""
    file_path = TEST_DIR / name
    file_path.write_text(content)
    print(f"Created test file: {file_path}")
    return file_path


def modify_test_file(file_path, content):
    """Modify a test file with new content."""
    file_path.write_text(content)
    print(f"Modified test file: {file_path}")
    return file_path


def delete_test_file(file_path):
    """Delete a test file."""
    file_path.unlink()
    print(f"Deleted test file: {file_path}")


def search_for_content(search_term, search_type="regex"):
    """Search for content in indexed files."""
    if search_type == "regex":
        cmd = f"{CHUNKHOUND_CMD} search-regex \"{search_term}\""
    else:
        cmd = f"{CHUNKHOUND_CMD} search \"{search_term}\""
    
    result = run_command(cmd, silent=True)
    return result.stdout, result.returncode


def test_file_creation_detection():
    """Test that newly created files are detected and indexed."""
    print("\n=== Testing file creation detection ===")
    
    # Create test file with unique marker
    file_content = f"""
# {UNIQUE_MARKER}_CREATION
def test_function_creation():
    \"\"\"This is a test function for file creation detection.\"\"\"
    print("{UNIQUE_MARKER}_CREATION")
    return True
"""
    test_file = create_test_file(f"creation_test_{UNIQUE_MARKER}.py", file_content)
    
    # Wait for indexing
    print(f"Waiting {WAIT_TIME} seconds for indexing...")
    time.sleep(WAIT_TIME)
    
    # Search for unique marker
    stdout, returncode = search_for_content(f"{UNIQUE_MARKER}_CREATION")
    if f"{UNIQUE_MARKER}_CREATION" in stdout:
        print("✅ File creation detection SUCCESS")
        return test_file
    else:
        print("❌ File creation detection FAILED")
        print("Search results did not contain the unique marker")
        return None


def test_file_modification_detection(test_file):
    """Test that file modifications are detected and indexed."""
    print("\n=== Testing file modification detection ===")
    
    if test_file is None or not test_file.exists():
        print("❌ Cannot test modification: test file does not exist")
        return False
    
    # Modify test file with new unique marker
    modified_content = f"""
# {UNIQUE_MARKER}_MODIFIED
def test_function_modified():
    \"\"\"This is a modified test function for file modification detection.\"\"\"
    print("{UNIQUE_MARKER}_MODIFIED")
    return True

# Additional content to ensure significant change
class TestClass_{UNIQUE_MARKER}:
    def method1(self):
        \"\"\"First test method\"\"\"
        return "{UNIQUE_MARKER}_MODIFIED"
        
    def method2(self):
        \"\"\"Second test method\"\"\"
        return "{UNIQUE_MARKER}_METHOD2"
"""
    modify_test_file(test_file, modified_content)
    
    # Wait for indexing
    print(f"Waiting {WAIT_TIME} seconds for indexing...")
    time.sleep(WAIT_TIME)
    
    # Search for new unique marker
    stdout, returncode = search_for_content(f"{UNIQUE_MARKER}_MODIFIED")
    
    # Also search for method2 marker to verify complete content indexing
    stdout2, returncode2 = search_for_content(f"{UNIQUE_MARKER}_METHOD2")
    
    if f"{UNIQUE_MARKER}_MODIFIED" in stdout and f"{UNIQUE_MARKER}_METHOD2" in stdout2:
        print("✅ File modification detection SUCCESS")
        return True
    else:
        print("❌ File modification detection FAILED")
        if f"{UNIQUE_MARKER}_MODIFIED" not in stdout:
            print("Search results did not contain the modified marker")
        if f"{UNIQUE_MARKER}_METHOD2" not in stdout2:
            print("Search results did not contain the method2 marker")
        return False


def test_file_deletion_detection(test_file):
    """Test that file deletions are detected and removed from index."""
    print("\n=== Testing file deletion detection ===")
    
    if test_file is None or not test_file.exists():
        print("❌ Cannot test deletion: test file does not exist")
        return False
    
    # Remember the unique marker before deleting
    unique_marker = UNIQUE_MARKER
    
    # Delete the test file
    delete_test_file(test_file)
    
    # Wait for processing
    print(f"Waiting {WAIT_TIME} seconds for processing...")
    time.sleep(WAIT_TIME)
    
    # Search for unique marker (should not find it)
    stdout, returncode = search_for_content(f"{unique_marker}_MODIFIED")
    
    if f"{unique_marker}_MODIFIED" not in stdout:
        print("✅ File deletion detection SUCCESS")
        return True
    else:
        print("❌ File deletion detection FAILED")
        print("Search results still contain content from deleted file")
        return False


def setup():
    """Set up test environment."""
    print("\n=== Setting up test environment ===")
    
    # Create test directory
    TEST_DIR.mkdir(exist_ok=True, parents=True)
    print(f"Created test directory: {TEST_DIR}")
    
    # Index the empty directory first to ensure MCP server is running
    run_command(f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py'")
    
    # Wait for initial indexing
    time.sleep(2)


def cleanup():
    """Clean up test environment."""
    print("\n=== Cleaning up test environment ===")
    
    try:
        # Remove test directory
        if TEST_DIR.exists():
            for file in TEST_DIR.glob("*"):
                if file.is_file():
                    file.unlink()
            TEST_DIR.rmdir()
            print(f"Removed test directory: {TEST_DIR}")
    except Exception as e:
        print(f"Error during cleanup: {e}")


def main():
    """Run the file modification detection tests."""
    global WAIT_TIME
    
    parser = argparse.ArgumentParser(description="Test file modification detection in ChunkHound")
    parser.add_argument("--wait", type=int, default=WAIT_TIME, help="Seconds to wait for file processing")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup after tests")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()
    
    WAIT_TIME = args.wait
    
    try:
        setup()
        
        # Run tests
        test_file = test_file_creation_detection()
        modification_success = test_file_modification_detection(test_file)
        deletion_success = test_file_deletion_detection(test_file)
        
        # Report results
        print("\n=== Test Results ===")
        print(f"File Creation Detection: {'✅ SUCCESS' if test_file else '❌ FAILED'}")
        print(f"File Modification Detection: {'✅ SUCCESS' if modification_success else '❌ FAILED'}")
        print(f"File Deletion Detection: {'✅ SUCCESS' if deletion_success else '❌ FAILED'}")
        
        # Overall success
        if test_file and modification_success and deletion_success:
            print("\n✅ All tests PASSED")
            return 0
        else:
            print("\n❌ Some tests FAILED")
            return 1
        
    except Exception as e:
        print(f"Error during testing: {e}")
        return 1
    finally:
        if not args.skip_cleanup:
            cleanup()


if __name__ == "__main__":
    sys.exit(main())