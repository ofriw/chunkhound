#!/usr/bin/env python3
"""Test MCP server startup to see what error we get."""

import asyncio
import subprocess
import tempfile
from pathlib import Path
import json

async def test_server_startup():
    """Test basic server startup."""
    
    # Create minimal test
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Test directory: {temp_dir}")
    
    try:
        # Create test content and config
        (temp_dir / "test.py").write_text("def hello(): return 'world'")
        
        config_path = temp_dir / ".chunkhound.json"
        db_path = temp_dir / ".chunkhound" / "test.db"
        db_path.parent.mkdir(exist_ok=True)
        
        config_content = {
            "database": {"path": str(db_path), "provider": "duckdb"},
            "indexing": {"include": ["*.py"]}
        }
        config_path.write_text(json.dumps(config_content, indent=2))
        
        # Try to start MCP server
        print("Starting MCP server...")
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "chunkhound", "mcp", "--stdio", str(temp_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Give it a moment to start or fail
        await asyncio.sleep(2)
        
        if process.returncode is not None:
            stdout, stderr = await process.communicate()
            print(f"Server failed to start!")
            print(f"Return code: {process.returncode}")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return False
        else:
            print("Server started successfully!")
            process.terminate()
            await process.wait()
            return True
            
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(test_server_startup())
    print(f"Test {'PASSED' if success else 'FAILED'}")