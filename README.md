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
- Edit the current IDE / agent's config files to configure chunkhound as an MCP server. See instructions in the README
- Upgrade chunkhound if already installed

Start by asking the user:
1. What embeddings provider would they like to use? Suggest from the list of supported providers.
2. Based on the user's response, ask for the relevant configuration parameters
3. Proceed with the configuration based on the user's input
```

Your AI assistant will automatically detect your environment, install ChunkHound, and configure it for your specific IDE and embedding provider preferences.

### Installation

ChunkHound requires [uv](https://github.com/astral-sh/uv), an extremely fast Python package manager written in Rust. If you don't have uv installed:

**Install uv** (choose one method):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or using pip (if you have Python)
pip install uv
```

**What is uv?** It's a modern Python tool that replaces pip, virtualenv, and other Python development tools with a single, fast utility. It manages packages, Python versions, and project dependencies 10-100x faster than traditional tools.

**Install ChunkHound**:
```bash
uv tool install chunkhound
```

## Quick Start

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-your-key-here"

# Index your codebase first (creates .chunkhound.db in current directory)
uv run chunkhound index

# OR: Index and watch for changes (standalone mode)
uv run chunkhound index --watch

# Start MCP server for AI assistants (automatically watches for file changes)
uv run chunkhound mcp

# Use custom database location
uv run chunkhound index --db /path/to/my-chunks
uv run chunkhound mcp --db /path/to/my-chunks
```

## Usage Modes

ChunkHound works in two modes depending on your setup:

**🔍 Regex Search Only** (no API key needed):
- Works immediately after installation
- Search with exact patterns: `class.*Error`, `async def.*`
- Perfect for code structure analysis and precise matching

**🧠 Semantic + Regex Search** (requires embedding provider):
- Natural language queries: "find database connection code"
- Uses OpenAI API, or local servers like Ollama/LocalAI
- Includes all regex functionality plus AI-powered search

**Choose your preferred setup below** ⬇️

## AI Assistant Setup

ChunkHound integrates with all major AI development tools:

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
      "args": ["run", "chunkhound", "mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here"
      }
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
      "args": ["run", "chunkhound", "mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here"
      }
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
      "args": ["run", "chunkhound", "mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here"
      }
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
  "chunkhound": {
    "command": "uv",
    "args": ["run", "chunkhound", "mcp"],
    "env": {
      "OPENAI_API_KEY": "sk-your-key-here"
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
      "args": ["run", "chunkhound", "mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here"
      }
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
        "args": ["run", "chunkhound", "mcp"],
        "env": {
          "OPENAI_API_KEY": "sk-your-key-here"
        }
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
- **Environment Variables**: OPENAI_API_KEY=sk-your-key-here
- **Working Directory**: (leave empty or set to project root)
</details>

</details>



## What You Get

**Always Available:**
- **Regex search** - Find exact patterns like `async def.*error` (no API key needed)
- **Code context** - AI assistants understand your codebase structure  
- **Multi-language** - Python, TypeScript, Java, C#, JavaScript, Groovy, Kotlin, Go, Rust, C, C++, Matlab, Bash, Makefile, Markdown, JSON, YAML, TOML
- **Pagination** - Efficiently handle large result sets with smart pagination controls

**With Embedding Provider:**
- **Semantic search** - "Find database connection code" (requires OpenAI API or local server)

## Search Pagination

ChunkHound supports efficient pagination for both semantic and regex searches to handle large codebases:

- **Page size**: Control results per page (1-100, default: 10)
- **Offset**: Navigate through result pages starting from any position
- **Smart metadata**: Automatic `has_more` detection and `next_offset` calculation
- **Total counts**: Get complete result counts for accurate pagination
- **Token limiting**: Automatic response size optimization for MCP compatibility

Both search tools return results with pagination metadata:
```json
{
  "results": [...],
  "pagination": {
    "offset": 0,
    "page_size": 10,
    "has_more": true,
    "next_offset": 10,
    "total": 47
  }
}
```

## Language Support

| Language | Extensions | Extracted Elements |
|----------|------------|-------------------|
| **Python** | `.py` | Functions, classes, methods, async functions |
| **Java** | `.java` | Classes, methods, interfaces, constructors |
| **C#** | `.cs` | Classes, methods, interfaces, properties |
| **TypeScript** | `.ts`, `.tsx` | Functions, classes, interfaces, React components |
| **JavaScript** | `.js`, `.jsx` | Functions, classes, React components |
| **Groovy** | `.groovy`, `.gvy`, `.gy` | Classes, methods, closures, traits, enums, scripts |
| **Kotlin** | `.kt`, `.kts` | Classes, objects, functions, properties, data classes, extension functions |
| **Go** | `.go` | Functions, methods, structs, interfaces, type declarations, variables, constants |
| **Rust** | `.rs` | Functions, methods, structs, enums, traits, implementations, modules, macros, constants, statics, type aliases |
| **C** | `.c`, `.h` | Functions, structs, unions, enums, variables, typedefs, macros |
| **C++** | `.cpp`, `.cxx`, `.cc`, `.hpp`, `.hxx`, `.h++` | Classes, functions, namespaces, templates, enums, variables, type aliases, macros |
| **Matlab** | `.m` | Functions, classes, methods, scripts, nested functions |
| **Bash** | `.sh`, `.bash`, `.zsh` | Functions, control structures, complex commands |
| **Makefile** | `Makefile`, `makefile`, `GNUmakefile`, `.mk`, `.make` | Targets, rules, variables, recipes |
| **Markdown** | `.md`, `.markdown` | Headers, code blocks, documentation |
| **JSON** | `.json` | Structure and data elements |
| **YAML** | `.yaml`, `.yml` | Configuration and data elements |
| **TOML** | `.toml` | Tables, key-value pairs, arrays, inline tables |
| **Text** | `.txt` | Plain text content |

## Usage Modes

ChunkHound operates in two main modes:

1. **MCP Server Mode** (`chunkhound mcp`) - Recommended for AI assistants
   - Automatically watches for file changes
   - Responds to search queries via MCP protocol
   - Runs continuously in background

2. **Standalone Mode** (`chunkhound index`)
   - One-time indexing: `chunkhound index`
   - Continuous watching: `chunkhound index --watch`
   - Direct CLI usage without MCP integration

## Configuration

### Database Location

By default, ChunkHound creates `.chunkhound.db` in your current directory. You can customize this with:

- **Command line**: `--db /path/to/my-chunks`
- **Environment variable**: `CHUNKHOUND_DB_PATH="/path/to/.chunkhound.db"`

### Project Configuration File

ChunkHound supports project-level configuration through a `.chunkhound.json` file in your project root. This allows you to maintain consistent settings across your team and avoid repetitive command-line arguments.

**Configuration Hierarchy** (highest to lowest priority):
1. Command-line arguments
2. Environment variables
3. Project config file (`.chunkhound.json` in current directory)
4. User config file (`~/.chunkhound/config.json`)
5. Default values

**Example `.chunkhound.json`**:
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
- Environment variables (`CHUNKHOUND_EMBEDDING__API_KEY`) always override config files
- Add `.chunkhound.json` to `.gitignore` to prevent committing API keys:

```gitignore
# ChunkHound config with API keys
.chunkhound.json
```

**Configuration Options**:

- **`embedding`**: Embedding provider settings
  - `provider`: Choose from `openai`, `openai-compatible`, `tei`, `bge-in-icl`
  - `model`: Model name (uses provider default if not specified)
  - `api_key`: API key for authentication (can be stored in config file)
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

- **`mcp`**: MCP server settings
  - `transport`: `stdio` (default) or `http`
  - `port`: Port for HTTP transport
  - `host`: Host for HTTP transport
  - `cors`: Enable CORS for HTTP

- **`debug`**: Enable debug logging

**Security Note**: Never commit API keys to your config file. Use environment variables instead:
```bash
export CHUNKHOUND_EMBEDDING__API_KEY="sk-your-key-here"
```

### Embedding Providers

ChunkHound supports multiple embedding providers for semantic search:

**OpenAI (requires API key)**:
```bash
export OPENAI_API_KEY="sk-your-key-here"
uv run chunkhound index --provider openai --model text-embedding-3-small
```

**Local embedding servers (no API key required)**:

**Ollama**:
```bash
# First, start Ollama with an embedding model
ollama pull nomic-embed-text

# Then use ChunkHound with Ollama
uv run chunkhound index --provider openai-compatible --base-url http://localhost:11434 --model nomic-embed-text
```

**LocalAI, LM Studio, or other OpenAI-compatible servers**:
```bash
uv run chunkhound index --provider openai-compatible --base-url http://localhost:1234 --model your-embedding-model
```

**Text Embeddings Inference (TEI)**:
```bash
uv run chunkhound index --provider tei --base-url http://localhost:8080
```

**Regex-only mode (no embeddings)**:
```bash
# Skip embedding setup entirely - only regex search will be available
uv run chunkhound index --no-embeddings
```

### Environment Variables
```bash
# For OpenAI semantic search only
export OPENAI_API_KEY="sk-your-key-here"

# For local embedding servers (Ollama, LocalAI, etc.)
export CHUNKHOUND_EMBEDDING_PROVIDER="openai-compatible"
export CHUNKHOUND_EMBEDDING_BASE_URL="http://localhost:11434"  # Ollama default
export CHUNKHOUND_EMBEDDING_MODEL="nomic-embed-text"

# Optional: Database location
export CHUNKHOUND_DB_PATH="/path/to/.chunkhound.db"

# Note: No environment variables needed for regex-only usage
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

## How Indexing Works

**Three-tier indexing system for complete coverage:**

1. **Pre-index**: `chunkhound index` - Synchronizes database with current code state by adding new files, removing deleted files, and updating only changed content. Reuses existing embeddings for unchanged code, making re-indexing fast and cost-effective. Can be run periodically (cron, CI/CD, server) and the resulting database shared across teams for secure enterprise workflows
2. **Background scan**: MCP server runs periodic scans every 5 minutes to catch any missed changes  
3. **Real-time updates**: File system events trigger immediate re-indexing of changed files

**Processing pipeline:**
1. **Scan** - Finds code files in your project
2. **Parse** - Extracts functions, classes, methods using tree-sitter  
3. **Index** - Stores code chunks in local DuckDB database
4. **Embed** - Creates AI embeddings for semantic search
5. **Search** - AI assistants query via MCP protocol

## Priority Queue System

ChunkHound uses an internal priority queue to ensure optimal responsiveness and data consistency:

**Priority Order (highest to lowest):**
1. **User queries** - Search requests from AI assistants get immediate processing
2. **File system events** - Real-time file changes are processed next for quick updates
3. **Background search** - Periodic scans run when system is idle

This design ensures that user interactions remain fast and responsive while maintaining up-to-date search results. The queue prevents background operations from interfering with active search requests, while file system events are prioritized to keep the index current with your latest code changes.

## Caching System

ChunkHound uses smart caching to avoid redundant work:

**File change detection:**
- Checks file modification time first, then content checksums
- Unchanged files skip all processing
- Persistent tracking across restarts

**Parse tree caching:**
- Stores parsed code structures in memory
- Reuses existing parsing results when files haven't changed
- Automatic cleanup of outdated entries

**Directory scanning cache:**
- Remembers file discovery results temporarily
- Avoids re-scanning unchanged directories
- Refreshes when directories are modified

This layered approach ensures ChunkHound only processes what actually changed, making indexing fast and efficient even for large codebases.

**Database synchronization:**
Running `chunkhound index` acts as a "fix" command that brings your database into perfect sync with your current codebase. It handles all inconsistencies by adding missing files, removing orphaned entries for deleted files, and updating only the content that actually changed. Expensive embedding generation is skipped for unchanged code chunks, making full re-indexing surprisingly fast and cost-effective.

*Note: ChunkHound currently uses DuckDB. Support for other local and remote databases is planned.*

## Origin Story

**100% of ChunkHound's code was written by an AI agent - zero lines written by hand.**

A human envisioned the project and provided strategic direction, but every single line of code, the project name, documentation, and technical decisions were generated by language models. The human acted as product manager and architect, writing prompts and validating each step, while the AI agent served as compiler - transforming requirements into working code.

The entire codebase emerged through an iterative human-AI collaboration: design → code → test → review → commit. Remarkably, the agent performed its own QA and testing by using ChunkHound to search its own code, creating a self-improving feedback loop where the tool helped build itself.

## License

MIT
