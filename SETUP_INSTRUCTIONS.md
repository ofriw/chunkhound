# ChunkHound Setup Instructions

## What is ChunkHound?

ChunkHound is a semantic and regex search tool that makes your codebase searchable for AI assistants. It creates embeddings to enable natural language search alongside traditional regex pattern matching through the Model Context Protocol (MCP).

**How it works:** ChunkHound breaks your code into small pieces called "chunks" (like individual functions or classes), then converts each chunk into a mathematical representation called an "embedding" - essentially a list of numbers that captures the meaning of that code. These embeddings get stored in a vector database, which can quickly find chunks with similar meanings when you search. It also supports traditional regex search for exact pattern matching. When you ask your AI assistant "find authentication code," the AI can use ChunkHound's semantic search (converting your question to embeddings) or regex search (for precise patterns) to find relevant code. ChunkHound works independently from any specific LLM or AI assistant - as long as your AI tool supports the Model Context Protocol (MCP), it can use ChunkHound's search capabilities. You don't interact with ChunkHound directly; your AI assistant uses it behind the scenes.

**Key Features:**
- **Semantic Search**: Find code by meaning, not just keywords (e.g., "authentication logic" finds auth-related code even without the word "auth")
- **Regex Search**: Pattern matching for precise code queries
- **MCP Integration**: Works with VS Code and other MCP-compatible tools
- **Multi-language Support**: Supports 20+ programming languages via Tree-sitter parsing

## Prerequisites

### 1. Install `uv` Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install ChunkHound

```bash
uv tool install chunkhound
```

## Project Setup

### 1. Configure ChunkHound

Inside your project's root directory, create a `.chunkhound.json` configuration file:

```json
{
  "embedding": {
    "provider": "openai-compatible",
    "base_url": "https://pdc-llm-srv1/llm",
    "api_key": "sk-pdc-llm-05-2025",
    "model": "bge-en-icl"
  }
}
```

This configuration connects ChunkHound to the local PDC LLM server for generating embeddings.

### 2. Run Initial Indexing

Inside the project directory, run the indexing command:

```bash
uv run chunkhound index
```

**What this does:**
- Scans your codebase
- Parses code files and breaks them into chunks
- Generates embeddings for code chunks using the local PDC LLM server
- Stores everything in a local database on your VDI

**Note:** This initial indexing takes time (grab some coffee!), but it's a one-time setup. Future runs perform incremental indexing - only processing changed files and updating the database to match your current filesystem state.

### 3. Start MCP Server

Launch the ChunkHound MCP server:

```bash
uv run chunkhound mcp --http
```

This starts an HTTP server that VS Code and other tools can connect to for search functionality. The MCP server also watches for filesystem changes and updates the index in real-time as you modify files.

### 4. Configure VS Code

Create or update `.vscode/mcp.json` in your project root:

```json
{
 "servers": {
   "chunkhound": {
     "url": "http://127.0.0.1:8000/mcp/",
     "type": "http"
    }
  }
}
```

**Activate in VS Code:**
1. Open Command Palette (`Ctrl+Shift+P`)
2. Select "MCP Servers"
3. Choose "chunkhound"
4. Click "Start"

## Usage Examples

Once set up, you can use ChunkHound through your AI assistant with natural language queries:

### Semantic Search Examples

```
"Find authentication and login related code"
"Show me error handling patterns"
"Where are database connections established?"
"Find code that processes user input validation"
"Show me all REST API endpoint definitions"
```

### Regex Search Examples

```
"Find all functions named 'process*' using regex"
"Search for TODO comments with regex pattern"
"Find all import statements matching a specific pattern"
"Locate all class definitions with regex"
```

### Combined Usage

```
"Find all authentication functions and then show me regex matches for 'auth.*token'"
"Search for database-related code semantically, then find specific SQL patterns"
```
