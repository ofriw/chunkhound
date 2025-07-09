# ChunkHound

**Modern RAG for your codebase - semantic and regex search via MCP.**

Transform your codebase into a searchable knowledge base. ChunkHound provides AI assistants with intelligent code search capabilities using natural language and regex patterns.

## Installation

### 🤖 AI Agent Installation (For Humans - Recommended)

The easiest way to install and configure ChunkHound is to use your AI assistant. Simply copy and paste this prompt:

```
- Check the current OS type and version.
- Detect what IDE and agent versions are you running in.
- Read https://raw.githubusercontent.com/ofriw/chunkhound/refs/heads/main/README.md
- Install ChunkHound using uv and configure it for the current IDE and agent
  - Upgrade chunkhound if already installed
- Edit the current IDE / agent's config files to configure chunkhound as an MCP server. See instructions in the README

Start by asking the user:
1. What embeddings provider would they like to use? Suggest from the list of supported providers. Clearly articulate defaults.
2. Based on the user's response, ask for the relevant configuration parameters. Use defaults if user hasn't decided.
3. Ask clarifying questions if unsure.

Proceed with the configuration based on the user's input.
```

Your AI assistant will automatically detect your environment, install ChunkHound, and configure it for your specific IDE and embedding provider preferences.

**Install ChunkHound**:
```bash
uv tool install chunkhound
```

> **Need uv?** ChunkHound requires [uv](https://github.com/astral-sh/uv): `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Quick Start

```bash
# 1. Index your codebase (creates .chunkhound.db)
uv run chunkhound index
# ChunkHound automatically detects and uses .chunkhound.json in the current directory

# 2. Start MCP server for AI assistants (auto-watches for changes)
uv run chunkhound mcp

# Work with any project directory - complete project scope control
uv run chunkhound mcp /path/to/your/project
# This sets database to /path/to/your/project/.chunkhound/db
# Searches for config at /path/to/your/project/.chunkhound.json
# Watches /path/to/your/project for changes

# Optional: Set OpenAI API key for semantic search
export CHUNKHOUND_EMBEDDING__API_KEY="sk-your-key-here"

# Optional: Override with a different config file
uv run chunkhound index --config /path/to/different-config.json
```

### Automatic Configuration Detection

ChunkHound automatically detects and uses project configurations:

**For `index` command:**
```bash
cd /my/project              # Has .chunkhound.json
uv run chunkhound index     # Automatically uses /my/project/.chunkhound.json
```

**For `mcp` command with positional path:**
```bash
uv run chunkhound mcp /my/project
# Automatically uses /my/project/.chunkhound.json
# Sets database to /my/project/.chunkhound/db
# Watches /my/project for changes
```

**For `mcp` command without path:**
```bash
cd /my/project              # Has .chunkhound.json
uv run chunkhound mcp       # Automatically uses /my/project/.chunkhound.json
```

## Features

**Always Available:**
- **Regex search** - Find exact patterns like `class.*Error` (no API key needed)
- **Code context** - AI assistants understand your codebase structure
- **Multi-language** - 20+ languages supported
- **Real-time updates** - Automatically watches for file changes

**With API Key:**
- **Semantic search** - Natural language queries like "find database connection code"

## AI Assistant Setup

ChunkHound integrates with all major AI development tools. Add these minimal configurations:

<details>
<summary><strong>Configuration for Each IDE/Tool</strong></summary>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"]
    }
  }
}
```

**For specific project directories:**
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
    }
  }
}
```
</details>

<details>
<summary><strong>Claude Code</strong></summary>

Add to `~/.claude.json`:
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"]
    }
  }
}
```

**For specific project directories:**
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
    }
  }
}
```
</details>

<details>
<summary><strong>VS Code</strong></summary>

Add to `.vscode/mcp.json` in your project:
```json
{
  "servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"]
    }
  }
}
```

**For specific project directories:**
```json
{
  "servers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
    }
  }
}
```
</details>

<details>
<summary><strong>Cursor</strong></summary>

Add to `.cursor/mcp.json` in your project:
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"]
    }
  }
}
```

**For specific project directories:**
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
    }
  }
}
```
</details>

<details>
<summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp"]
    }
  }
}
```

**For specific project directories:**
```json
{
  "mcpServers": {
    "chunkhound": {
      "command": "uv",
      "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
    }
  }
}
```
</details>

<details>
<summary><strong>Zed</strong></summary>

Add to settings.json (Preferences > Open Settings):
```json
{
  "context_servers": {
    "chunkhound": {
      "source": "custom",
      "command": {
        "path": "uv",
        "args": ["run", "chunkhound", "mcp"]
      }
    }
  }
}
```

**For specific project directories:**
```json
{
  "context_servers": {
    "chunkhound": {
      "source": "custom",
      "command": {
        "path": "uv",
        "args": ["run", "chunkhound", "mcp", "/path/to/your/project"]
      }
    }
  }
}
```
</details>

<details>
<summary><strong>IntelliJ IDEA / PyCharm / WebStorm</strong> (2025.1+)</summary>

Go to Settings > Tools > AI Assistant > Model Context Protocol (MCP) and add:
- **Name**: chunkhound
- **Command**: uv
- **Arguments**: run chunkhound mcp
- **Working Directory**: (leave empty or set to project root)

**For specific project directories:**
- **Name**: chunkhound
- **Command**: uv
- **Arguments**: run chunkhound mcp /path/to/your/project
- **Working Directory**: (leave empty)
</details>

</details>




## Supported Languages

Python, Java, C#, TypeScript, JavaScript, Groovy, Kotlin, Go, Rust, C, C++, Matlab, Bash, Makefile, Markdown, JSON, YAML, TOML, and more.


## Configuration

### Automatic Configuration Detection

**ChunkHound automatically looks for `.chunkhound.json` in the directory being indexed - no flags needed!**

```bash
# If /my/project/.chunkhound.json exists:
cd /my/project
uv run chunkhound index    # Automatically uses .chunkhound.json
```

### Configuration Priority

ChunkHound loads configuration in this order (highest priority first):
1. **Command-line arguments** - Override everything
2. **`.chunkhound.json` in indexed directory** - Automatically detected
3. **`--config` file** - When explicitly specified
4. **Environment variables** - System-wide defaults
5. **Built-in defaults** - Fallback values

### Database Location

ChunkHound automatically determines the database location based on project scope:

**With positional path argument:**
```bash
uv run chunkhound mcp /my/project
# Database automatically created at: /my/project/.chunkhound/db
```

**Without positional path (current directory):**
```bash
cd /my/project
uv run chunkhound mcp
# Database created at: /my/project/.chunkhound/db
```

**Manual overrides** (in priority order):
- **Command line**: `--database-path /path/to/my-chunks`
- **Config file**: Add to `.chunkhound.json`: `{"database": {"path": "/path/to/.chunkhound.db"}}`
- **Environment variable**: `CHUNKHOUND_DATABASE__PATH="/path/to/.chunkhound.db"`

### Configuration File Format

Create `.chunkhound.json` in your project root for automatic loading:
```json
{
  "embedding": {
    "provider": "openai",
    "api_key": "sk-your-openai-key-here",
    "model": "text-embedding-3-small",
    "batch_size": 50,
    "timeout": 30,
    "max_retries": 3,
    "max_concurrent_batches": 3
  },
  "database": {
    "path": ".chunkhound.db",
    "provider": "duckdb"
  },
  "indexing": {
    "watch": true,
    "debounce_ms": 500,
    "batch_size": 100,
    "db_batch_size": 500,
    "max_concurrent": 4,
    "include_patterns": [
      "**/*.py",
      "**/*.ts",
      "**/*.jsx"
    ],
    "exclude_patterns": [
      "**/node_modules/**",
      "**/__pycache__/**",
      "**/dist/**"
    ]
  },
  "mcp": {
    "transport": "stdio"
  },
  "debug": false
}
```

### Working with `.chunkhound.json`

**Example 1: Project with OpenAI embeddings**
```bash
# Create .chunkhound.json in your project
echo '{
  "embedding": {
    "provider": "openai",
    "api_key": "sk-your-key-here"
  }
}' > .chunkhound.json

# Index - automatically uses .chunkhound.json
uv run chunkhound index
```

**Example 2: Project with local Ollama**
```bash
# Create .chunkhound.json for Ollama
echo '{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "http://localhost:11434",
    "model": "nomic-embed-text"
  }
}' > .chunkhound.json

# Index - automatically uses .chunkhound.json
uv run chunkhound index
```

**Provider-Specific Examples**:

OpenAI-compatible (Ollama, LocalAI):
```json
{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "http://localhost:11434",
    "model": "nomic-embed-text",
    "api_key": "optional-api-key"
  }
}
```

Text Embeddings Inference (TEI):
```json
{
  "embedding": {
    "provider": "tei",
    "base_url": "http://localhost:8080"
  }
}
```

BGE-IN-ICL:
```json
{
  "embedding": {
    "provider": "bge-in-icl",
    "base_url": "http://localhost:8080",
    "language": "python",
    "enable_icl": true
  }
}
```

**Security Note**: 
- API keys in config files are convenient for local development
- Add `.chunkhound.json` to `.gitignore` to prevent committing API keys:

```gitignore
# ChunkHound config files
.chunkhound.json
*.chunkhound.json
chunkhound.json
```

**Configuration Options**:

- **`embedding`**: Embedding provider settings
  - `provider`: Choose from `openai`, `openai-compatible`, `tei`, `bge-in-icl`
  - `model`: Model name (uses provider default if not specified)
  - `api_key`: API key for authentication
  - `base_url`: Base URL for API (for local/custom providers)
  - `batch_size`: Number of texts to embed at once (1-1000)
  - `timeout`: Request timeout in seconds
  - `max_retries`: Retry attempts for failed requests
  - `max_concurrent_batches`: Concurrent embedding batches

- **`database`**: Database settings
  - `path`: Database file location (relative or absolute)
  - `provider`: Database type (`duckdb` or `lancedb`)

- **`indexing`**: File indexing behavior
  - `watch`: Enable file watching in standalone mode
  - `debounce_ms`: Delay before processing file changes
  - `batch_size`: Files to process per batch
  - `db_batch_size`: Database records per transaction
  - `max_concurrent`: Parallel file processing limit
  - `include_patterns`: Glob patterns for files to index
  - `exclude_patterns`: Glob patterns to ignore

- **`debug`**: Enable debug logging

**Security Note**: Never commit API keys to version control. Use environment variables or `.chunkhound.json` (added to .gitignore):
```bash
# Option 1: Environment variable
export CHUNKHOUND_EMBEDDING__API_KEY="sk-your-key-here"

# Option 2: .chunkhound.json (automatically detected)
echo '{"embedding": {"api_key": "sk-your-key-here"}}' > .chunkhound.json
echo ".chunkhound.json" >> .gitignore
```

### Embedding Providers

ChunkHound supports multiple embedding providers for semantic search:

**OpenAI (requires API key)**:
```bash
# Option 1: Use .chunkhound.json (automatically detected)
echo '{
  "embedding": {
    "provider": "openai",
    "api_key": "sk-your-key-here",
    "model": "text-embedding-3-small"
  }
}' > .chunkhound.json
uv run chunkhound index

# Option 2: Use environment variable
export CHUNKHOUND_EMBEDDING__API_KEY="sk-your-key-here"
uv run chunkhound index --provider openai --model text-embedding-3-small
```

**Local embedding servers (no API key required)**:

**Ollama**:
```bash
# First, start Ollama with an embedding model
ollama pull nomic-embed-text

# Option 1: Use .chunkhound.json (automatically detected)
echo '{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "http://localhost:11434",
    "model": "nomic-embed-text"
  }
}' > .chunkhound.json
uv run chunkhound index

# Option 2: Use command line
uv run chunkhound index --provider openai-compatible --base-url http://localhost:11434 --model nomic-embed-text
```

**LocalAI, LM Studio, or other OpenAI-compatible servers**:
```bash
# Create .chunkhound.json for automatic detection
echo '{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "http://localhost:1234",
    "model": "your-embedding-model"
  }
}' > .chunkhound.json
uv run chunkhound index

# Or use command line
uv run chunkhound index --provider openai-compatible --base-url http://localhost:1234 --model your-embedding-model
```

**Text Embeddings Inference (TEI)**:
```bash
# Create .chunkhound.json for automatic detection
echo '{
  "embedding": {
    "provider": "tei",
    "base_url": "http://localhost:8080"
  }
}' > .chunkhound.json
uv run chunkhound index

# Or use command line
uv run chunkhound index --provider tei --base-url http://localhost:8080
```

**Regex-only mode (no embeddings)**:
```bash
# Skip embedding setup entirely - only regex search will be available
uv run chunkhound index --no-embeddings
```

### Environment Variables

Environment variables are useful for system-wide defaults, but `.chunkhound.json` in your project directory will take precedence:

```bash
# For OpenAI semantic search only
export CHUNKHOUND_EMBEDDING__API_KEY="sk-your-key-here"

# For local embedding servers (Ollama, LocalAI, etc.)
export CHUNKHOUND_EMBEDDING__PROVIDER="openai-compatible"
export CHUNKHOUND_EMBEDDING__BASE_URL="http://localhost:11434"  # Ollama default
export CHUNKHOUND_EMBEDDING__MODEL="nomic-embed-text"

# Optional: Database location
export CHUNKHOUND_DATABASE__PATH="/path/to/.chunkhound.db"

# Note: .chunkhound.json in your project will override these settings
```

## Security

ChunkHound prioritizes data security through a local-first architecture:

- **Local database**: All code chunks stored in local DuckDB file - no data sent to external servers
- **Local embeddings**: Supports self-hosted embedding servers (Ollama, LocalAI, TEI) for complete data isolation
- **MCP over stdio**: Uses standard input/output for AI assistant communication - no network exposure
- **No authentication complexity**: Zero auth required since everything runs locally on your machine

Your code never leaves your environment unless you explicitly configure external embedding providers.

## Requirements

- **Python**: 3.10+
- **API Key**: Only required for semantic search - **regex search works without any API key**
  - **OpenAI API key**: For OpenAI semantic search
  - **No API key needed**: For local embedding servers (Ollama, LocalAI, TEI) or regex-only usage

## How It Works

ChunkHound indexes your codebase in three layers:
1. **Pre-index** - Run `chunkhound index` to sync database with current code (automatically uses `.chunkhound.json` if present)
2. **Background scan** - MCP server checks for changes every 5 minutes  
3. **Real-time updates** - File system events trigger immediate updates

**Project Scope Control:**
- `chunkhound mcp` - Uses current directory as project root
- `chunkhound mcp /path/to/project` - Uses specified path as project root
- Database, config, and watch paths all scoped to project root

**Processing pipeline:**
Scan → Parse → Index → Embed → Search

## Performance

ChunkHound uses smart caching and prioritization:
- **Priority queue** - User queries > file changes > background scans
- **Change detection** - Only processes modified files
- **Efficient re-indexing** - Reuses existing embeddings for unchanged code

## Origin Story

**100% of ChunkHound's code was written by an AI agent - zero lines written by hand.**

A human envisioned the project and provided strategic direction, but every single line of code, the project name, documentation, and technical decisions were generated by language models. The human acted as product manager and architect, writing prompts and validating each step, while the AI agent served as compiler - transforming requirements into working code.

The entire codebase emerged through an iterative human-AI collaboration: design → code → test → review → commit. Remarkably, the agent performed its own QA and testing by using ChunkHound to search its own code, creating a self-improving feedback loop where the tool helped build itself.

## License

MIT
