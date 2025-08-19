"""Test MCP server directory argument handling for VS Code compatibility.

This test reproduces the issue where VS Code invokes the MCP server with a
positional directory argument but from a different working directory.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from subprocess import PIPE

import pytest


@pytest.mark.asyncio
async def test_mcp_server_uses_positional_directory_argument():
    """Test that MCP server correctly uses positional directory argument.
    
    This reproduces the VS Code issue where the server is invoked as:
    chunkhound mcp /path/to/project
    from a different working directory.
    """
    # Create temporary directories
    home_dir = Path(tempfile.mkdtemp())
    project_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create project config in project directory (following test patterns)
        db_path = project_dir / ".chunkhound" / "test.db"
        db_path.parent.mkdir(exist_ok=True)
        
        config = {
            "database": {
                "path": str(db_path),
                "provider": "duckdb"
            }
        }
        config_file = project_dir / ".chunkhound.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        # Set environment for MCP mode
        import os
        mcp_env = os.environ.copy()
        mcp_env["CHUNKHOUND_MCP_MODE"] = "1"
        
        # Run MCP server from home_dir with project_dir as argument
        # This simulates VS Code's invocation pattern
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "mcp", "--stdio", str(project_dir),
            cwd=str(home_dir),  # Run from different directory
            env=mcp_env,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE
        )
        
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            request_json = json.dumps(init_request) + "\n"
            proc.stdin.write(request_json.encode())
            await proc.stdin.drain()
            
            # Read the response line
            try:
                response_line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=5.0
                )
                response_text = response_line.decode().strip()
                print(f"Raw response: {response_text}")
                
                if response_text:
                    response = json.loads(response_text)
                    print(f"Parsed response: {response}")
                else:
                    print("Empty response line")
                    
            except asyncio.TimeoutError:
                print("Timeout waiting for response")
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}, raw: {response_text}")
            except Exception as e:
                print(f"Unexpected error reading response: {e}")
            
            # Close stdin and wait for process to finish  
            proc.stdin.close()
            await proc.wait()
            
            # Get the output
            remaining_stdout, stderr = await proc.communicate()
            stderr_text = stderr.decode()
            stdout_text = remaining_stdout.decode()
            
            print(f"MCP server exit code: {proc.returncode}")
            print(f"stdout: {stdout_text}")
            print(f"stderr: {stderr_text}")
            
            if "No ChunkHound project found" in stderr_text:
                # This would be the bug we're testing for
                pytest.fail(
                    "MCP server failed to use positional directory argument. "
                    f"Error: {stderr_text}"
                )
            
            # Success! The server started without the "No ChunkHound project found" error
            # This means it correctly used the positional directory argument
            assert proc.returncode == 0, f"MCP server exited with error code {proc.returncode}"
            print("✓ MCP server correctly used positional directory argument")
            print(f"✓ No 'No ChunkHound project found' error in stderr")
            print(f"✓ Server started successfully from different working directory")
                
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(home_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_mcp_server_handles_empty_directory_gracefully():
    """Test that MCP server handles directories without config files gracefully.
    
    After the fix, the server should be able to start even when pointing to
    a directory that doesn't have a .chunkhound.json file and properly
    respond to MCP protocol initialization.
    """
    import json
    import shutil
    
    home_dir = Path(tempfile.mkdtemp())
    project_dir = Path(tempfile.mkdtemp())
    
    try:
        # Don't create any config files - test graceful handling
        
        # Run MCP server from home_dir with project_dir as argument  
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "mcp", "--stdio", str(project_dir),
            cwd=str(home_dir),
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE
        )
        
        try:
            # Step 1: Send initialize request (with id)
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
            
            # Step 2: Receive initialize response
            response_line = await asyncio.wait_for(
                proc.stdout.readline(), timeout=5.0
            )
            
            init_response = json.loads(response_line.decode())
            
            # Verify we got a valid response with correct structure
            assert "jsonrpc" in init_response and init_response["jsonrpc"] == "2.0"
            assert "id" in init_response and init_response["id"] == 1
            assert "result" in init_response, f"No result in response: {init_response}"
            assert "serverInfo" in init_response["result"]
            assert "protocolVersion" in init_response["result"]
            
            print(f"✓ Server responded with serverInfo: {init_response['result']['serverInfo']}")
            
            # Step 3: Send initialized notification (no id - it's a notification)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
                # No "id" field for notifications
            }
            
            proc.stdin.write((json.dumps(initialized_notification) + "\n").encode())
            await proc.stdin.drain()
            
            # Optional: Test that server is now ready by requesting tools list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            proc.stdin.write((json.dumps(tools_request) + "\n").encode())
            await proc.stdin.drain()
            
            # Read tools response
            tools_line = await asyncio.wait_for(
                proc.stdout.readline(), timeout=5.0
            )
            tools_response = json.loads(tools_line.decode())
            
            # Verify tools response
            assert "result" in tools_response
            assert "tools" in tools_response["result"]
            
            print(f"✓ Server initialized successfully with {len(tools_response['result']['tools'])} tools")
            print("✓ Server handles empty directory gracefully")
            
        finally:
            # Properly terminate the server
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
    
    finally:
        shutil.rmtree(home_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)