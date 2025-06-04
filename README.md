# ChunkHound

**Local code search with regex and AI-powered semantic search.**

Dead simple to use. Dead simple to develop.

## Quick Start

### For Users

```bash
pip install chunkhound
chunkhound run .
```

That's it! ChunkHound will:
- Index your code 
- Start a search server at `http://localhost:7474`
- Watch for file changes and update automatically

### Search Your Code

```bash
# Regex search
curl "http://localhost:7474/search/regex?pattern=def.*test"

# AI semantic search (requires OpenAI API key)
export OPENAI_API_KEY=your-key-here
curl -X POST http://localhost:7474/search/semantic -d '{"query": "database connection"}'

# Check stats
curl http://localhost:7474/stats
```

## Real Example: Index ChunkHound's Own Codebase

Here's how ChunkHound indexes and searches its own code:

```bash
# Clone and setup ChunkHound
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
pip install .

# Index the codebase (excludes venv, tests, etc. automatically)
chunkhound run . --verbose

# The server starts automatically at http://localhost:7474
# In another terminal, search the code:

# Find all database operations
curl "http://localhost:7474/search/regex?pattern=def.*database"

# Find embedding-related functions  
curl "http://localhost:7474/search/regex?pattern=embedding"

# Search for CLI command handling
curl "http://localhost:7474/search/regex?pattern=def.*command"

# With OpenAI API key, try semantic search:
export OPENAI_API_KEY=your-key-here
curl -X POST http://localhost:7474/search/semantic -d '{"query": "parse Python code"}'
curl -X POST http://localhost:7474/search/semantic -d '{"query": "vector similarity search"}'

# Check what was indexed
curl http://localhost:7474/stats
# Response: {"files": 1342, "chunks": 23991, "embeddings": 0}
```

**What gets indexed:**
- 🐍 **Python files**: Functions, classes, methods from `chunkhound/`
- 📊 **Statistics**: ~1,300 files, ~24,000 code chunks  
- 🔍 **Searchable**: Function definitions, class structures, imports
- ⚡ **Fast**: Regex search returns results instantly
- 🧠 **Smart**: Semantic search finds conceptually related code

**Try these searches on ChunkHound's code:**
- `"def connect"` - Find database connection logic
- `"class.*Parser"` - Find parser classes
- `"async def"` - Find async functions
- `"import.*tree_sitter"` - Find tree-sitter usage

**Example Search Results:**

```bash
# Search for database functions
curl "http://localhost:7474/search/regex?pattern=def.*database&limit=3"
```

```json
{"chunk_id": 1, "symbol": "Database.__init__", "start_line": 16, "end_line": 22, "code": "def __init__(self, db_path: Path, embedding_manager: Optional[EmbeddingManager] = None):", "chunk_type": "function", "file_path": "chunkhound/database.py", "language": "python"}
{"chunk_id": 2, "symbol": "Database.connect", "start_line": 28, "end_line": 52, "code": "def connect(self) -> None:", "chunk_type": "function", "file_path": "chunkhound/database.py", "language": "python"}
{"chunk_id": 3, "symbol": "Database.close", "start_line": 797, "end_line": 801, "code": "def close(self) -> None:", "chunk_type": "function", "file_path": "chunkhound/database.py", "language": "python"}
```

```bash
# Semantic search for parsing logic
curl -X POST http://localhost:7474/search/semantic -d '{"query": "extract code symbols", "limit": 3}'
```

```json
{"chunk_id": 15, "symbol": "CodeParser._extract_functions", "start_line": 82, "end_line": 123, "code": "def _extract_functions(self, tree_node: Node, source_code: str) -> List[Dict[str, Any]]:", "chunk_type": "function", "file_path": "chunkhound/parser.py", "language": "python", "distance": 0.11}
{"chunk_id": 28, "symbol": "CodeParser._extract_classes", "start_line": 124, "end_line": 170, "code": "def _extract_classes(self, tree_node: Node, source_code: str) -> List[Dict[str, Any]]:", "chunk_type": "function", "file_path": "chunkhound/parser.py", "language": "python", "distance": 0.14}
{"chunk_id": 42, "symbol": "Chunker.chunk_file", "start_line": 45, "end_line": 78, "code": "def chunk_file(self, file_path: Path) -> List[Dict[str, Any]]:", "chunk_type": "function", "file_path": "chunkhound/chunker.py", "language": "python", "distance": 0.17}
```

**Response Format:**
- All search results return **NDJSON** (newline-delimited JSON)
- Each line is a complete JSON object
- Perfect for streaming and processing by coding agents
- Use `jq` to parse: `curl ... | jq '.'` or process line-by-line in scripts

**Parsing Examples:**

```bash
# Pretty print results with jq
curl -s "http://localhost:7474/search/regex?pattern=def.*test" | jq '.'

# Extract just function names
curl -s "http://localhost:7474/search/regex?pattern=class" | jq -r '.symbol'

# Filter by file type
curl -s "http://localhost:7474/search/regex?pattern=async" | jq 'select(.file_path | contains("api"))'

# Count results
curl -s "http://localhost:7474/search/regex?pattern=def" | wc -l
```

```python
# Python script to process results
import requests
import json

response = requests.get("http://localhost:7474/search/regex", 
                       params={"pattern": "class.*Parser", "limit": 5})

for line in response.text.strip().split('\n'):
    if line:
        result = json.loads(line)
        print(f"{result['symbol']} in {result['file_path']}:{result['start_line']}")
```

**Advanced Indexing Options:**

```bash
# Index only specific directories
chunkhound run . --include "chunkhound/**/*.py" --exclude "tests/*"

# Skip embeddings for faster indexing (regex search only)
chunkhound run . --no-embeddings

# Custom database location
chunkhound run . --db ./my-code-search.duckdb

# Verbose output to see what's being processed
chunkhound run . --verbose --exclude "venv/*" --exclude "__pycache__/*"

# Index multiple patterns
chunkhound run . --include "*.py" --include "*.js" --include "*.ts"
```

## For Developers

### One-Command Setup

```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
./scripts/setup.sh
```

Or use Make:

```bash
make setup  # One-time setup
make dev    # Start development server
make test   # Run tests
make help   # See all commands
```

### Development Commands

| Command | Description |
|---------|-------------|
| `make setup` | One-time development setup |
| `make dev` | Start development server with file watching |
| `make test` | Run all tests |
| `make lint` | Check code quality |
| `make format` | Format code |
| `make clean` | Clean temporary files |

## CLI Options

```bash
chunkhound run /path/to/code              # Index directory
chunkhound run . --exclude "*/tests/*"   # Skip directories  
chunkhound run . --verbose               # Detailed output
chunkhound run . --no-embeddings        # Skip AI features
chunkhound server --port 8080            # Custom port
```

## API Endpoints

- `GET /health` - Health check
- `GET /stats` - Database statistics  
- `GET /search/regex?pattern=...` - Regex search
- `POST /search/semantic` - AI search (requires OpenAI key)

## Installation Methods

### Method 1: pip (Recommended)
```bash
pip install chunkhound
```

### Method 2: From source
```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
pip install .
```

### Method 3: Development mode
```bash
git clone https://github.com/chunkhound/chunkhound.git
cd chunkhound
pip install -e ".[dev]"
```

## AI Features (Optional)

ChunkHound works great without AI, but for semantic search:

```bash
export OPENAI_API_KEY=your-key-here
chunkhound run .
```

## Requirements

- Python 3.8+
- Works on Mac and Linux
- Optional: OpenAI API key for semantic search

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Command not found | Use `python -m chunkhound.cli` |
| Database errors | Delete `~/.cache/chunkhound/` and re-run |
| Import errors | Run `pip install -e .` in project directory |
| Port in use | Use `--port 8080` to change port |

Run `make health` to check system status.

## Architecture

- **Database**: DuckDB with vector search (VSS extension)
- **Parsing**: Tree-sitter for Python AST extraction
- **Embeddings**: OpenAI text-embedding-3-small
- **API**: FastAPI with async support
- **Search**: Combined regex + vector similarity

## Contributing

1. Fork and clone
2. Run `./scripts/setup.sh` 
3. Make changes
4. Run `make check` (lint + test)
5. Submit PR

## License

MIT License. See LICENSE file.