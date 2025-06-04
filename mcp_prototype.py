#!/usr/bin/env python3
"""
FastMCP prototype server for ChunkHound
Testing basic MCP functionality before full implementation
"""

import random
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("ChunkHound Prototype")

@mcp.tool()
def test_search(pattern: str, limit: int = 5) -> str:
    """Test search function that simulates regex search results"""
    # Simulate some search results
    results = []
    for i in range(min(limit, 3)):
        results.append({
            "file": f"test_file_{i + 1}.py",
            "line": random.randint(10, 100),
            "match": f"def {pattern}_function_{i + 1}():",
            "context": f"Sample code containing {pattern}"
        })
    
    # Return as NDJSON format (one JSON per line)
    output_lines = []
    for result in results:
        import json
        output_lines.append(json.dumps(result))
    
    return "\n".join(output_lines)

@mcp.tool()
def get_test_stats() -> str:
    """Get test statistics for the prototype"""
    import json
    stats = {
        "files": 42,
        "chunks": 1337,
        "embeddings": 0,
        "status": "prototype"
    }
    return json.dumps(stats)

@mcp.tool() 
def health_check() -> str:
    """Check prototype server health"""
    import json
    return json.dumps({"status": "healthy", "version": "prototype"})

if __name__ == "__main__":
    print("Starting ChunkHound MCP Prototype Server")
    print("This server will communicate via stdin/stdout")
    mcp.run()  # Uses STDIO transport by default