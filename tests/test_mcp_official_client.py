#!/usr/bin/env python3
"""Test MCP server using official MCP client SDK."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

# Try to use the official MCP client SDK
try:
    import mcp.client.stdio
    from mcp.types import Tool
    HAS_MCP_CLIENT = True
except ImportError:
    HAS_MCP_CLIENT = False
    print("Official MCP client not available, trying manual approach...")


async def test_mcp_with_official_client():
    """Test MCP server using the official MCP client SDK."""
    if not HAS_MCP_CLIENT:
        print("Skipping official client test - MCP client SDK not available")
        return False
    
    # Create a minimal test project
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Test directory: {temp_dir}")
    
    try:
        # Create test content
        (temp_dir / "test.py").write_text("def hello(): return 'world'")
        
        # Create config
        config_path = temp_dir / ".chunkhound.json"
        db_path = temp_dir / ".chunkhound" / "test.db"
        db_path.parent.mkdir(exist_ok=True)
        
        config_content = {
            "database": {"path": str(db_path), "provider": "duckdb"},
            "indexing": {"include": ["*.py"]}
        }
        config_path.write_text(json.dumps(config_content, indent=2))
        
        # Index the content
        print("Indexing...")
        index_process = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "index", str(temp_dir), "--no-embeddings",
            cwd=temp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await index_process.communicate()
        
        if index_process.returncode != 0:
            print(f"Index failed: {stderr.decode()}")
            return False
        
        print("Index completed successfully")
        
        # Start MCP server
        print("Starting MCP server...")
        mcp_env = os.environ.copy()
        # Clear existing env vars
        for key in list(mcp_env.keys()):
            if key.startswith("CHUNKHOUND_"):
                del mcp_env[key]
        
        mcp_env.update({
            "CHUNKHOUND_PROJECT_ROOT": str(temp_dir),
            "CHUNKHOUND_DATABASE__PATH": str(db_path),
            "CHUNKHOUND_MCP_MODE": "1"
        })
        
        # Use the official MCP client
        try:
            async with mcp.client.stdio.stdio_client(
                "uv", "run", "chunkhound", "mcp", "--stdio", str(temp_dir),
                env=mcp_env,
                cwd=temp_dir
            ) as client:
                print("MCP client connected successfully!")
                
                # Initialize the client
                await client.initialize()
                print("MCP client initialized successfully!")
                
                # List available tools
                tools = await client.list_tools()
                print(f"Available tools: {[tool.name for tool in tools.tools]}")
                
                # Test a search
                if any(tool.name == "search_regex" for tool in tools.tools):
                    result = await client.call_tool("search_regex", {"pattern": "hello"})
                    print(f"Search result: {result}")
                    return True
                else:
                    print("search_regex tool not available")
                    return False
                    
        except Exception as e:
            print(f"Official MCP client failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_mcp_manual_proper_protocol():
    """Test MCP server with manually implemented but proper JSON-RPC protocol."""
    
    # Create a minimal test project  
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Manual test directory: {temp_dir}")
    
    try:
        # Create test content
        (temp_dir / "test.py").write_text("def hello(): return 'world'")
        
        # Create config
        config_path = temp_dir / ".chunkhound.json"
        db_path = temp_dir / ".chunkhound" / "test.db"
        db_path.parent.mkdir(exist_ok=True)
        
        config_content = {
            "database": {"path": str(db_path), "provider": "duckdb"},
            "indexing": {"include": ["*.py"]}
        }
        config_path.write_text(json.dumps(config_content, indent=2))
        
        # Index the content
        print("Manual: Indexing...")
        index_process = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "index", str(temp_dir), "--no-embeddings",
            cwd=temp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await index_process.communicate()
        
        if index_process.returncode != 0:
            print(f"Manual: Index failed: {stderr.decode()}")
            return False
        
        print("Manual: Index completed successfully")
        
        # Start MCP server  
        print("Manual: Starting MCP server...")
        mcp_env = os.environ.copy()
        # Clear existing env vars
        for key in list(mcp_env.keys()):
            if key.startswith("CHUNKHOUND_"):
                del mcp_env[key]
        
        mcp_env["CHUNKHOUND_MCP_MODE"] = "1"
        
        mcp_process = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "mcp", "--stdio", str(temp_dir),
            cwd=temp_dir,
            env=mcp_env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for startup
        await asyncio.sleep(2)
        
        if mcp_process.returncode is not None:
            stdout, stderr = await mcp_process.communicate()
            print(f"Manual: MCP server failed: {stderr.decode()}")
            return False
        
        print("Manual: MCP server started, testing handshake...")
        
        # Test proper MCP handshake
        request_id = 1
        
        # 1. Send initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "manual-test",
                    "version": "1.0.0"
                }
            }
        }
        
        request_json = json.dumps(init_request, separators=(',', ':')) + "\n"
        print(f"Manual: Sending initialize: {request_json.strip()}")
        
        mcp_process.stdin.write(request_json.encode('utf-8'))
        await mcp_process.stdin.drain()
        
        # 2. Read initialize response
        try:
            response_line = await asyncio.wait_for(
                mcp_process.stdout.readline(),
                timeout=10.0
            )
            
            if not response_line:
                print("Manual: No response to initialize")
                return False
                
            response_text = response_line.decode('utf-8').strip()
            print(f"Manual: Initialize response: {response_text}")
            
            try:
                init_response = json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"Manual: Failed to parse initialize response: {e}")
                return False
                
            if "error" in init_response:
                print(f"Manual: Initialize error: {init_response['error']}")
                return False
                
            if "result" not in init_response:
                print(f"Manual: No result in initialize response: {init_response}")
                return False
                
            print("Manual: Initialize successful!")
            
            # 3. Send initialized notification (no response expected)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {}
            }
            
            notification_json = json.dumps(initialized_notification, separators=(',', ':')) + "\n"
            print(f"Manual: Sending initialized notification: {notification_json.strip()}")
            
            mcp_process.stdin.write(notification_json.encode('utf-8'))
            await mcp_process.stdin.drain()
            
            # Wait a moment for server to process
            await asyncio.sleep(0.5)
            
            # 4. Test a tool call
            request_id += 1
            search_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": "search_regex",
                    "arguments": {
                        "pattern": "hello"
                    }
                }
            }
            
            search_json = json.dumps(search_request, separators=(',', ':')) + "\n"
            print(f"Manual: Sending search request: {search_json.strip()}")
            
            mcp_process.stdin.write(search_json.encode('utf-8'))
            await mcp_process.stdin.drain()
            
            # Read search response
            search_response_line = await asyncio.wait_for(
                mcp_process.stdout.readline(),
                timeout=10.0
            )
            
            if search_response_line:
                search_response_text = search_response_line.decode('utf-8').strip()
                print(f"Manual: Search response: {search_response_text}")
                
                try:
                    search_response = json.loads(search_response_text)
                    if "result" in search_response:
                        print("Manual: ✓ Search successful!")
                        return True
                    else:
                        print(f"Manual: Search failed: {search_response}")
                        return False
                except json.JSONDecodeError as e:
                    print(f"Manual: Failed to parse search response: {e}")
                    return False
            else:
                print("Manual: No response to search")
                return False
                
        except asyncio.TimeoutError:
            print("Manual: Timeout waiting for response")
            return False
        finally:
            # Cleanup
            mcp_process.terminate()
            try:
                await asyncio.wait_for(mcp_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                mcp_process.kill()
                await mcp_process.wait()
                
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main():
    """Run both official and manual MCP client tests."""
    print("=" * 60)
    print("Testing MCP server communication")
    print("=" * 60)
    
    # Test 1: Official MCP client
    print("\n1. Testing with official MCP client SDK...")
    official_success = await test_mcp_with_official_client()
    
    # Test 2: Manual protocol implementation
    print("\n2. Testing with manual JSON-RPC protocol...")
    manual_success = await test_mcp_manual_proper_protocol()
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print(f"Official MCP client: {'✓ SUCCESS' if official_success else '✗ FAILED'}")
    print(f"Manual JSON-RPC:     {'✓ SUCCESS' if manual_success else '✗ FAILED'}")
    print("=" * 60)
    
    return official_success or manual_success


if __name__ == "__main__":
    asyncio.run(main())