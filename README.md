<p align="center">
  <a href="https://chunkhound.github.io">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="public/wordmark-centered-dark.svg">
      <img src="public/wordmark-centered.svg" alt="ChunkHound" width="400">
    </picture>
  </a>
</p>

<p align="center">
  <strong>Modern RAG for your codebase - semantic and regex search via MCP.</strong>
</p>

<p align="center">
  <a href="https://github.com/chunkhound/chunkhound/actions/workflows/smoke-tests.yml"><img src="https://github.com/chunkhound/chunkhound/actions/workflows/smoke-tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/100%25%20AI-Generated-ff69b4.svg" alt="100% AI Generated">
  <a href="https://discord.gg/BAepHEXXnX"><img src="https://img.shields.io/badge/Discord-Join_Community-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
</p>

Transform your codebase into a searchable knowledge base for AI assistants using [semantic search via cAST algorithm](https://arxiv.org/pdf/2506.15655) and regex search. Integrates with AI assistants via the [Model Context Protocol (MCP)](https://spec.modelcontextprotocol.io/).

## Features

- **[cAST Algorithm](https://arxiv.org/pdf/2506.15655)** - Research-backed semantic code chunking
- **[Multi-Hop Semantic Search](https://chunkhound.github.io/under-the-hood/#multi-hop-semantic-search)** - Discovers interconnected code relationships beyond direct matches
- **Semantic search** - Natural language queries like "find authentication code"
- **Regex search** - Pattern matching without API keys
- **Local-first** - Your code stays on your machine
- **22 languages** with structured parsing
  - **Programming** (via [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)): Python, JavaScript, TypeScript, JSX, TSX, Java, Kotlin, Groovy, C, C++, C#, Go, Rust, Bash, MATLAB, Makefile
  - **Configuration** (via Tree-sitter): JSON, YAML, TOML, Markdown
  - **Text-based** (custom parsers): Text files, PDF
- **[MCP integration](https://spec.modelcontextprotocol.io/)** - Works with Claude, VS Code, Cursor, Windsurf, Zed, etc

## Documentation

**Visit [chunkhound.github.io](https://chunkhound.github.io) for complete guides:**
- [Tutorial](https://chunkhound.github.io/tutorial/)
- [Configuration Guide](https://chunkhound.github.io/configuration/)
- [Architecture Deep Dive](https://chunkhound.github.io/under-the-hood/)

## Requirements

- Python 3.10+
- [uv package manager](https://docs.astral.sh/uv/)
- API key for semantic search (optional - regex search works without any keys)
  - [OpenAI](https://platform.openai.com/api-keys) | [VoyageAI](https://dash.voyageai.com/) | [Local with Ollama](https://ollama.ai/)

## Installation

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ChunkHound
uv tool install chunkhound
```

## Quick Start

### Option 1: With Embeddings (Recommended)


1. Create `.chunkhound.json` in project root file
```json
{
  "embedding": {
    "provider": "openai",
    "api_key": "your-api-key-here"
  }
}
```
2. Index your codebase
```bash
chunkhound index
```

### Option 2: Without embeddings (regex search only)
```bash
chunkhound index --no-embeddings
```

**For configuration, IDE setup, and advanced usage, see the [documentation](https://chunkhound.github.io).**

## Real-Time Indexing

**Automatic File Watching**: MCP servers monitor your codebase and update the index automatically as you edit files. No manual re-indexing required.

**Smart Content Diffs**: Only changed code chunks get re-processed. Unchanged chunks keep their existing embeddings, making updates efficient even for large codebases.

**Seamless Branch Switching**: When you switch git branches, ChunkHound automatically detects and re-indexes only the files that actually changed between branches.

**Live Memory Systems**: Index markdown notes or documentation that updates in real-time while you work, creating a dynamic knowledge base.

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
- Structured parsing for 22 languages (Tree-sitter + custom parsers)
- Same semantic concepts across all programming languages

**Intelligent Code Discovery**:
- Multi-hop search follows semantic relationships to find related implementations
- Automatically discovers complete feature patterns: find "authentication" to get password hashing, token validation, session management
- Convergence detection prevents semantic drift while maximizing discovery

## License

MIT
