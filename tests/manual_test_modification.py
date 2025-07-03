#!/usr/bin/env python3
"""
Manual test script for debugging file modification detection in ChunkHound.

This script provides a simple interactive way to test:
1. Creating a test file
2. Indexing it
3. Searching for its content
4. Modifying the file
5. Searching again to see if modifications were detected

Usage:
    python manual_test_modification.py

This script is meant to be run interactively to debug file modification detection
issues in ChunkHound's realtime watching system.
"""

import os
import subprocess
import time
import uuid
from pathlib import Path

# Test configuration
TEST_DIR = Path("/tmp/chunkhound_manual_test")
TEST_FILE = TEST_DIR / "test_file.py"
CHUNKHOUND_CMD = "uv run chunkhound"
UNIQUE_ID = str(uuid.uuid4())[:8]  # Use a unique ID for this test run


# REALTIME_TEST_MARKER: Added to test real-time indexing
def realtime_test_function():
    """Test function for real-time indexing verification."""
    return "realtime_test_marker_12345"


# POST_FIX_MODIFICATION_MARKER: Added after import fixes
def post_fix_modification_test():
    """Function added after import path fixes."""
    return "post_fix_modification_success"


def run_command(cmd):
    """Run a command and print its output."""
    print(f"\n> {cmd}")
    result = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.stdout:
        print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")

    return result.returncode == 0


def setup():
    """Set up test environment."""
    print("\n=== Setting up test environment ===")

    # Create test directory
    TEST_DIR.mkdir(exist_ok=True, parents=True)
    print(f"Created test directory: {TEST_DIR}")

    # Create initial test file
    initial_content = f"""# Test file for ChunkHound file modification detection
# MARKER: {UNIQUE_ID}_INITIAL

def initial_function():
    \"\"\"This function should be detected in the initial indexing.\"\"\"
    return "{UNIQUE_ID}_INITIAL"

class InitialClass:
    \"\"\"This class should be detected in the initial indexing.\"\"\"

    def method1(self):
        return "{UNIQUE_ID}_INITIAL_METHOD1"
"""
    TEST_FILE.write_text(initial_content)
    print(f"Created test file with unique ID: {UNIQUE_ID}")
    print(f"File path: {TEST_FILE}")


def index_directory():
    """Index the test directory."""
    print("\n=== Indexing test directory ===")
    cmd = f"{CHUNKHOUND_CMD} run {TEST_DIR} --include='*.py'"
    success = run_command(cmd)
    if success:
        print("Indexing command executed successfully")
    else:
        print("Indexing command failed")


def search_content(marker, wait_time=0):
    """Search for content with the specified marker."""
    if wait_time > 0:
        print(f"Waiting {wait_time} seconds before searching...")
        time.sleep(wait_time)

    print(f"\n=== Searching for marker: {marker} ===")
    cmd = f'{CHUNKHOUND_CMD} search-regex "{marker}"'
    success = run_command(cmd)
    return success


def modify_file():
    """Modify the test file with new content."""
    print("\n=== Modifying test file ===")

    # Read current content to preserve it
    current_content = TEST_FILE.read_text() if TEST_FILE.exists() else ""

    # Append new content
    modified_content = (
        current_content
        + f"""
# MARKER: {UNIQUE_ID}_MODIFIED
# Added at: {time.strftime("%Y-%m-%d %H:%M:%S")}

def modified_function():
    \"\"\"This function should be detected after file modification.\"\"\"
    return "{UNIQUE_ID}_MODIFIED"

class ModifiedClass:
    \"\"\"This class should be detected after file modification.\"\"\"

    def new_method(self):
        return "{UNIQUE_ID}_MODIFIED_METHOD"
"""
    )

    # Write modified content
    TEST_FILE.write_text(modified_content)
    print(f"Modified test file: {TEST_FILE}")
    print(f"Added marker: {UNIQUE_ID}_MODIFIED")

    # Touch the file to ensure mtime changes
    os.utime(TEST_FILE, None)
    print(f"Updated file modification time: {TEST_FILE.stat().st_mtime}")


def replace_file():
    """Replace the test file with completely new content."""
    print("\n=== Replacing test file content ===")

    # Create completely new content
    new_content = f"""# Test file for ChunkHound file modification detection
# MARKER: {UNIQUE_ID}_REPLACED
# Created at: {time.strftime("%Y-%m-%d %H:%M:%S")}

def replaced_function():
    \"\"\"This function should be detected after file replacement.\"\"\"
    return "{UNIQUE_ID}_REPLACED"

class ReplacedClass:
    \"\"\"This class should be detected after file replacement.\"\"\"

    def replaced_method(self):
        return "{UNIQUE_ID}_REPLACED_METHOD"
"""

    # Write new content
    TEST_FILE.write_text(new_content)
    print(f"Replaced test file content: {TEST_FILE}")
    print(f"New marker: {UNIQUE_ID}_REPLACED")

    # Touch the file to ensure mtime changes
    os.utime(TEST_FILE, None)
    print(f"Updated file modification time: {TEST_FILE.stat().st_mtime}")


def get_stats():
    """Get ChunkHound database statistics."""
    print("\n=== Getting ChunkHound stats ===")
    cmd = f"{CHUNKHOUND_CMD} stats"
    run_command(cmd)


def check_modified_time():
    """Check the file's modified time and print details."""
    if not TEST_FILE.exists():
        print(f"Test file does not exist: {TEST_FILE}")
        return

    stats = TEST_FILE.stat()
    print(f"\nFile: {TEST_FILE}")
    print(f"Size: {stats.st_size} bytes")
    print(f"Modified time (epoch): {stats.st_mtime}")
    print(f"Modified time (formatted): {time.ctime(stats.st_mtime)}")


def get_mcp_status():
    """Check if the MCP server is running."""
    print("\n=== Checking MCP server status ===")
    cmd = "ps aux | grep '[c]hunkhound mcp' || echo 'MCP server not running'"
    run_command(cmd)


def debug_file():
    """Print the current content of the test file."""
    print("\n=== Current test file content ===")
    if TEST_FILE.exists():
        print(f"Content of {TEST_FILE}:")
        print("---")
        print(TEST_FILE.read_text())
        print("---")
    else:
        print(f"Test file does not exist: {TEST_FILE}")


def interactive_menu():
    """Show an interactive menu for debugging."""
    while True:
        print("\n=== ChunkHound File Modification Debug Menu ===")
        print(f"Test directory: {TEST_DIR}")
        print(f"Test file: {TEST_FILE}")
        print(f"Unique ID: {UNIQUE_ID}")
        print("\nOptions:")
        print("1. Setup test environment")
        print("2. Index test directory")
        print("3. Search for initial marker")
        print("4. Modify test file (append)")
        print("5. Replace test file (complete)")
        print("6. Search for modified marker")
        print("7. Search for replaced marker")
        print("8. Get ChunkHound stats")
        print("9. Check file modified time")
        print("10. Check MCP server status")
        print("11. View test file content")
        print("12. Exit")

        choice = input("\nEnter your choice (1-12): ")

        if choice == "1":
            setup()
        elif choice == "2":
            index_directory()
        elif choice == "3":
            search_content(f"{UNIQUE_ID}_INITIAL", wait_time=1)
        elif choice == "4":
            modify_file()
        elif choice == "5":
            replace_file()
        elif choice == "6":
            search_content(f"{UNIQUE_ID}_MODIFIED", wait_time=5)
        elif choice == "7":
            search_content(f"{UNIQUE_ID}_REPLACED", wait_time=5)
        elif choice == "8":
            get_stats()
        elif choice == "9":
            check_modified_time()
        elif choice == "10":
            get_mcp_status()
        elif choice == "11":
            debug_file()
        elif choice == "12":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")


def cleanup():
    """Clean up test files."""
    try:
        if TEST_FILE.exists():
            TEST_FILE.unlink()
            print(f"Removed test file: {TEST_FILE}")

        if TEST_DIR.exists():
            TEST_DIR.rmdir()
            print(f"Removed test directory: {TEST_DIR}")
    except Exception as e:
        print(f"Error during cleanup: {e}")


def main():
    """Main function."""
    try:
        print("ChunkHound File Modification Detection Debug Tool")
        print("================================================")
        print(f"Unique test ID: {UNIQUE_ID}")

        interactive_menu()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        choice = input("\nClean up test files? (y/n): ")
        if choice.lower() == "y":
            cleanup()
        else:
            print(f"Test files remain at: {TEST_DIR}")


if __name__ == "__main__":
    main()
