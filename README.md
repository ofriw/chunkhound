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
- **Multi-language support** - Python, Java, C#, TypeScript, JavaScript, and Markdown

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

1. **Scan** - ChunkHound reads your Python, Java, C#, TypeScript, JavaScript, and Markdown files
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
- "Find TypeScript interfaces and their implementations"
- "Show me JavaScript async functions"
- "Find React components in TypeScript"

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

- **Startup Time**: ~0.6 seconds (onedir distribution, 16x faster than old single-file)
- **Size**: ~97MB directory distribution
- **Dependencies**: None (fully self-contained)
- **Platforms**: macOS, Linux (Windows coming soon)

```bash
# Download and extract (example for Linux)
wget https://github.com/chunkhound/chunkhound/releases/latest/chunkhound-ubuntu.tar.gz
tar -xzf chunkhound-ubuntu.tar.gz
cd chunkhound-ubuntu
./chunkhound --help

# For macOS
wget https://github.com/chunkhound/chunkhound/releases/latest/chunkhound-macos.tar.gz
tar -xzf chunkhound-macos.tar.gz
cd chunkhound-macos
./chunkhound --help
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

## Installation Verification

Verify your ChunkHound installation is working correctly:

```bash
# Check version and startup performance
time chunkhound --version
# Expected: chunkhound 1.1.0 in ~0.3 seconds

# Test basic functionality
chunkhound --help

# Quick functionality test (optional)
mkdir test-chunkhound
cd test-chunkhound
echo "def hello(): pass" > test.py
chunkhound run . --no-embeddings --initial-scan-only
# Should index the test file successfully

# Test MCP server (Ctrl+C to exit)
chunkhound mcp --verbose
```

**Expected Results:**
- Version command: ~0.3s startup time
- Help displays all commands (run, mcp, config)
- Test indexing completes without errors
- MCP server starts and shows "Server ready" message

## Language Support

ChunkHound provides comprehensive parsing and indexing with **tree-sitter** for accurate syntax analysis:

### Supported Languages

| Language | Extensions | Extracted Elements | Status |
|----------|------------|-------------------|---------|
| **Python** | `.py` | Functions, classes, methods, decorators, async functions | ✅ Full |
| **Java** | `.java` | Classes, methods, interfaces, packages, constructors | ✅ Full |
| **C#** | `.cs` | Classes, methods, interfaces, namespaces, properties, events | ✅ Full |
| **TypeScript** | `.ts`, `.tsx` | Functions, classes, interfaces, types, enums, React components | ✅ Full |
| **JavaScript** | `.js`, `.jsx`, `.mjs`, `.cjs` | Functions, classes, modules, React components, arrow functions | ✅ Full |
| **Markdown** | `.md` | Headers, code blocks, structured content, documentation | ✅ Full |

### Advanced Features

- **Tree-sitter parsing** - Accurate syntax analysis with proper AST generation
- **Incremental parsing** - Only reparse changed files for fast updates
- **Symbol extraction** - Precise code structure with scope and context
- **Cross-language search** - Find patterns across all supported file types
- **React/JSX support** - Full component and hook extraction
- **Async/await patterns** - Modern JavaScript and Python async code
- **Generics support** - TypeScript and C# generic type extraction

## Examples

See the [examples/](examples/) directory for sample code demonstrating multi-language support features.

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

**Python CLI slow startup?**
- Expected performance: ~0.3s startup (90% improvement from original 2.7s)
- If slower than 0.5s, try: `pip install --upgrade chunkhound`
- Verify with: `time chunkhound --version`

**Semantic search not working?**
- Set your `OPENAI_API_KEY` environment variable
- Or configure a local embedding server (see docs/CLI_GUIDE.md)

**"You must provide a model parameter" error?**
- Update to latest version: `pip install --upgrade chunkhound`
- Or specify model explicitly: `chunkhound run . --model text-embedding-3-small`

**Database errors?**
- Delete `.chunkhound.db` and re-run `chunkhound run .`

**Performance Issues?**
- Python CLI: ~0.3s startup (excellent performance)
- Binary CLI: ~0.6s startup (onedir distribution)
- If performance is poor, ensure you have the latest version

## License

MIT
