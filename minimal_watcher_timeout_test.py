#!/usr/bin/env python3
"""
Minimal File Watcher Timeout Hypothesis Test

Based on notes from realtime-indexing-file-watcher-null-2025-06-14.md:
- File watcher initialization has 5-second timeout in MCP server
- If timeout occurs, continues without real-time indexing
- This test isolates the timeout behavior to prove/disprove hypothesis
"""

import asyncio
import time
import os
import sys
from pathlib import Path

# Add chunkhound to path
sys.path.insert(0, str(Path(__file__).parent))

from chunkhound.file_watcher import FileWatcherManager, is_filesystem_watching_enabled

async def dummy_callback(event_type, file_path):
    """Dummy callback for testing"""
    print(f"CALLBACK: {event_type} - {file_path}")

async def test_file_watcher_timeout():
    """Test if file watcher initialization times out like in MCP server"""

    print("=== File Watcher Timeout Hypothesis Test ===")
    print(f"Test started at: {time.time():.6f}")

    # Check prerequisites
    enabled = is_filesystem_watching_enabled()
    print(f"Filesystem watching enabled: {enabled}")

    if not enabled:
        print("❌ BLOCKED: Filesystem watching disabled")
        return False

    # Test 1: Normal initialization (no timeout)
    print("\n--- Test 1: Normal initialization ---")
    try:
        watcher1 = FileWatcherManager()
        start_time = time.time()
        success = await watcher1.initialize(dummy_callback)
        duration = time.time() - start_time
        print(f"Normal init: {success} in {duration:.2f}s")
        if watcher1.file_watcher:
            watcher1.file_watcher.stop()
    except Exception as e:
        print(f"Normal init failed: {e}")
        return False

    # Test 2: With 5-second timeout (MCP server behavior)
    print("\n--- Test 2: With 5-second timeout (MCP server simulation) ---")
    try:
        watcher2 = FileWatcherManager()
        start_time = time.time()

        try:
            success = await asyncio.wait_for(
                watcher2.initialize(dummy_callback),
                timeout=5.0
            )
            duration = time.time() - start_time
            print(f"✅ Timeout init: SUCCESS in {duration:.2f}s")
            if watcher2.file_watcher:
                watcher2.file_watcher.stop()
            return True

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            print(f"❌ Timeout init: TIMED OUT after {duration:.2f}s")
            print("🎯 HYPOTHESIS CONFIRMED: File watcher initialization times out")
            return False

    except Exception as e:
        print(f"Timeout test failed: {e}")
        return False

def main():
    """Run the timeout test"""
    print("Starting minimal file watcher timeout diagnostic...")

    # Run async test
    try:
        result = asyncio.run(test_file_watcher_timeout())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        result = False
    except Exception as e:
        print(f"💥 Test crashed: {e}")
        result = False

    print(f"\n=== RESULTS ===")
    if result:
        print("✅ HYPOTHESIS DISPROVEN: File watcher initializes within timeout")
        print("   → Real-time indexing should work (issue elsewhere)")
    else:
        print("🎯 HYPOTHESIS CONFIRMED: File watcher initialization times out")
        print("   → This explains why real-time indexing fails")
        print("   → MCP server continues without file watching after timeout")

    return result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
