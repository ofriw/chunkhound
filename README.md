# ChunkHound

**Local code search with regex and AI-powered semantic search.**

Dead simple to use. Dead simple to develop.

## For Users

### Install & Use
```bash
pip install chunkhound
chunkhound run .        # Index your code
chunkhound mcp          # Start MCP server for AI assistants
```

That's it! ChunkHound indexes your code and provides search tools for AI assistants like Claude Desktop, Cursor, and VS Code.

### AI Assistant Integration

**Claude Desktop** - Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "chunkhound",
      "args": ["mcp", "--db", "/path/to/your/project/.chunkhound.duckdb"],
      "env": {
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**VS Code/Cursor** - Install MCP extension and configure similarly.

### What You Get
- **Regex Search**: Find code patterns instantly
- **Semantic Search**: AI-powered conceptual search (requires OpenAI key)
- **Smart Parsing**: Extracts functions, classes, methods automatically
- **NDJSON Output**: Perfect for AI assistant integration

## For Contributors

### Development Setup
```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
uv sync                     # Install dependencies
uv run chunkhound run .     # Index ChunkHound's own code
uv run chunkhound mcp       # Start MCP server
```

**ChunkHound indexes itself** during development - use it to search its own codebase while working on it!

### Development Commands
```bash
# Essential commands
make setup          # One-time setup (uses uv)
make dev            # Index current directory  
make test           # Run tests
make check          # Lint + test

# Development workflow
uv run chunkhound run . --verbose      # Re-index after changes
./scripts/mcp-server.sh               # Start MCP server with logging
```

### IDE Integration for Development

**Zed** - Create `.zed/settings.json`:
```json
{
  "context_servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "--db", ".chunkhound.duckdb"],
      "cwd": ".",
      "env": {
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**VS Code** - Add to workspace settings:
```json
{
  "mcp.servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"],
      "cwd": "${workspaceFolder}",
      "env": {
        "CHUNKHOUND_DB_PATH": "${workspaceFolder}/.chunkhound.duckdb"
      }
    }
  }
}
```

### Using ChunkHound to Develop ChunkHound

This is the key workflow - ChunkHound searches its own code:

```bash
# Index the codebase
uv run chunkhound run . --verbose

# Start MCP server
uv run chunkhound mcp --verbose

# Now use in your AI assistant:
# "Find all database connection functions"
# "Show me how embeddings are processed" 
# "Search for error handling patterns"
```

**Example searches on ChunkHound's codebase:**
- `"def.*database"` - Database functions
- `"class.*Parser"` - Parser implementations  
- `"async.*embed"` - Embedding functions
- Semantic: "How are chunks stored?" - Finds storage logic

## Architecture

- **Database**: DuckDB with vector search
- **Parsing**: Tree-sitter for AST extraction
- **Embeddings**: OpenAI text-embedding-3-small
- **Protocol**: MCP (Model Context Protocol)
- **Search**: Regex + vector similarity

## MCP Tools

ChunkHound provides these tools to AI assistants:

| Tool | Description | Example |
|------|-------------|---------|
| `search_regex` | Regex pattern search | `search_regex(pattern="def.*async", limit=5)` |
| `search_semantic` | AI semantic search | `search_semantic(query="database connection")` |
| `get_stats` | Database statistics | `get_stats()` |
| `health_check` | System status | `health_check()` |

## Requirements

- **Python 3.10+** (for uv development)
- **OpenAI API key** (optional, for semantic search)
- **Works on**: macOS, Linux

## Advanced Usage

```bash
# Custom exclude patterns
chunkhound run . --exclude "node_modules/*" --exclude "*.log"

# Skip embeddings (faster, regex only)
chunkhound run . --no-embeddings

# Custom database location
chunkhound run . --db ./my-project.duckdb
chunkhound mcp --db ./my-project.duckdb
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Command not found | Run `pip install chunkhound` or use `uv run chunkhound` |
| Database errors | Delete `~/.cache/chunkhound/` and re-index |
| MCP not connecting | Check config file syntax and paths |
| Semantic search fails | Set `OPENAI_API_KEY` environment variable |

## Contributing

1. Fork and clone repo
2. Run `uv sync` to setup
3. Use `uv run chunkhound run .` to index for development
4. Make changes and test with `make check`
5. Use ChunkHound to search its own code while developing!

## License

MIT License