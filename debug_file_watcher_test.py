#!/usr/bin/env python3
"""
Standalone test to validate file watcher callback chain hypothesis.
This test isolates the file watcher components to determine if the callback
chain is broken in the MCP server integration.
"""

import os
import sys
import time
import asyncio
import tempfile
from pathlib import Path
from typing import List

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from chunkhound.file_watcher import FileWatcherManager, get_watch_paths_from_env
    from chunkhound.database import Database
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the chunkhound directory")
    sys.exit(1)

# Global variables to track callback invocations
callback_invocations = []
test_results = {}

async def test_callback(file_path: Path, event_type: str):
    """Test callback function that logs invocations."""
    timestamp = time.time()
    invocation = {
        'timestamp': timestamp,
        'file_path': str(file_path),
        'event_type': event_type
    }
    callback_invocations.append(invocation)
    print(f"TEST_CALLBACK: {timestamp:.6f} - {event_type} - {file_path}")

async def test_file_watcher_callback_chain():
    """Test the file watcher callback chain in isolation."""
    print("=== FILE WATCHER CALLBACK CHAIN TEST ===")
    print(f"Test started at: {time.time():.6f}")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Using temp directory: {temp_path}")

        # Initialize file watcher manager
        watcher_manager = FileWatcherManager()

        try:
            # Test 1: Initialize file watcher
            print("\n1. Testing FileWatcherManager initialization...")
            success = await watcher_manager.initialize(
                process_callback=test_callback,
                watch_paths=[temp_path]
            )
            test_results['initialization'] = success
            print(f"   Initialization result: {success}")

            if success:
                print(f"   Watcher active: {watcher_manager.is_active()}")
                print(f"   Watch paths: {watcher_manager.watch_paths}")

                # Test 2: File creation
                print("\n2. Testing file creation detection...")
                test_file = temp_path / "test_creation.py"
                callback_count_before = len(callback_invocations)

                # Create test file
                test_file.write_text("""
# Test file for file watcher validation
CREATION_TEST_MARKER = "test_file_created"
""")
                print(f"   Created test file: {test_file}")
                print(f"   Callbacks before: {callback_count_before}")

                # Wait for file watcher to detect change
                await asyncio.sleep(3.0)

                callback_count_after = len(callback_invocations)
                print(f"   Callbacks after: {callback_count_after}")
                print(f"   New callbacks: {callback_count_after - callback_count_before}")
                test_results['file_creation'] = callback_count_after > callback_count_before

                # Test 3: File modification
                print("\n3. Testing file modification detection...")
                callback_count_before = len(callback_invocations)

                # Modify test file
                test_file.write_text("""
# Test file for file watcher validation
CREATION_TEST_MARKER = "test_file_created"
MODIFICATION_TEST_MARKER = "test_file_modified"
""")
                print(f"   Modified test file: {test_file}")
                print(f"   Callbacks before: {callback_count_before}")

                # Wait for file watcher to detect change
                await asyncio.sleep(3.0)

                callback_count_after = len(callback_invocations)
                print(f"   Callbacks after: {callback_count_after}")
                print(f"   New callbacks: {callback_count_after - callback_count_before}")
                test_results['file_modification'] = callback_count_after > callback_count_before

                # Test 4: File deletion
                print("\n4. Testing file deletion detection...")
                callback_count_before = len(callback_invocations)

                # Delete test file
                test_file.unlink()
                print(f"   Deleted test file: {test_file}")
                print(f"   Callbacks before: {callback_count_before}")

                # Wait for file watcher to detect change
                await asyncio.sleep(3.0)

                callback_count_after = len(callback_invocations)
                print(f"   Callbacks after: {callback_count_after}")
                print(f"   New callbacks: {callback_count_after - callback_count_before}")
                test_results['file_deletion'] = callback_count_after > callback_count_before

            else:
                print("   Skipping file tests due to initialization failure")
                test_results['file_creation'] = False
                test_results['file_modification'] = False
                test_results['file_deletion'] = False

        except Exception as e:
            print(f"   Test error: {e}")
            test_results['error'] = str(e)

        finally:
            # Cleanup
            print("\n5. Cleaning up...")
            await watcher_manager.cleanup()
            print("   Cleanup completed")

def test_mcp_server_database_connection():
    """Test database connection similar to MCP server setup."""
    print("\n=== DATABASE CONNECTION TEST ===")

    try:
        # Use same database path as MCP server
        db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
        if not db_path.exists():
            db_path = Path(".chunkhound.db")  # Fallback to local database

        print(f"Testing database at: {db_path}")
        print(f"Database exists: {db_path.exists()}")

        if db_path.exists():
            print(f"Database size: {db_path.stat().st_size} bytes")

        # Test database connection
        database = Database(db_path)
        database.connect()

        print("Database connection: SUCCESS")

        # Test database stats
        stats = database.get_stats()
        print(f"Database stats: {stats}")
        test_results['database_connection'] = True
        test_results['database_stats'] = stats

        database.close()

    except Exception as e:
        print(f"Database connection error: {e}")
        test_results['database_connection'] = False
        test_results['database_error'] = str(e)

async def main():
    """Main test function."""
    print("CHUNKHOUND FILE WATCHER DEBUG TEST")
    print("=" * 50)
    print(f"Started at: {time.time():.6f}")

    # Test database connection first
    test_mcp_server_database_connection()

    # Test file watcher callback chain
    await test_file_watcher_callback_chain()

    # Print summary
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)

    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:25} : {status}")

    print(f"\nTotal callback invocations: {len(callback_invocations)}")
    if callback_invocations:
        print("\nCallback details:")
        for i, callback in enumerate(callback_invocations, 1):
            print(f"  {i}. {callback['timestamp']:.6f} - {callback['event_type']} - {callback['file_path']}")

    # Analysis
    print("\n" + "=" * 50)
    print("HYPOTHESIS VALIDATION")
    print("=" * 50)

    if test_results.get('initialization'):
        if any(test_results.get(k, False) for k in ['file_creation', 'file_modification', 'file_deletion']):
            print("✅ HYPOTHESIS DISPROVEN: File watcher callback chain works correctly")
            print("   The issue is likely elsewhere in the MCP server integration")
        else:
            print("❌ HYPOTHESIS CONFIRMED: File watcher callback chain is broken")
            print("   File watcher initializes but callbacks are not invoked")
    else:
        print("❌ FILE WATCHER INITIALIZATION FAILED")
        print("   Cannot test callback chain due to initialization failure")

    if not test_results.get('database_connection'):
        print("⚠️  DATABASE CONNECTION ISSUE DETECTED")
        print("   This could prevent file indexing even if callbacks work")

    print(f"\nTest completed at: {time.time():.6f}")

if __name__ == "__main__":
    asyncio.run(main())
