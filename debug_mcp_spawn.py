#!/usr/bin/env python3
"""
MCP Binary Spawn Debug Script
Tests the hypothesis: "Silent Startup Failure" vs "True Spawn Failure"

This script investigates whether the chunkhound binary:
1. Fails to spawn at all (process creation failure)
2. Spawns but fails silently during initialization
3. Works but has JSON-RPC protocol issues
"""

import subprocess
import time
import os
import sys
import json
from pathlib import Path


def test_binary_execution():
    """Test 1: Basic binary execution and process creation"""
    print("=== TEST 1: Binary Execution ===")

    binary_path = "./dist/chunkhound-macos-universal/chunkhound-optimized"

    # Test 1a: Basic version check
    try:
        result = subprocess.run([binary_path, "--version"],
                              capture_output=True, text=True, timeout=5)
        print(f"Version check: {result.returncode}")
        print(f"Output: {result.stdout.strip()}")
        if result.stderr:
            print(f"Stderr: {result.stderr.strip()}")
    except Exception as e:
        print(f"Version check failed: {e}")
        return False

    # Test 1b: MCP command spawn test
    try:
        process = subprocess.Popen(
            [binary_path, "mcp", "--db", ".chunkhound.db"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"MCP process spawned: PID {process.pid}")

        # Give it a moment to initialize
        time.sleep(0.5)

        # Check if process is still running
        poll_result = process.poll()
        if poll_result is None:
            print("Process is running (not terminated)")
            process.terminate()
            process.wait()
            return True
        else:
            print(f"Process terminated early with code: {poll_result}")
            stdout, stderr = process.communicate()
            if stdout:
                print(f"Stdout: {stdout}")
            if stderr:
                print(f"Stderr: {stderr}")
            return False

    except Exception as e:
        print(f"MCP spawn test failed: {e}")
        return False


def test_mcp_protocol():
    """Test 2: JSON-RPC Protocol Handshake"""
    print("\n=== TEST 2: JSON-RPC Protocol ===")

    binary_path = "./dist/chunkhound-macos-universal/chunkhound-optimized"

    # Initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}}
        }
    }

    try:
        process = subprocess.Popen(
            [binary_path, "mcp", "--db", ".chunkhound.db"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print(f"Sending initialize request to PID {process.pid}")

        # Send initialization request
        request_json = json.dumps(init_request) + "\n"
        process.stdin.write(request_json)
        process.stdin.flush()

        # Wait for response with timeout
        try:
            stdout, stderr = process.communicate(timeout=3.0)
            print(f"Process exit code: {process.returncode}")

            if stdout:
                print(f"Response received: {stdout}")
                # Try to parse as JSON
                try:
                    response = json.loads(stdout.strip())
                    if "result" in response:
                        print("✅ Valid JSON-RPC initialize response")
                        return True
                    else:
                        print("❌ Invalid JSON-RPC response structure")
                except json.JSONDecodeError:
                    print("❌ Response is not valid JSON")
            else:
                print("❌ No response received")

            if stderr:
                print(f"Error output: {stderr}")

        except subprocess.TimeoutExpired:
            print("❌ Timeout waiting for response")
            process.kill()
            stdout, stderr = process.communicate()
            if stderr:
                print(f"Error after timeout: {stderr}")

        return False

    except Exception as e:
        print(f"Protocol test failed: {e}")
        return False


def test_database_connectivity():
    """Test 3: Database Access in Current Directory"""
    print("\n=== TEST 3: Database Connectivity ===")

    db_path = Path(".chunkhound.db")

    # Check if database file exists or can be created
    try:
        if db_path.exists():
            print(f"Database exists: {db_path.stat().st_size} bytes")
        else:
            print("Database file does not exist (will be created)")

        # Test write permissions in current directory
        test_file = Path(".chunkhound_test")
        try:
            test_file.write_text("test")
            test_file.unlink()
            print("✅ Write permissions in current directory: OK")
        except Exception as e:
            print(f"❌ Write permission test failed: {e}")
            return False

        return True

    except Exception as e:
        print(f"Database connectivity test failed: {e}")
        return False


def test_environment_comparison():
    """Test 4: Environment Variable Analysis"""
    print("\n=== TEST 4: Environment Analysis ===")

    # Key environment variables that might affect MCP
    key_vars = [
        "PATH", "PYTHONPATH", "HOME", "USER", "TERM",
        "SHELL", "PWD", "CHUNKHOUND_MCP_MODE", "CHUNKHOUND_DB_PATH"
    ]

    print("Current environment:")
    for var in key_vars:
        value = os.environ.get(var, "<not set>")
        print(f"  {var}: {value}")

    # Test with explicit MCP mode environment
    print("\nTesting with explicit MCP environment:")
    env = os.environ.copy()
    env["CHUNKHOUND_MCP_MODE"] = "1"
    env["CHUNKHOUND_DB_PATH"] = str(Path(".chunkhound.db").absolute())

    try:
        result = subprocess.run([
            "./dist/chunkhound-macos-universal/chunkhound-optimized",
            "mcp", "--db", ".chunkhound.db"
        ], env=env, capture_output=True, text=True, timeout=2.0)

        print(f"With explicit env - Exit code: {result.returncode}")
        if result.stdout:
            print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("Process with explicit env timed out (might be waiting for input)")
        return True  # Timeout suggests it's running
    except Exception as e:
        print(f"Environment test failed: {e}")
        return False


def main():
    """Run all diagnostic tests"""
    print("ChunkHound MCP Binary Spawn Diagnostic")
    print("=" * 50)

    working_dir = Path.cwd()
    print(f"Working directory: {working_dir}")
    print(f"Binary path: {Path('./dist/chunkhound-macos-universal/chunkhound-optimized').absolute()}")

    # Run all tests
    tests = [
        ("Binary Execution", test_binary_execution),
        ("JSON-RPC Protocol", test_mcp_protocol),
        ("Database Connectivity", test_database_connectivity),
        ("Environment Analysis", test_environment_comparison),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 50)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    # Hypothesis analysis
    all_passed = all(results.values())
    spawn_test_passed = results.get("Binary Execution", False)
    protocol_test_passed = results.get("JSON-RPC Protocol", False)

    print("\nHYPOTHESIS ANALYSIS:")
    if not spawn_test_passed:
        print("❌ TRUE SPAWN FAILURE: Binary fails to start process")
    elif spawn_test_passed and not protocol_test_passed:
        print("❌ SILENT STARTUP FAILURE: Binary spawns but fails during initialization")
    elif all_passed:
        print("✅ BINARY WORKS: Issue may be IDE-specific environment")
    else:
        print("❓ MIXED RESULTS: Partial functionality")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
