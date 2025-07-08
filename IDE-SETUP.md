# IDE Setup for ChunkHound Development

**Quick setup for developing ChunkHound using ChunkHound itself**

## Prerequisites

```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
uv sync                 # Install dependencies
uv run chunkhound run . # Index ChunkHound's own code
```

## Zed Editor (Recommended)

Create `.zed/settings.json` in the ChunkHound directory:

```json
{
  "context_servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "--db", ".chunkhound.duckdb"],
      "cwd": ".",
      "env": {
        "CHUNKHOUND_EMBEDDING_API_KEY": "your-openai-api-key-here"
      }
    }
  }
}
```

## VS Code

Install the MCP extension, then add to workspace `.vscode/settings.json`:

```json
{
  "mcp.servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"],
      "cwd": "${workspaceFolder}",
      "env": {
        "CHUNKHOUND_DB_PATH": "${workspaceFolder}/.chunkhound.duckdb",
        "CHUNKHOUND_EMBEDDING_API_KEY": "your-openai-api-key-here"
      }
    }
  }
}
```

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "--db", "/full/path/to/chunkhound/.chunkhound.duckdb"],
      "cwd": "/full/path/to/chunkhound",
      "env": {
        "CHUNKHOUND_EMBEDDING_API_KEY": "your-openai-api-key-here"
      }
    }
  }
}
```

## Development Workflow

1. **Make code changes** to ChunkHound
2. **Re-index**: `uv run chunkhound run . --verbose`
3. **Use AI assistant** to search the updated codebase
4. **Ask questions** like:
   - "Find database connection functions"
   - "Show me how parsing works"
   - "Find all async functions"
   - "How does the MCP server handle requests?"

## Environment Variables

Create `.env` file in ChunkHound directory:

```bash
CHUNKHOUND_EMBEDDING_API_KEY=your-openai-api-key-here
CHUNKHOUND_DB_PATH=./.chunkhound.duckdb
```

## Troubleshooting

- **MCP not connecting**: Check JSON syntax and file paths
- **Tools not appearing**: Restart your IDE after configuration changes
- **Database not found**: Run `uv run chunkhound run .` first to create database
- **Permission denied**: Make sure `uv` is in your PATH

## Quick Test

```bash
# Test MCP server directly
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | uv run chunkhound mcp

# Should return 4 tools: search_regex, search_semantic, get_stats, health_check
```