"""Test to verify the MCP server initialization fix works correctly.

This test verifies that the server now responds quickly even with large directories,
and that scan progress is available through the stats tool.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from tests.utils.windows_compat import windows_safe_tempdir, database_cleanup_context


class TestMCPFixVerification:
    """Test MCP server initialization fix."""

    @pytest.mark.asyncio
    async def test_mcp_responds_quickly_with_large_directory(self):
        """Test that MCP server now responds quickly even with large directories.
        
        This verifies our fix works - the server should respond to initialize
        within a few seconds even with a large directory.
        """
        with windows_safe_tempdir() as temp_path:
            
            # Create a moderately large directory to test responsiveness
            for i in range(100):  # Enough files to potentially cause delay
                subdir = temp_path / f"module_{i // 10}"
                subdir.mkdir(exist_ok=True)
                
                test_file = subdir / f"file_{i}.py"
                test_file.write_text(f"""
def function_{i}():
    '''Function {i} for testing.'''
    return "value_{i}"

class Class_{i}:
    '''Class {i} for testing.'''
    
    def method_{i}(self):
        return "result_{i}"
""")
            
            # Create minimal config
            config_path = temp_path / ".chunkhound.json"
            db_path = temp_path / ".chunkhound" / "test.db"
            db_path.parent.mkdir(exist_ok=True)
            
            config = {
                "database": {"path": str(db_path), "provider": "duckdb"},
                "indexing": {"include": ["*.py"]}
            }
            config_path.write_text(json.dumps(config))
            
            # Use database cleanup context to ensure proper resource management
            with database_cleanup_context():
                # Start MCP server
                mcp_env = os.environ.copy()
                mcp_env["CHUNKHOUND_MCP_MODE"] = "1"
                
                proc = await asyncio.create_subprocess_exec(
                    "uv", "run", "chunkhound", "mcp", str(temp_path),
                    cwd=temp_path,
                    env=mcp_env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    start_time = time.time()
                
                    # Send initialize request
                    init_request = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    }
                    
                    proc.stdin.write((json.dumps(init_request) + "\n").encode())
                    await proc.stdin.drain()
                    
                    # Should respond quickly now (within 5 seconds - allow extra time for macOS)
                    response_line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=5.0
                    )

                    response_time = time.time() - start_time

                    # Verify quick response
                    assert response_time < 5.0, f"Server took {response_time:.2f} seconds to respond (should be < 5s)"
                    
                    # Verify response structure
                    init_response = json.loads(response_line.decode())
                    assert "result" in init_response, f"No result in response: {init_response}"
                    assert "serverInfo" in init_response["result"], f"No serverInfo in result: {init_response['result']}"
                    assert init_response["result"]["serverInfo"]["name"] == "ChunkHound Code Search"
                    
                    print(f"✅ Server responded in {response_time:.2f} seconds")
                        
                finally:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()

    @pytest.mark.asyncio
    async def test_stats_includes_scan_progress(self):
        """Test that get_stats tool now includes scan progress information."""
        with windows_safe_tempdir() as temp_path:
            
            # Create a few test files
            for i in range(5):
                test_file = temp_path / f"test_{i}.py"
                test_file.write_text(f"def test_{i}(): pass")
            
            # Create minimal config
            config_path = temp_path / ".chunkhound.json"
            db_path = temp_path / ".chunkhound" / "test.db"
            db_path.parent.mkdir(exist_ok=True)
            
            config = {
                "database": {"path": str(db_path), "provider": "duckdb"},
                "indexing": {"include": ["*.py"]}
            }
            config_path.write_text(json.dumps(config))
            
            # Use database cleanup context to ensure proper resource management
            with database_cleanup_context():
                # Start MCP server
                mcp_env = os.environ.copy()
                mcp_env["CHUNKHOUND_MCP_MODE"] = "1"
                
                proc = await asyncio.create_subprocess_exec(
                    "uv", "run", "chunkhound", "mcp", str(temp_path),
                    cwd=temp_path,
                    env=mcp_env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    # Initialize the server
                    init_request = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    }
                    
                    proc.stdin.write((json.dumps(init_request) + "\n").encode())
                    await proc.stdin.drain()
                    
                    # Read initialize response
                    await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
                    
                    # Send initialized notification
                    proc.stdin.write((json.dumps({
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized"
                    }) + "\n").encode())
                    await proc.stdin.drain()
                    
                    # Call get_stats tool
                    stats_request = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "get_stats",
                            "arguments": {}
                        }
                    }
                    
                    proc.stdin.write((json.dumps(stats_request) + "\n").encode())
                    await proc.stdin.drain()
                    
                    # Read stats response
                    stats_line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=5.0
                    )
                    stats_response = json.loads(stats_line.decode())
                    
                    # Verify stats structure
                    assert "result" in stats_response, f"No result in stats response: {stats_response}"
                    assert "content" in stats_response["result"], f"No content in stats result: {stats_response['result']}"
                    
                    # Parse the stats content
                    content = stats_response["result"]["content"][0]["text"]
                    stats_data = json.loads(content)
                    
                    # Verify scan progress is included
                    assert "initial_scan" in stats_data, f"No initial_scan in stats: {stats_data}"
                    
                    scan_info = stats_data["initial_scan"]
                    assert "is_scanning" in scan_info, f"No is_scanning field: {scan_info}"
                    assert "files_processed" in scan_info, f"No files_processed field: {scan_info}"
                    assert "chunks_created" in scan_info, f"No chunks_created field: {scan_info}"
                    assert "started_at" in scan_info, f"No started_at field: {scan_info}"
                    
                    print(f"✅ Scan progress info: {scan_info}")
                        
                finally:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()