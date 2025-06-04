# ChunkHound

Local-first semantic code search with vector and regex capabilities for coding agents.

## Overview

ChunkHound watches your codebase, extracts semantic units (functions, classes, methods), and stores them in a DuckDB database with vector embeddings for fast semantic search alongside traditional regex pattern matching.

## Features

- **Dual Search Capabilities**: Both semantic (vector) and regex search
- **Local-First**: No data leaves your machine, embedded DuckDB storage
- **Real-Time Updates**: File watching with incremental indexing
- **Coding Agent Optimized**: Structured API responses for programmatic access
- **Pluggable Embeddings**: Support for multiple embedding providers

## Tech Stack

- **Database**: DuckDB with vss extension for HNSW vector indexing
- **Parsing**: tree-sitter for reliable AST-based code extraction
- **Embeddings**: OpenAI text-embedding-3-small (configurable)
- **API**: FastAPI with NDJSON streaming responses
- **File Watching**: Rust-powered watchfiles for cross-platform monitoring

## Quick Start

```bash
# Set up development environment
cd chunkhound
python3 -m venv venv
source venv/bin/activate
pip install loguru click  # minimal dependencies for Phase 1

# Test the CLI
python -m chunkhound.cli --help
python -m chunkhound.cli run . --verbose

# Full installation (coming in later phases)
# pip install -e .
```

## API Endpoints

### Semantic Search
```bash
GET /search/semantic?q=authentication%20middleware&top_k=10
```

### Regex Search  
```bash
GET /search/regex?pattern=@app\.route.*&lang=python
```

## Configuration

Environment variables:
- `OPENAI_API_KEY`: Required for embeddings
- `CHUNKHOUND_DB_PATH`: Custom database location
- `CHUNKHOUND_LOG_LEVEL`: Logging verbosity

## Development Status

🚧 **Phase 1 POC** - Core infrastructure and parsing

### ✅ Task 1 Complete: Project Setup
- [x] Python package structure with pyproject.toml
- [x] Working CLI with argparse (`chunkhound run <path>`)
- [x] Argument validation and configuration
- [x] Logging setup with timestamps
- [x] File pattern inclusion/exclusion
- [x] Database path management

### 🔄 Next: Task 2 - Database Layer
- [ ] DuckDB connection with vss extension
- [ ] Schema creation (files, chunks, embeddings)
- [ ] HNSW index setup for vector search

### 🔄 Next: Task 3 - Code Parsing
- [ ] tree-sitter integration for Python
- [ ] Function and class extraction
- [ ] Chunk storage with metadata

**Current CLI Output:**
```
✅ Starting ChunkHound v0.1.0
✅ Watching directory: .
✅ Database: /Users/user/.cache/chunkhound/chunks.duckdb
✅ API server: http://127.0.0.1:7474
✅ Include patterns: ['*.py']
✅ Phase 1: Configuration validated.
```

## Performance Targets

- **Indexing**: 2k LOC/s throughput
- **Search**: <50ms p99 for vector queries
- **Updates**: File changes visible within 2s
- **Memory**: ~500MB for 100k code chunks

## License

MIT