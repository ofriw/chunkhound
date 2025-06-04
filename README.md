# ChunkHound

Local code search with regex and AI-powered semantic search.

## Install

```bash
git clone https://github.com/yourusername/chunkhound.git
cd chunkhound
pip install -e .
```

## Quick Start

```bash
# Index your code
chunkhound run .

# Start search server
chunkhound server

# Search for functions
curl "http://localhost:7474/search/regex?pattern=def.*test"

# Get stats
curl http://localhost:7474/stats
```

## With AI Search

```bash
# Set OpenAI API key
export OPENAI_API_KEY=your-key-here

# Index with embeddings
chunkhound run .

# Semantic search
curl -X POST http://localhost:7474/search/semantic \
  -d '{"query": "database connection"}'
```

## CLI Options

```bash
chunkhound run /path/to/code              # Index directory
chunkhound run . --exclude "*/tests/*"   # Skip directories
chunkhound run . --verbose               # Detailed output
chunkhound server --port 8080            # Custom port
```

## API Endpoints

- `GET /health` - Health check
- `GET /stats` - Database statistics
- `GET /search/regex?pattern=...` - Regex search
- `POST /search/semantic` - AI search (requires OpenAI key)

## Troubleshooting

**Command not found**: Run `pip install -e .` again

**Database errors**: Delete `~/.cache/chunkhound/chunks.duckdb` and re-run

**No OpenAI key**: Regex search works without it

Works on Mac and Linux. Python 3.8+ required.