# ChunkHound Project Context

## What ChunkHound Is
ChunkHound is a semantic and regex search tool for codebases that provides MCP (Model Context Protocol) integration for AI assistants. It indexes code files using tree-sitter parsing, stores chunks in a local database, and enables both exact pattern matching and semantic search through AI embeddings.

## Key Technologies
- Python 3.10+ with tree-sitter for parsing
  - Using `uv` package and project manager
- SQLite database for local storage
- OpenAI embeddings for semantic search
- MCP server for AI assistant integration
- Support for Python, Java, C#, TypeScript, JavaScript, and Markdown
- Use `uv` to run python code and manage dependencies

## Project Structure
- Main indexing and search logic in chunkhound/ directory
- CLI wrapper and MCP launcher at root level
- Real-time file watching with debouncing for incremental updates
- Test files for modification and creation verification
- `<project dir>/tickets` contains project tickets

# Important!
- Avoid logs in the MCP server that will mess with the JSON-RPC
