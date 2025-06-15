#!/usr/bin/env python3
"""
Simple Filesystem Event Test - Minimal Investigation

Based on realtime-indexing-file-watcher-null-2025-06-14.md investigation:
- The hypothesis is that file watcher initialization times out in MCP server
- This test bypasses all database/CLI complexity and focuses on basic file watching
- Creates files and checks if they trigger any observable system activity
"""

import os
import sys
import time
import uuid
import subprocess
from pathlib import Path
from datetime import datetime

def log_with_timestamp(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {level}: {message}")

def get_mcp_server_info():
    """Get information about running MCP server"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )

        lines = result.stdout.split('\n')
        mcp_lines = [line for line in lines if 'chunkhound' in line and '--watch' in line]

        if mcp_lines:
            # Extract PID and command
            parts = mcp_lines[0].split()
            pid = parts[1]
            cmd_start = None
            for i, part in enumerate(parts):
                if 'chunkhound' in part:
                    cmd_start = i
                    break

            if cmd_start:
                command = ' '.join(parts[cmd_start:])
                return {'pid': pid, 'command': command}

        return None

    except Exception as e:
        log_with_timestamp(f"Process check failed: {e}", "ERROR")
        return None

def monitor_system_activity(duration=5):
    """Monitor system activity for the MCP server process"""
    mcp_info = get_mcp_server_info()
    if not mcp_info:
        return None

    pid = mcp_info['pid']
    log_with_timestamp(f"Monitoring MCP server PID {pid} for {duration} seconds...")

    try:
        # Get initial CPU/memory stats
        result = subprocess.run(
            ["ps", "-p", pid, "-o", "pid,pcpu,pmem,time"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            initial_stats = result.stdout.strip().split('\n')[-1]
            log_with_timestamp(f"Initial stats: {initial_stats}")

            # Wait
            time.sleep(duration)

            # Get final stats
            result = subprocess.run(
                ["ps", "-p", pid, "-o", "pid,pcpu,pmem,time"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                final_stats = result.stdout.strip().split('\n')[-1]
                log_with_timestamp(f"Final stats: {final_stats}")
                return {'initial': initial_stats, 'final': final_stats}

        return None

    except Exception as e:
        log_with_timestamp(f"Monitoring failed: {e}", "ERROR")
        return None

def test_filesystem_events():
    """Test basic filesystem event detection"""

    log_with_timestamp("=== Simple Filesystem Event Test ===")

    # Check MCP server
    mcp_info = get_mcp_server_info()
    if not mcp_info:
        log_with_timestamp("❌ MCP server not found", "ERROR")
        return False

    log_with_timestamp(f"✅ Found MCP server: PID {mcp_info['pid']}")
    log_with_timestamp(f"Command: {mcp_info['command']}")

    # Create unique test content
    test_marker = f"FILESYSTEM_TEST_{uuid.uuid4().hex[:12]}"
    timestamp = int(time.time())

    test_content = f'''
# Filesystem Event Test File
# Created: {datetime.now().isoformat()}
# Marker: {test_marker}
# Timestamp: {timestamp}

def test_function_{timestamp}():
    """Test function for filesystem event detection"""
    return "{test_marker}"

class TestClass_{timestamp}:
    """Test class for filesystem event detection"""
    marker = "{test_marker}"
'''

    # Create test file
    test_filename = f"filesystem_test_{timestamp}.py"
    test_file = Path(test_filename)

    log_with_timestamp(f"Creating test file: {test_file}")

    # Monitor system activity before file creation
    log_with_timestamp("Monitoring baseline activity...")
    baseline_stats = monitor_system_activity(3)

    # Create the file
    test_file.write_text(test_content)
    log_with_timestamp(f"✅ Created file: {test_file} ({test_file.stat().st_size} bytes)")

    # Monitor system activity after file creation
    log_with_timestamp("Monitoring activity after file creation...")
    post_create_stats = monitor_system_activity(5)

    # Modify the file
    log_with_timestamp("Modifying test file...")
    modified_content = test_content + f"\n# Modified at {datetime.now().isoformat()}\n"
    test_file.write_text(modified_content)
    log_with_timestamp(f"✅ Modified file: {test_file} ({test_file.stat().st_size} bytes)")

    # Monitor system activity after modification
    log_with_timestamp("Monitoring activity after file modification...")
    post_modify_stats = monitor_system_activity(5)

    # Analysis
    log_with_timestamp("=== ANALYSIS ===")

    # Check if process is still running
    final_mcp_info = get_mcp_server_info()
    if not final_mcp_info:
        log_with_timestamp("❌ MCP server stopped during test", "ERROR")
        return False

    if final_mcp_info['pid'] != mcp_info['pid']:
        log_with_timestamp("⚠️  MCP server PID changed during test", "WARNING")
    else:
        log_with_timestamp("✅ MCP server remained stable during test")

    # Simple heuristic: if the server is doing filesystem watching,
    # we might see some activity (though this is not definitive)
    log_with_timestamp("📊 System activity summary:")
    log_with_timestamp(f"   Baseline: {baseline_stats}")
    log_with_timestamp(f"   Post-create: {post_create_stats}")
    log_with_timestamp(f"   Post-modify: {post_modify_stats}")

    # Cleanup
    try:
        test_file.unlink()
        log_with_timestamp(f"🧹 Cleaned up: {test_file}")
    except Exception as e:
        log_with_timestamp(f"Cleanup failed: {e}", "ERROR")

    # Since we can't definitively test file watching without access to the server's
    # internal state, we'll report based on what we observed
    log_with_timestamp("=== CONCLUSION ===")
    log_with_timestamp("🤔 INCONCLUSIVE: Cannot definitively test file watching without MCP server internals")
    log_with_timestamp("   → MCP server is running with --watch flag")
    log_with_timestamp("   → Server remained stable during file operations")
    log_with_timestamp("   → No crashes or obvious failures detected")
    log_with_timestamp("   → Real issue likely requires server-side debugging")

    return True

def main():
    """Run the simple filesystem event test"""

    try:
        # Ensure we're in the right directory
        os.chdir(Path(__file__).parent)

        success = test_filesystem_events()

        if success:
            log_with_timestamp("✅ TEST COMPLETED: Basic filesystem operations successful")
            log_with_timestamp("💡 RECOMMENDATION: Debug MCP server file watcher initialization timeout")
        else:
            log_with_timestamp("❌ TEST FAILED: Basic filesystem operations failed")

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
