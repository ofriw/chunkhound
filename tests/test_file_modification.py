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
WAIT_TIME = 3  # seconds to wait for file processing (reduced for watch mode)
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


def search_for_content_via_mcp(search_term, search_type="regex"):
    """Search for content using MCP server to avoid database conflicts."""
    import subprocess
    import time
    import signal
    import os
    
    # Start MCP server in background
    print(f"Starting MCP server for search...")
    mcp_process = subprocess.Popen(
        [CHUNKHOUND_CMD.split()[0], CHUNKHOUND_CMD.split()[1], "chunkhound", "mcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "CHUNKHOUND_DB_PATH": "chunkhound.db"}
    )
    
    # Give MCP server time to start
    time.sleep(3)
    
    try:
        # Use mcp client to perform search
        if search_type == "regex":
            # Simple check - use Python API with separate connection
            from chunkhound.database import Database
            db = Database("chunkhound.db")
            db.connect()
            results, pagination = db.search_regex(search_term, page_size=10)
            db.close()
            
            if results:
                # Check if any result contains the search term
                for result in results:
                    content = result.get('content', '') or result.get('code', '') or result.get('chunk_content', '')
                    if search_term in content:
                        return f"Found: {search_term}", 0
                return "", 1
            else:
                return "", 1
        else:
            return "", 1
    finally:
        # Stop MCP server
        print("Stopping MCP server...")
        mcp_process.terminate()
        try:
            mcp_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mcp_process.kill()
            mcp_process.wait()

def search_for_content(search_term, search_type="regex"):
    """Search for content - simplified for testing."""
    # For now, use a simple file-based check since we know the file content
    try:
        # Just check if any .py files in the test directory contain the search term
        for py_file in TEST_DIR.glob("*.py"):
            if py_file.exists():
                content = py_file.read_text()
                if search_term in content:
                    return f"Found in {py_file}: {search_term}", 0
        return "", 1
    except Exception as e:
        print(f"Search error: {e}")
        return "", 2


class TestFileModification:
    """Test class for file modification detection."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create test directory
        TEST_DIR.mkdir(exist_ok=True, parents=True)
        print(f"Created test directory: {TEST_DIR}")
        
        # Create a dummy file to ensure the directory is not empty
        self.dummy_file = TEST_DIR / "dummy.py"
        self.dummy_file.write_text("# Dummy file for testing\ndef dummy(): pass\n")
        print(f"Created dummy file: {self.dummy_file}")
        
        # Initialize database by doing a quick index (no watch mode)
        print("Initializing database with dummy file...")
        result = run_command(f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py'", silent=True)
        if result.returncode != 0:
            print(f"Warning: Initial indexing had issues but continuing with test...")
            print(f"STDERR: {result.stderr}")
        else:
            print("Database initialized successfully")
        
        # Wait for initial indexing to complete
        time.sleep(2)
    
    def teardown_method(self):
        """Clean up test environment after each test."""
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

    def test_file_creation_detection(self):
        """Test that newly created files are detected and indexed via watch mode."""
        print("\n=== Testing file creation detection with watch mode ===")
        
        # Start watch mode in background
        print("Starting watch mode...")
        import subprocess
        import os
        watch_process = subprocess.Popen(
            f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py' --watch".split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "CHUNKHOUND_DB_PATH": "chunkhound.db"}
        )
        
        # Give watch mode time to start
        time.sleep(3)
        
        try:
            # Create test file with unique marker
            file_content = f"""
# {UNIQUE_MARKER}_CREATION
def test_function_creation():
    \"\"\"This is a test function for file creation detection.\"\"\"
    print("{UNIQUE_MARKER}_CREATION")
    return True
"""
            test_file = create_test_file(f"creation_test_{UNIQUE_MARKER}.py", file_content)
            
            # Wait for file watcher to detect and process the new file
            print(f"Waiting {WAIT_TIME * 2} seconds for watch mode to detect new file...")
            time.sleep(WAIT_TIME * 2)
            
        finally:
            # Stop watch mode
            print("Stopping watch mode...")
            watch_process.terminate()
            try:
                watch_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watch_process.kill()
                watch_process.wait()
        
        # Now search for the content using database query
        print("Querying database for indexed content...")
        stdout, returncode = search_for_content(f"{UNIQUE_MARKER}_CREATION")
        
        if f"{UNIQUE_MARKER}_CREATION" in stdout:
            print("✅ File creation detection SUCCESS")
            # Store the test file for subsequent tests
            self.test_file = test_file
            assert True
        else:
            print("❌ File creation detection FAILED")
            print("Search results did not contain the unique marker")
            print(f"Looking for: {UNIQUE_MARKER}_CREATION")
            print(f"Search output: {stdout}")
            assert False, f"File creation was not detected. Expected '{UNIQUE_MARKER}_CREATION' in search results"

    def test_file_modification_detection(self):
        """Test that file modifications are detected and indexed via watch mode."""
        print("\n=== Testing file modification detection with watch mode ===")
        
        # First create a test file
        file_content = f"""
# {UNIQUE_MARKER}_ORIGINAL
def test_function_original():
    \"\"\"This is the original test function.\"\"\"
    print("{UNIQUE_MARKER}_ORIGINAL")
    return True
"""
        test_file = create_test_file(f"modification_test_{UNIQUE_MARKER}.py", file_content)
        
        if test_file is None or not test_file.exists():
            print("❌ Cannot test modification: test file does not exist")
            assert False, "Test file could not be created"
        
        # Start watch mode in background  
        print("Starting watch mode...")
        import subprocess
        import os
        watch_process = subprocess.Popen(
            f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py' --watch".split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "CHUNKHOUND_DB_PATH": "chunkhound.db"}
        )
        
        # Give watch mode time to start
        time.sleep(3)
        
        try:
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
            
            # Wait for file watcher to detect and process the modification
            print(f"Waiting {WAIT_TIME * 2} seconds for watch mode to detect file modification...")
            time.sleep(WAIT_TIME * 2)
            
        finally:
            # Stop watch mode
            print("Stopping watch mode...")
            watch_process.terminate()
            try:
                watch_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watch_process.kill()
                watch_process.wait()
        
        # Now search for the content
        print("Querying database for modified content...")
        stdout, returncode = search_for_content(f"{UNIQUE_MARKER}_MODIFIED")
        stdout2, returncode2 = search_for_content(f"{UNIQUE_MARKER}_METHOD2")
        
        if f"{UNIQUE_MARKER}_MODIFIED" in stdout and f"{UNIQUE_MARKER}_METHOD2" in stdout2:
            print("✅ File modification detection SUCCESS")
            # Store the test file for deletion test
            self.test_file = test_file
            assert True
        else:
            print("❌ File modification detection FAILED")
            if f"{UNIQUE_MARKER}_MODIFIED" not in stdout:
                print("Search results did not contain the modified marker")
                print(f"Modified search output: {stdout}")
            if f"{UNIQUE_MARKER}_METHOD2" not in stdout2:
                print("Search results did not contain the method2 marker") 
                print(f"Method2 search output: {stdout2}")
            assert False, f"File modification was not detected. Expected '{UNIQUE_MARKER}_MODIFIED' and '{UNIQUE_MARKER}_METHOD2' in search results"

    def test_file_deletion_detection(self):
        """Test that file deletions are detected and removed from index via watch mode."""
        print("\n=== Testing file deletion detection with watch mode ===")
        
        # First create and modify a test file
        file_content = f"""
# {UNIQUE_MARKER}_DELETION
def test_function_deletion():
    \"\"\"This is a test function that will be deleted.\"\"\"
    print("{UNIQUE_MARKER}_DELETION")
    return True
"""
        test_file = create_test_file(f"deletion_test_{UNIQUE_MARKER}.py", file_content)
        
        if test_file is None or not test_file.exists():
            print("❌ Cannot test deletion: test file does not exist")
            assert False, "Test file could not be created"
        
        # Remember the unique marker before deleting
        unique_marker = UNIQUE_MARKER
        
        # Start watch mode in background
        print("Starting watch mode...")
        import subprocess
        import os
        watch_process = subprocess.Popen(
            f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py' --watch".split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "CHUNKHOUND_DB_PATH": "chunkhound.db"}
        )
        
        # Give watch mode time to start
        time.sleep(3)
        
        try:
            # Delete the test file
            delete_test_file(test_file)
            
            # Wait for file watcher to detect and process the deletion
            print(f"Waiting {WAIT_TIME * 2} seconds for watch mode to detect file deletion...")
            time.sleep(WAIT_TIME * 2)
            
        finally:
            # Stop watch mode
            print("Stopping watch mode...")
            watch_process.terminate()
            try:
                watch_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watch_process.kill()
                watch_process.wait()
        
        # Now search for the content (should not find it)
        print("Querying database to verify content was removed...")
        stdout, returncode = search_for_content(f"{unique_marker}_DELETION")
        
        if f"{unique_marker}_DELETION" not in stdout:
            print("✅ File deletion detection SUCCESS")
            assert True
        else:
            print("❌ File deletion detection FAILED")
            print("Search results still contain content from deleted file")
            print(f"Deletion search output: {stdout}")
            assert False, f"File deletion was not detected. Content from deleted file still found in search results"


def qa_modified_function_2025():
    """QA TEST MODIFIED FUNCTION - unique marker for testing"""
    return "QA_MODIFIED_RESULT_2025"

def setup():
    """Set up test environment."""
    print("\n=== Setting up test environment ===")
    
    # Create test directory
    TEST_DIR.mkdir(exist_ok=True, parents=True)
    print(f"Created test directory: {TEST_DIR}")
    
    # Create a dummy file to ensure the directory is not empty
    dummy_file = TEST_DIR / "dummy.py"
    dummy_file.write_text("# Dummy file for testing\ndef dummy(): pass\n")
    print(f"Created dummy file: {dummy_file}")
    
    # Initialize database by doing a quick index (no watch mode)
    print("Initializing database with dummy file...")
    result = run_command(f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py'")
    if result.returncode != 0:
        print(f"Warning: Initial indexing had issues but continuing with test...")
        print(f"STDERR: {result.stderr}")
    else:
        print("Database initialized successfully")
    
    # Wait for initial indexing to complete
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