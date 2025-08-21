<p align="center">
  <a href="https://ofriw.github.io/chunkhound">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/public/wordmark-github-dark.svg">
      <img src="docs/public/wordmark-centered.svg" alt="ChunkHound" width="400">
    </picture>
  </a>
</p>

<p align="center">
  <strong>Modern RAG for your codebase - semantic and regex search via MCP.</strong>
</p>

<p align="center">
  <a href="https://github.com/ofriw/chunkhound/actions/workflows/smoke-tests.yml">
    <img src="https://github.com/ofriw/chunkhound/actions/workflows/smoke-tests.yml/badge.svg" alt="Tests">
  </a>
</p>

Transform your codebase into a searchable knowledge base for AI assistants using semantic and regex search.

## Features

- **Semantic search** - Natural language queries like "find authentication code"
- **Regex search** - Pattern matching without API keys
- **Local-first** - Your code stays on your machine
- **20+ languages** - Python, TypeScript, Java, C++, Go, Rust, and more
- **MCP integration** - Works with Claude, VS Code, Cursor, Windsurf, Zed, etc

## Documentation

**Visit [ofriw.github.io/chunkhound](https://ofriw.github.io/chunkhound) for complete guides:**
- [Tutorial](https://ofriw.github.io/chunkhound/tutorial/)
- [Configuration Guide](https://ofriw.github.io/chunkhound/configuration/)
- [Architecture Deep Dive](https://ofriw.github.io/chunkhound/under-the-hood/)

## Installation

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ChunkHound
uv tool install chunkhound
```

## Quick Start

```bash
# Index your codebase
chunkhound index

# Start MCP server for AI assistants
chunkhound mcp
```

**For configuration, IDE setup, and advanced usage, see the [documentation](https://ofriw.github.io/chunkhound).**

## IDE Setup

ChunkHound works with Claude Desktop, Claude Code, VS Code, Cursor, Windsurf, Zed, and IntelliJ IDEA.

**See the [configuration guide](https://ofriw.github.io/chunkhound/configuration/) for setup instructions.**

## Requirements

- Python 3.10+
- [uv package manager](https://docs.astral.sh/uv/)
- API key for semantic search (optional - regex search works without any keys)

## License

MIT
