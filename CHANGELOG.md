# Changelog

All notable changes to ChunkHound will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2025-07-02

### Fixed
- Database duplication in MCP server by implementing single-threaded executor pattern
- WAL corruption handling during DuckDB catalog replay
- Parser architecture inconsistencies for C, Bash, and Makefile parsers
- DuckDB foreign key constraint transaction limitations
- Python parser CLI/MCP divergence through unified factory pattern
- Connection management architectural violations

### Changed
- Consolidated database operations through DuckDBProvider executor pattern
- Simplified ConnectionManager to handle only connection lifecycle
- Updated file discovery patterns to include all 16 supported languages
- Removed deprecated connection methods and schema fields
- Enhanced transaction handling with contextvars for task isolation

### Added
- Automatic database migration system for schema updates
- Enhanced parser functionality for C pointer functions and Bash function bodies
- Task-local transaction state management
- Comprehensive executor methods for database operations

## [2.0.0] - 2025-06-26

### Added
- 10 new language parsers: Rust, Go, C++, C, Kotlin, Groovy, Bash, TOML, Makefile, Matlab
- Search pagination with response size limits
- Registry-based parser architecture
- MCP search task coordinator
- Test coverage for file modification tracking
- Comment and docstring indexing for all language parsers
- Background periodic indexing for better performance
- Path filtering support for targeted searches
- HNSW index WAL recovery with enhanced checkpoints
- Embedding cache optimization with CRC32-based content tracking

### Changed
- **BREAKING**: 'run' command renamed to 'index' with current directory default
- **BREAKING**: Parser system refactored to registry pattern
- Centralized language support in Language enum
- Optimized embedding performance with token-aware batching
- Enhanced PyInstaller compatibility
- Improved cross-platform build support (Windows, Ubuntu Docker)
- Enhanced MCP server JSON-RPC communication with logging suppression

### Fixed
- Parser error handling and registry integration
- OpenAI token limit handling
- PyInstaller module path resolution
- Database WAL corruption issues on server exit
- File watcher cancellation responsiveness
- Signal handler safety by removing unsafe database operations
- Windows PyInstaller and MATLAB dependency issues
- Build workflow reliability across platforms

## [1.2.3] - 2025-06-23

### Changed
- Default database location changed to current directory for better persistence

### Fixed
- OpenAI token limit exceeded error with dynamic batching for large embedding requests
- Empty chunk filtering to reduce noise in search results
- Python parser validation for empty symbol names
- Windows build support with comprehensive GitHub Actions workflow
- macOS Intel build issues with UV package manager installation
- Cross-platform build workflow reliability

### Added
- Windows build support with automated testing
- Enhanced debugging for build processes across platforms

## [1.2.2] - 2024-12-15

### Added
- File watching CLI for real-time code monitoring

### Changed
- Unified JavaScript and TypeScript parsers
- Default database location to current directory

### Fixed
- Empty symbol validation in Python parser

## [1.2.1] - 2024-11-28

### Added
- Ubuntu 20.04 build support
- Token limit management for MCP search

### Fixed
- Duplicate chunks after file edits
- File modification detection race conditions

## [1.2.0] - 2024-11-15

### Added
- C# language support
- JSON, YAML, and plain text file support
- File watching with real-time indexing

### Fixed
- File deletion handling
- Database connection issues

## [1.1.0] - 2025-06-12

### Added
- Multi-language support: TypeScript, JavaScript, C#, Java, and Markdown
- Comprehensive CLI interface
- Binary distribution with faster startup

### Changed
- Improved CLI startup performance (90% faster)
- Binary startup performance (16x faster)

### Fixed
- Version display consistency
- Cross-platform build issues

## [1.0.1] - 2025-06-11

### Added
- Python 3.10+ compatibility
- PyPI publishing
- Standalone executable support
- MCP server integration

### Fixed
- Dependency conflicts
- OpenAI model parameter handling
- Binary compilation issues

## [1.0.0] - 2025-06-10

### Added
- Initial release of ChunkHound
- Python parsing with tree-sitter
- DuckDB backend for storage and search
- OpenAI embeddings for semantic search
- CLI interface for indexing and searching
- MCP server for AI assistant integration
- File watching for real-time indexing
- Regex search capabilities

For more information, visit: https://github.com/chunkhound/chunkhound

[Unreleased]: https://github.com/chunkhound/chunkhound/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/chunkhound/chunkhound/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/chunkhound/chunkhound/compare/v1.2.3...v2.0.0
[1.2.3]: https://github.com/chunkhound/chunkhound/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/chunkhound/chunkhound/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/chunkhound/chunkhound/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/chunkhound/chunkhound/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/chunkhound/chunkhound/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/chunkhound/chunkhound/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/chunkhound/chunkhound/releases/tag/v1.0.0