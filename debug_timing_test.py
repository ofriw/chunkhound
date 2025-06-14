#!/usr/bin/env python3
"""
Debug script to test realtime file sync timing coordination.
Creates, modifies, and deletes test files to validate timing hypothesis.
"""

import os
import sys
import time
import tempfile
import asyncio
from pathlib import Path
from typing import List, Dict, Any

# Add the chunkhound module to the path
sys.path.insert(0, str(Path(__file__).parent))

from providers.database.duckdb_provider import DuckDBProvider
from chunkhound.file_watcher import FileWatcherManager
from chunkhound.mcp_server import process_file_change


class TimingDebugger:
    """Debug timing coordination between file events and database updates."""

    def __init__(self):
        self.test_dir = None
        self.database = None
        self.file_watcher = None
        self.events_log = []
        self.db_path = None

    async def setup(self):
        """Set up test environment."""
        print("Setting up timing debug environment...")

        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="chunkhound_timing_test_"))
        print(f"Test directory: {self.test_dir}")

        # Create temporary database
        self.db_path = self.test_dir / "test.duckdb"
        self.database = DuckDBProvider(str(self.db_path))
        print(f"Test database: {self.db_path}")

        # Create test files
        self.test_files = {
            "test_file.py": "# Test Python file\nprint('Hello World')\n",
            "test_file.md": "# Test Markdown\nThis is a test file.\n",
            "test_file.txt": "This is a plain text file.\n"
        }

        for filename, content in self.test_files.items():
            file_path = self.test_dir / filename
            file_path.write_text(content)
            print(f"Created test file: {file_path}")

        print("Setup complete.\n")

    def log_event(self, event_type: str, file_path: Path, details: Dict[str, Any] = None):
        """Log timing event with precise timestamp."""
        timestamp = time.time()
        event = {
            "timestamp": timestamp,
            "formatted_time": f"{timestamp:.6f}",
            "event_type": event_type,
            "file_path": str(file_path),
            "details": details or {}
        }
        self.events_log.append(event)
        print(f"[{event['formatted_time']}] {event_type}: {file_path} {details or ''}")

    async def test_file_modification_timing(self):
        """Test file modification timing coordination."""
        print("\n=== Testing File Modification Timing ===")

        test_file = self.test_dir / "test_file.py"
        original_content = test_file.read_text()

        # Get initial database state
        self.log_event("DB_QUERY_START", test_file)
        initial_file_record = self.database.get_file_by_path(str(test_file))
        self.log_event("DB_QUERY_END", test_file, {"exists": initial_file_record is not None})

        if initial_file_record:
            initial_mtime = initial_file_record.get('mtime', 0)
            print(f"Initial database mtime: {initial_mtime}")

        # Modify file
        self.log_event("FILE_MODIFY_START", test_file)
        modified_content = original_content + f"\n# Modified at {time.time():.6f}\n"
        test_file.write_text(modified_content)

        # Get file system mtime immediately after write
        file_stat = test_file.stat()
        fs_mtime = file_stat.st_mtime
        self.log_event("FILE_MODIFY_END", test_file, {"fs_mtime": f"{fs_mtime:.6f}"})

        # Simulate file watcher detection delay
        await asyncio.sleep(0.1)

        # Process file change (this simulates the MCP server processing)
        self.log_event("MCP_PROCESS_START", test_file)
        await process_file_change(test_file, "modified")
        self.log_event("MCP_PROCESS_END", test_file)

        # Check database state after processing
        self.log_event("DB_QUERY_POST_START", test_file)
        updated_file_record = self.database.get_file_by_path(str(test_file))
        self.log_event("DB_QUERY_POST_END", test_file)

        if updated_file_record:
            db_mtime_after = updated_file_record.get('mtime', 0)
            print(f"Database mtime after processing: {db_mtime_after}")

            # Calculate timing differences
            mtime_diff = abs(fs_mtime - db_mtime_after)
            print(f"Mtime difference (fs vs db): {mtime_diff:.6f}s")

            if mtime_diff > 1.0:
                print("⚠️  WARNING: Large mtime difference detected!")
                return False
            else:
                print("✅ Mtime synchronization looks good")
                return True
        else:
            print("❌ ERROR: File not found in database after processing")
            return False

    async def test_file_deletion_timing(self):
        """Test file deletion timing coordination."""
        print("\n=== Testing File Deletion Timing ===")

        # Create a temporary file for deletion test
        delete_test_file = self.test_dir / "delete_test.py"
        delete_test_file.write_text("# File to be deleted\nprint('This will be deleted')\n")

        # First, add it to database
        self.log_event("DB_ADD_START", delete_test_file)
        await process_file_change(delete_test_file, "created")
        self.log_event("DB_ADD_END", delete_test_file)

        # Verify it exists in database
        file_record = self.database.get_file_by_path(str(delete_test_file))
        if not file_record:
            print("❌ ERROR: File was not added to database")
            return False

        print(f"✅ File added to database: {file_record.get('id', 'unknown_id')}")

        # Delete file from filesystem
        self.log_event("FILE_DELETE_START", delete_test_file)
        delete_test_file.unlink()
        self.log_event("FILE_DELETE_END", delete_test_file)

        # Simulate file watcher detection delay
        await asyncio.sleep(0.1)

        # Process deletion
        self.log_event("MCP_DELETE_START", delete_test_file)
        await process_file_change(delete_test_file, "deleted")
        self.log_event("MCP_DELETE_END", delete_test_file)

        # Check if file was removed from database
        self.log_event("DB_QUERY_DELETE_START", delete_test_file)
        deleted_file_record = self.database.get_file_by_path(str(delete_test_file))
        self.log_event("DB_QUERY_DELETE_END", delete_test_file)

        if deleted_file_record:
            print("❌ ERROR: File still exists in database after deletion")
            return False
        else:
            print("✅ File successfully removed from database")
            return True

    async def test_rapid_modifications(self):
        """Test rapid file modifications within debounce period."""
        print("\n=== Testing Rapid Modifications ===")

        rapid_test_file = self.test_dir / "rapid_test.py"
        rapid_test_file.write_text("# Rapid modification test\n")

        # Add to database initially
        await process_file_change(rapid_test_file, "created")

        # Perform rapid modifications
        for i in range(5):
            self.log_event("RAPID_MODIFY_START", rapid_test_file, {"iteration": i})
            content = f"# Rapid modification test - iteration {i}\nprint('Iteration {i}')\n"
            rapid_test_file.write_text(content)

            # Get current mtime
            fs_mtime = rapid_test_file.stat().st_mtime
            self.log_event("RAPID_MODIFY_END", rapid_test_file, {"iteration": i, "fs_mtime": f"{fs_mtime:.6f}"})

            # Small delay between modifications (within debounce period)
            await asyncio.sleep(0.3)

        # Wait for debounce period to complete
        await asyncio.sleep(3.0)

        # Process the final change
        self.log_event("RAPID_PROCESS_START", rapid_test_file)
        await process_file_change(rapid_test_file, "modified")
        self.log_event("RAPID_PROCESS_END", rapid_test_file)

        # Check final database state
        final_record = self.database.get_file_by_path(str(rapid_test_file))
        if final_record:
            db_mtime = final_record.get('mtime', 0)
            fs_mtime = rapid_test_file.stat().st_mtime

            print(f"Final fs_mtime: {fs_mtime:.6f}")
            print(f"Final db_mtime: {db_mtime:.6f}")
            print(f"Difference: {abs(fs_mtime - db_mtime):.6f}s")

            return abs(fs_mtime - db_mtime) < 2.0
        else:
            print("❌ ERROR: File not found in database after rapid modifications")
            return False

    def analyze_timing_events(self):
        """Analyze timing events for coordination issues."""
        print("\n=== Timing Analysis ===")

        if len(self.events_log) < 2:
            print("Not enough events to analyze")
            return

        # Group events by file
        file_events = {}
        for event in self.events_log:
            file_path = event["file_path"]
            if file_path not in file_events:
                file_events[file_path] = []
            file_events[file_path].append(event)

        # Analyze timing gaps
        for file_path, events in file_events.items():
            print(f"\nFile: {Path(file_path).name}")

            for i in range(1, len(events)):
                prev_event = events[i-1]
                curr_event = events[i]

                time_diff = curr_event["timestamp"] - prev_event["timestamp"]

                if time_diff > 0.5:  # Flag delays > 500ms
                    print(f"  ⚠️  Potential delay: {prev_event['event_type']} → {curr_event['event_type']}: {time_diff:.3f}s")
                else:
                    print(f"  ✅ Normal timing: {prev_event['event_type']} → {curr_event['event_type']}: {time_diff:.3f}s")

    async def run_all_tests(self):
        """Run all timing tests."""
        print("🔍 Starting Realtime File Sync Timing Debug Tests")
        print("=" * 60)

        await self.setup()

        results = []

        # Test 1: File modification timing
        try:
            result = await self.test_file_modification_timing()
            results.append(("File Modification Timing", result))
        except Exception as e:
            print(f"❌ File modification test failed: {e}")
            results.append(("File Modification Timing", False))

        # Test 2: File deletion timing
        try:
            result = await self.test_file_deletion_timing()
            results.append(("File Deletion Timing", result))
        except Exception as e:
            print(f"❌ File deletion test failed: {e}")
            results.append(("File Deletion Timing", False))

        # Test 3: Rapid modifications
        try:
            result = await self.test_rapid_modifications()
            results.append(("Rapid Modifications", result))
        except Exception as e:
            print(f"❌ Rapid modifications test failed: {e}")
            results.append(("Rapid Modifications", False))

        # Analyze timing
        self.analyze_timing_events()

        # Summary
        print("\n" + "=" * 60)
        print("🎯 TEST RESULTS SUMMARY")
        print("=" * 60)

        passed = 0
        total = len(results)

        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
            if result:
                passed += 1

        print(f"\nOverall: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed! Timing coordination appears to be working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. This supports the timing coordination hypothesis.")
            return False

    async def cleanup(self):
        """Clean up test environment."""
        print("\n🧹 Cleaning up test environment...")

        if self.database:
            try:
                self.database.close()
            except:
                pass

        if self.test_dir and self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print(f"Removed test directory: {self.test_dir}")


async def main():
    """Main test runner."""
    debugger = TimingDebugger()

    try:
        success = await debugger.run_all_tests()

        print("\n🔍 HYPOTHESIS EVALUATION")
        print("=" * 60)

        if success:
            print("HYPOTHESIS STATUS: DISPROVEN")
            print("The timing coordination appears to be working correctly.")
            print("The bug may be in a different area (search caching, file detection, etc.)")
        else:
            print("HYPOTHESIS STATUS: SUPPORTED")
            print("Timing coordination issues detected.")
            print("The hypothesis about multi-layer timing synchronization problems is likely correct.")

        return success

    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await debugger.cleanup()


if __name__ == "__main__":
    # Enable debug logging
    import logging
    logging.basicConfig(level=logging.DEBUG)

    # Run the test suite
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
