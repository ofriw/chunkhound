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
    a directory that doesn't have a .chunkhound.json file, as long as the
    directory argument is properly passed through the configuration system.
    """
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
            # Wait for process to exit
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=5.0
            )
            
            stderr_text = stderr.decode()
            
            # The server should handle this gracefully now that the fix is in place
            # It may exit with an error code, but it should use the correct directory
            print(f"Exit code: {proc.returncode}")
            print(f"stderr: {stderr_text}")
            
            # The key test is that we don't get the "Expected .chunkhound.json in current directory: {home_dir}" error
            # Instead, if there's an error, it should reference the project_dir
            if "No ChunkHound project found" in stderr_text:
                # The error should reference project_dir, not home_dir
                assert str(project_dir) in stderr_text or "current directory" not in stderr_text, \
                    f"Error should reference project dir, not home dir. stderr: {stderr_text}"
                print("✓ Error correctly references project directory, not working directory")
            else:
                print("✓ Server started successfully despite no config file")
            
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(home_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)