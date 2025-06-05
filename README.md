# ChunkHound

**AI-powered code search for your projects.**

ChunkHound indexes your code and lets AI assistants search it intelligently.

## Quick Start

```bash
# Install
uv pip install chunkhound

# Index your code  
chunkhound run .

# Start search server for AI assistants
chunkhound mcp
```

That's it! Your code is now searchable by AI assistants.

## What It Does

- **Indexes your code** - Finds functions, classes, and methods automatically
- **Regex search** - Find exact patterns like `def.*async` 
- **Semantic search** - Ask questions like "How do I connect to the database?"
- **Works with AI assistants** - Claude, Cursor, VS Code, etc.

## AI Assistant Setup

### Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "chunkhound",
      "args": ["mcp"],
      "env": {
        "OPENAI_API_KEY": "your-openai-key-here"
      }
    }
  }
}
```

### VS Code / Cursor

Install the MCP extension and add similar config.

## How It Works

1. **Scan** - ChunkHound reads your Python files
2. **Parse** - Extracts functions, classes, methods using tree-sitter
3. **Index** - Stores code chunks in a local database
4. **Embed** - Creates AI embeddings for semantic search (optional)
5. **Search** - AI assistants can now search your code

## Search Examples

Once running, ask your AI assistant:

- "Find all database connection functions"
- "Show me error handling patterns"  
- "How is user authentication implemented?"
- "Find functions that process files"

## Requirements

- Python 3.10+
- OpenAI API key (optional, for semantic search)
- Works on macOS and Linux

## Development

```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
uv sync                    # Install dependencies
uv run chunkhound run .    # Index ChunkHound's own code
uv run chunkhound mcp      # Start MCP server
```

Use ChunkHound to search its own codebase while developing!

## Commands

```bash
chunkhound run .                    # Index current directory
chunkhound run . --verbose         # Index with detailed output
chunkhound run . --no-embeddings   # Skip AI embeddings (faster)
chunkhound mcp --verbose           # Start server with logging
```

## Troubleshooting

**Command not found?**
- Try `uv run chunkhound` instead
- Or install with `uv pip install chunkhound`

**Semantic search not working?** 
- Set your `OPENAI_API_KEY` environment variable

**Database errors?**
- Delete `.chunkhound.db` and re-run `chunkhound run .`

## License

MIT