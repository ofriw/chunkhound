# 2025-07-13 - [FEATURE] Enhanced Docker VS Code Multi-Language Setup
**Priority**: High

Enhance the existing Docker VS Code environment to include comprehensive multi-language test files and ensure proper ollama embeddings configuration for ChunkHound testing.

## Current State

Existing `Dockerfile.ubuntu20-mcp-test` provides:
- ✅ Ubuntu 20.04 with code-server (VS Code web interface)
- ✅ ChunkHound installation and basic indexing
- ✅ MCP configuration template for VS Code integration
- ✅ Basic ollama embeddings configuration using `host.docker.internal:11434`

**Enhancement Needed:**
- Limited test data (only single Python file)
- Missing examples from other supported languages
- Basic test directory structure

## Scope

**Primary Objectives:**
1. **Create comprehensive multi-language test directory** with examples from all supported languages
2. **Enhance ollama embeddings configuration** for reliable Mac host connection
3. **Expand test file coverage** to demonstrate ChunkHound's full language support
4. **Ensure reproducible container setup** with rich test data

**Success Criteria:**
- VS Code accessible at http://localhost:8080 with ChunkHound MCP integration
- Rich multi-language test codebase available for indexing and search
- All ChunkHound-supported languages represented in test files
- Container startup creates identical environment every run with comprehensive test data

## Requirements

### Multi-Language Test Files

Based on ChunkHound's supported languages:
- **Python** (`.py`) - classes, functions, imports, docstrings
- **TypeScript** (`.ts`) - interfaces, types, modules, generics
- **JavaScript** (`.js`) - functions, objects, async/await
- **Go** (`.go`) - packages, structs, methods, interfaces
- **Rust** (`.rs`) - modules, structs, impl blocks, traits  
- **Java** (`.java`) - classes, methods, packages, annotations
- **C#** (`.cs`) - classes, namespaces, properties, LINQ
- **JSON** (`.json`) - configuration, API responses
- **Markdown** (`.md`) - documentation, README files
- **YAML** (`.yml`) - config files, CI/CD definitions

### Technical Configuration

**Ollama Embeddings:**
- Provider: `openai-compatible`
- Base URL: `http://host.docker.internal:11434/v1`
- Model: `nomic-embed-text`
- API Key: `sk-test-local-ollama` (dummy for testing)
- Follow README.md configuration examples for ollama setup

**VS Code MCP Integration:**
- Use stdio transport (per README.md VS Code configuration)
- Configure in `.vscode/mcp.json` as documented in README.md
- Proper environment variable setup
- Reference README.md MCP configuration section

**Container Persistence:**
- Bake test files into image for consistency
- Mount logs directory for debugging
- Ensure database isolation between runs

## Expected Outcome

A robust test environment where:
- Developers can test MCP functionality through familiar VS Code interface
- All ChunkHound features (semantic search, regex search, stats) accessible via MCP
- Multi-language codebase provides realistic testing scenarios
- Ollama embeddings work reliably from Mac host
- Container behavior is consistent and reproducible

## Files to Modify

1. **`Dockerfile.ubuntu20-mcp-test`** - Add comprehensive multi-language test files
2. **`docker-compose.mcp-test.yml`** - Update environment variables for ollama integration
3. **Create test directory structure** - Representative examples for each supported language
4. **Enhance MCP configuration** - Optimize for ollama embeddings

## Dependencies

- **Ollama running on Mac host** at port 11434 with `nomic-embed-text` model
- **VS Code MCP extension compatibility** - Ensure proper MCP protocol support
- **ChunkHound setup instructions** - Follow README.md for installation and configuration guidance

# History

## 2025-07-13T11:08:18+03:00
Initial ticket creation based on comprehensive codebase analysis. Identified existing Docker infrastructure and opportunities for enhancement with multi-language test files.

Key findings:
- Existing Docker setup provides good foundation with VS Code and ChunkHound integration
- ChunkHound supports 20+ languages but test environment only has single Python example
- Ollama configuration template exists and needs optimization for Mac host setup
- Need comprehensive test file suite to demonstrate full ChunkHound capabilities

Next steps: Implement comprehensive multi-language test file suite and optimize ollama embeddings configuration.