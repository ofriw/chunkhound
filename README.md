# ChunkHound

**Semantic and Regex search for your projects via MCP.**

ChunkHound indexes your code and lets AI assistants search it intelligently. It uses Tree-Sitter to parse code and DuckDB for search. Everything is done fully locally.

## Quick Start

```bash
# Install (after PyPI release)
pip install chunkhound

# Or install with uv
uv add chunkhound

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
- **Multi-language support** - Python, Java, C#, and Markdown

## AI Assistant Setup
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

## How It Works

1. **Scan** - ChunkHound reads your Python, Java, C#, and Markdown files
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
- "Find Java interfaces that implement Comparable"
- "Show me C# classes with async methods"
- "Find C# interfaces and their implementations"

## Installation

### Python Package (Recommended)
```bash
# Install via pip
pip install chunkhound

# Or install with uv
uv add chunkhound
```

### Standalone Binary (Zero Dependencies)
Download the latest binary from [releases](https://github.com/chunkhound/chunkhound/releases):

- **Startup Time**: ~0.6 seconds (16x faster than previous versions)
- **Size**: ~106MB directory distribution
- **Dependencies**: None (fully self-contained)
- **Platforms**: Linux, macOS, Windows

```bash
# Download and extract (example)
wget https://github.com/chunkhound/chunkhound/releases/latest/chunkhound-linux.tar.gz
tar -xzf chunkhound-linux.tar.gz
./chunkhound-cli --help
```

## Requirements

- **Python Package**: Python 3.10+
- **Standalone Binary**: No requirements (zero dependencies)
- OpenAI API key (optional, for semantic search)
- Works on macOS and Linux

## Development

```bash
# Development setup
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
uv sync                    # Install dependencies
uv run chunkhound run .    # Index ChunkHound's own code
uv run chunkhound mcp      # Start MCP server
```

Use ChunkHound to search its own codebase while developing!

## Examples

See the [examples/](examples/) directory for sample code demonstrating C# language support features.

## Commands

```bash
chunkhound run .                    # Index current directory
chunkhound run . --verbose         # Index with detailed output
chunkhound run . --no-embeddings   # Skip AI embeddings (faster)
chunkhound mcp --verbose           # Start server with logging
```

## Troubleshooting

**Command not found?**
- For development: Try `uv run chunkhound` instead
- For production: Install with `pip install chunkhound` or `uv add chunkhound`

**Binary CLI slow startup?**
- Use the latest version (1.1.0+) with onedir deployment (~0.6s startup)
- Older single-file binaries had 15+ second startup times (now fixed)
- Ensure you're using the onedir distribution, not deprecated single-file

**Semantic search not working?**
- Set your `OPENAI_API_KEY` environment variable

**"You must provide a model parameter" error?**
- Update to latest version: `pip install --upgrade chunkhound`
- Or specify model explicitly: `chunkhound run . --model text-embedding-3-small`

**Database errors?**
- Delete `.chunkhound.db` and re-run `chunkhound run .`

**Performance Issues?**
- Python CLI: ~0.4s startup (baseline)
- Binary CLI: ~0.6s startup (excellent, 16x faster than old versions)
- If binary is slower, ensure you have the latest onedir distribution

## License

MIT
