#!/usr/bin/env python3
"""
Minimal investigation script to test the event detection and processing pipeline.

This script tests the complete pipeline from file system events to database updates
to identify where the real-time indexing failure occurs.
"""

import asyncio
import time
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add chunkhound to path
sys.path.insert(0, str(Path(__file__).parent))

from chunkhound.file_watcher import FileWatcherManager
from providers.database.duckdb_provider import DuckDBProvider


class EventPipelineInvestigator:
    """Minimal test to investigate the event processing pipeline."""

    def __init__(self):
        self.temp_dir = None
        self.test_db = None
        self.file_watcher = None
        self.callback_calls = []
        self.test_start_time = time.time()

    async def setup(self):
        """Set up test environment."""
        print(f"INVESTIGATION: Setting up test environment at {time.time():.6f}")

        # Create temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp(prefix="chunkhound_investigation_"))
        print(f"INVESTIGATION: Created temp directory: {self.temp_dir}")

        # Create temporary database
        db_path = self.temp_dir / "test.db"
        self.test_db = DuckDBProvider(str(db_path))
        self.test_db.connect()
        print(f"INVESTIGATION: Created test database: {db_path}")

        # Create file watcher
        self.file_watcher = FileWatcherManager()

        print(f"INVESTIGATION: Setup complete at {time.time():.6f}")

    async def test_callback(self, file_path: Path, event_type: str):
        """Test callback to track all events."""
        callback_time = time.time()
        relative_time = callback_time - self.test_start_time
        call_info = {
            'timestamp': callback_time,
            'relative_time': relative_time,
            'file_path': str(file_path),
            'event_type': event_type
        }
        self.callback_calls.append(call_info)

        print(f"CALLBACK_RECEIVED: {relative_time:.3f}s - {event_type} - {file_path}")

        # Try to process with database (if available)
        if self.test_db:
            try:
                if event_type == 'deleted':
                    result = self.test_db.delete_file_completely(str(file_path))
                    print(f"DATABASE_DELETE: {relative_time:.3f}s - Result: {result}")
                else:
                    if file_path.exists() and file_path.is_file():
                        result = self.test_db.process_file_incremental(file_path=file_path)
                        print(f"DATABASE_PROCESS: {relative_time:.3f}s - Result: {result}")
            except Exception as e:
                print(f"DATABASE_ERROR: {relative_time:.3f}s - {e}")

    async def run_investigation(self):
        """Run the complete investigation."""
        print(f"\n{'='*60}")
        print(f"EVENT PIPELINE INVESTIGATION STARTING")
        print(f"{'='*60}")

        try:
            # Setup
            await self.setup()

            # Initialize file watcher with correct watch paths
            print(f"\nINVESTIGATION: Initializing FileWatcher at {time.time():.6f}")
            init_success = await self.file_watcher.initialize(self.test_callback, watch_paths=[self.temp_dir])
            print(f"INVESTIGATION: FileWatcher initialization result: {init_success}")

            if not init_success:
                print("INVESTIGATION: FileWatcher initialization failed, aborting test")
                return

            # Wait for initialization to stabilize
            print(f"INVESTIGATION: Waiting 2 seconds for initialization to stabilize...")
            await asyncio.sleep(2.0)

            # Test 1: Create a new file
            print(f"\nTEST 1: Creating new file at {time.time():.6f}")
            test_file = self.temp_dir / "test_file_1.txt"
            test_file.write_text("Hello, World! Test file content.")
            print(f"TEST 1: File created: {test_file}")

            # Wait for events
            await asyncio.sleep(3.0)

            # Test 2: Modify the file
            print(f"\nTEST 2: Modifying file at {time.time():.6f}")
            test_file.write_text("Hello, World! Modified content.")
            print(f"TEST 2: File modified: {test_file}")

            # Wait for events
            await asyncio.sleep(3.0)

            # Test 3: Create another file
            print(f"\nTEST 3: Creating second file at {time.time():.6f}")
            test_file_2 = self.temp_dir / "test_file_2.py"
            test_file_2.write_text("# Python test file\ndef hello():\n    print('Hello from Python')\n")
            print(f"TEST 3: File created: {test_file_2}")

            # Wait for events
            await asyncio.sleep(3.0)

            # Test 4: Delete first file
            print(f"\nTEST 4: Deleting first file at {time.time():.6f}")
            test_file.unlink()
            print(f"TEST 4: File deleted: {test_file}")

            # Wait for events
            await asyncio.sleep(3.0)

            # Report results
            await self.report_results()

        except Exception as e:
            print(f"INVESTIGATION: Error during investigation: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

    async def report_results(self):
        """Report investigation results."""
        print(f"\n{'='*60}")
        print(f"INVESTIGATION RESULTS")
        print(f"{'='*60}")

        print(f"Total callback calls received: {len(self.callback_calls)}")

        if self.callback_calls:
            print(f"\nCallback Details:")
            for i, call in enumerate(self.callback_calls, 1):
                print(f"  {i}. {call['relative_time']:.3f}s - {call['event_type']} - {call['file_path']}")
        else:
            print(f"\n❌ NO CALLBACKS RECEIVED - This indicates the event pipeline is broken!")
            print(f"   Events are not reaching the callback function.")
            print(f"   Possible causes:")
            print(f"   - Observer not detecting file system events")
            print(f"   - Events not being queued properly")
            print(f"   - Queue processing loop not running")
            print(f"   - Callback not being called from queue processor")

        # Check FileWatcher state
        if self.file_watcher:
            print(f"\nFileWatcher State:")
            print(f"  Watcher exists: {self.file_watcher.watcher is not None}")
            if self.file_watcher.watcher:
                print(f"  Is watching: {getattr(self.file_watcher.watcher, 'is_watching', 'unknown')}")
                if hasattr(self.file_watcher.watcher, 'observer'):
                    observer = self.file_watcher.watcher.observer
                    print(f"  Observer exists: {observer is not None}")
                    if observer:
                        print(f"  Observer is alive: {observer.is_alive()}")

            print(f"  Processing task exists: {self.file_watcher.processing_task is not None}")
            if self.file_watcher.processing_task:
                print(f"  Processing task done: {self.file_watcher.processing_task.done()}")
                print(f"  Processing task cancelled: {self.file_watcher.processing_task.cancelled()}")
                if self.file_watcher.processing_task.done() and not self.file_watcher.processing_task.cancelled():
                    try:
                        exc = self.file_watcher.processing_task.exception()
                        if exc:
                            print(f"  Processing task exception: {exc}")
                    except Exception as e:
                        print(f"  Error checking task exception: {e}")

            print(f"  Event queue exists: {self.file_watcher.event_queue is not None}")
            if self.file_watcher.event_queue:
                print(f"  Event queue size: {self.file_watcher.event_queue.qsize()}")

        # Database state
        if self.test_db:
            try:
                stats = self.test_db.get_stats()
                print(f"\nDatabase Stats:")
                print(f"  Files: {stats.get('files', 'unknown')}")
                print(f"  Chunks: {stats.get('chunks', 'unknown')}")
            except Exception as e:
                print(f"  Error getting database stats: {e}")

    async def cleanup(self):
        """Clean up test environment."""
        print(f"\nINVESTIGATION: Cleaning up at {time.time():.6f}")

        # Stop file watcher
        if self.file_watcher:
            try:
                await self.file_watcher.cleanup()
            except Exception as e:
                print(f"INVESTIGATION: Error cleaning up file watcher: {e}")

        # Close database
        if self.test_db:
            try:
                self.test_db.disconnect()
            except Exception as e:
                print(f"INVESTIGATION: Error closing database: {e}")

        # Remove temp directory
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                print(f"INVESTIGATION: Removed temp directory: {self.temp_dir}")
            except Exception as e:
                print(f"INVESTIGATION: Error removing temp directory: {e}")


async def main():
    """Run the investigation."""
    print(f"FileWatcher Event Pipeline Investigation")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    investigator = EventPipelineInvestigator()
    await investigator.run_investigation()

    print(f"\nInvestigation completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
