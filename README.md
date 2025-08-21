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
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  </a>
  <img src="https://img.shields.io/badge/100%25%20AI-Generated-ff69b4.svg" alt="100% AI Generated">
</p>

Transform your codebase into a searchable knowledge base for AI assistants using [semantic search via cAST algorithm](https://arxiv.org/pdf/2506.15655) and regex search. Integrates with AI assistants via the [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/).

## Features

- **[cAST Algorithm](https://arxiv.org/pdf/2506.15655)** - Research-backed semantic code chunking
- **Semantic search** - Natural language queries like "find authentication code"
- **Regex search** - Pattern matching without API keys
- **Local-first** - Your code stays on your machine
- **[20+ languages](https://tree-sitter.github.io/tree-sitter/)** - Python, TypeScript, Java, C++, Go, Rust, and more
- **[MCP integration](https://spec.modelcontextprotocol.io/)** - Works with Claude, VS Code, Cursor, Windsurf, Zed, etc

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

ChunkHound works with any AI assistant that supports [MCP (Model Context Protocol)](https://spec.modelcontextprotocol.io/):

- **[Claude Desktop](https://claude.ai/)** - Add to `~/.claude.json` MCP servers
- **[Claude Code](https://docs.anthropic.com/claude/docs/claude-code)** - Built-in MCP support
- **[VS Code](https://marketplace.visualstudio.com/)** - MCP extensions available
- **[Cursor](https://cursor.com/)** - MCP configuration in `.cursor/mcp.json`
- **[Windsurf](https://codeium.com/windsurf)** - MCP server support
- **[Zed](https://zed.dev/)** - MCP integration

**See the [configuration guide](https://ofriw.github.io/chunkhound/configuration/) for detailed setup instructions.**

## Requirements

- Python 3.10+
- [uv package manager](https://docs.astral.sh/uv/)
- API key for semantic search (optional - regex search works without any keys)
  - [OpenAI](https://platform.openai.com/api-keys) | [VoyageAI](https://dash.voyageai.com/) | [Local with Ollama](https://ollama.ai/)

## Why ChunkHound?

**Research Foundation**: Built on the [cAST (Chunking via Abstract Syntax Trees)](https://arxiv.org/pdf/2506.15655) algorithm from Carnegie Mellon University, providing:
- **4.3 point gain** in Recall@5 on RepoEval retrieval
- **2.67 point gain** in Pass@1 on SWE-bench generation
- **Structure-aware chunking** that preserves code meaning

**Local-First Architecture**:
- Your code never leaves your machine
- Works offline with [Ollama](https://ollama.ai/) local models
- No per-token charges for large codebases

**Universal Language Support**:
- Powered by [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for 20+ languages
- Same semantic concepts across all programming languages

## License

MIT
