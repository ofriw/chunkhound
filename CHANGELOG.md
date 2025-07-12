# Changelog

All notable changes to ChunkHound will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.7.0] - 2025-07-12

### Fixed
- MCP server now uses configured embedding model instead of hardcoded text-embedding-3-small default, ensuring semantic search works with any configured model
- MCP test environment improvements with comprehensive test data and configuration files

## [2.6.3] - 2025-07-10

### Fixed
- Configuration merge precedence now correctly preserves environment variables over JSON config values
- MCP server semantic search now works properly when running from different directories

### Removed
- Removed obsolete Ubuntu 20 Dockerfile as issue was resolved in configuration system

## [2.6.2] - 2025-07-10

### Fixed
- MCP server now properly loads embedding provider configuration from target directory

## [2.6.1] - 2025-07-10

### Fixed
- MCP server now properly respects CLI-provided project root directory for configuration loading
- Configuration files (.chunkhound.json) are now correctly loaded when running MCP server from different directories

## [2.6.0] - 2025-07-10

### Fixed
- MCP server crashes on Ubuntu and Linux systems when running from different directories by fixing database path resolution and process coordination
- Enhanced TaskGroup error reporting to show underlying causes instead of generic wrapper errors
- Configuration file loading in MCP server now properly respects .chunkhound.json files in target directories
- Database lock conflicts between multiple MCP instances resolved with proper process detection

### Enhanced
- Docker test infrastructure for MCP server validation to prevent future regressions
- Improved error messages for debugging MCP server issues with detailed analysis

## [2.5.4] - 2025-07-10

### Fixed
- MCP server reliability on Ubuntu and other Linux distributions when running from different directories
- Database path resolution consistency across all MCP server components

## [2.5.3] - 2025-07-10

### Fixed
- MCP server communication reliability improved by removing debug logging that interfered with JSON-RPC protocol

## [2.5.2] - 2025-07-10

### Added
- Automatic database optimization during embedding generation to maintain performance with large datasets (every 1000 batches, configurable via `CHUNKHOUND_EMBEDDING_OPTIMIZATION_BATCH_FREQUENCY`)

### Fixed
- MCP server compatibility on Ubuntu and other strict platforms by preserving virtual environment context in subprocesses
- OpenAI embedding provider crash on Ubuntu due to async resource creation outside event loop context

## [2.5.1] - 2025-01-09

### Fixed
- Project detection now properly respects CHUNKHOUND_PROJECT_ROOT environment variable, ensuring MCP command works correctly when launched from any directory
- Removed duplicate MCP parser function that could cause confusion

## [2.5.0] - 2025-01-09

### Enhanced
- MCP positional path argument now controls complete project scope - database location, config file search, and watch paths are all set to the specified directory instead of just watch paths

### Fixed
- MCP launcher import path resolution when running from different directories, eliminating TaskGroup errors on Ubuntu and other strict platforms

## [2.4.4] - 2025-01-09

### Fixed
- Ubuntu TaskGroup crash fixed by removing problematic directory change in MCP launcher

## [2.4.3] - 2025-01-09

### Fixed
- MCP server now works correctly when launched from any directory, not just the project root
- Fixed path resolution inconsistencies that caused TaskGroup errors on Ubuntu deployments

## [2.4.2] - 2025-01-09

### Added
- MCP command now accepts optional path argument to specify directory for indexing and watching (defaults to current directory)

### Fixed
- Parser architecture inconsistencies resolved across C, Bash, and Makefile parsers for consistent search functionality
- MCP server database duplication eliminated through proper async task isolation
- LanceDB storage growth controlled with automatic optimization during quiet periods
- MCP server reliability improved with corrected import structure and dependency resolution
- Python parser behavior now consistent between CLI and MCP modes
- Search operation freezes after file deletion resolved with proper thread safety

## [2.4.1] - 2025-01-09

### Fixed
- Package structure consolidated under chunkhound/ directory for improved import reliability and Python packaging best practices

## [2.4.0] - 2025-01-09

### Fixed
- LanceDB storage growth issue resolved with automatic database optimization during quiet periods
- Configuration system project root detection for .chunkhound.json files improved

### Changed
- Enhanced database provider architecture with capability detection and activity tracking
- Modernized configuration system by removing legacy registry config building

## [2.3.1] - 2025-07-09

### Fixed
- MCP server communication reliability improved by preventing stderr output from corrupting JSON-RPC messages
- Enhanced configuration documentation with automatic .chunkhound.json detection examples

## [2.3.0] - 2025-07-08

### Changed
- **BREAKING**: Configuration system completely refactored with centralized management and clear precedence hierarchy
- **BREAKING**: Automatic configuration file loading removed - config files now only load with explicit `--config` flag
- **BREAKING**: Environment variables standardized to `CHUNKHOUND_*` prefix with `__` delimiters (e.g., `CHUNKHOUND_EMBEDDING__API_KEY`)
- **BREAKING**: Legacy `OPENAI_API_KEY` and `OPENAI_BASE_URL` environment variables no longer supported

### Added
- Complete CLI argument coverage for all configuration options
- Centralized configuration precedence: CLI args → Config file → Environment variables → Defaults
- Comprehensive migration guide for updating existing configurations
- Database file gitignore pattern for Lance database files

### Fixed
- MCP server database duplication caused by shared transaction state across async tasks
- Parser architecture inconsistencies for C, Bash, and Makefile language parsers
- Configuration auto-detection issues that caused deployment complexity

## [2.2.0] - 2025-01-07

### Fixed
- Database freezing during concurrent file operations through proper async/sync boundary handling
- Thread safety issues in DuckDB provider with synchronized WAL cleanup and operation timeouts
- LanceDB duplicate file entries through atomic merge operations and path normalization
- File deletion operations now properly handle async contexts without blocking the event loop

### Changed
- Aligned LanceDB provider with serial executor pattern for consistency with DuckDB
- Improved path normalization to handle symlinks and different path representations
- Enhanced database operation reliability with proper thread isolation

### Added
- Support for complete configuration storage including API keys in .chunkhound.json files
- Consolidated embedding provider creation system for consistent behavior across CLI and config files

## [2.1.4] - 2025-07-03

### Fixed
- CLI argument defaults no longer override config file values
- Updated dependencies via uv.lock

## [2.1.3] - 2025-07-03

### Changed
- Consolidated embedding provider creation to use single factory pattern for consistency
- Reduced embedding provider log verbosity for cleaner output

## [2.1.2] - 2025-07-03

### Fixed
- API key configuration loading from .chunkhound.json files
- Configuration precedence documentation to match actual behavior

### Added
- Complete configuration examples with API key and security guidance

## [2.1.1] - 2025-07-03

### Added
- Centralized version management system for consistent versioning across all components

### Changed
- Simplified version updates through automated scripts
- Enhanced installation and development documentation
- Code formatting improvements and linting cleanup

### Fixed
- Version consistency across CLI, MCP server, and package initialization
- Import statement in package `__init__.py` for better module exposure

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

[Unreleased]: https://github.com/chunkhound/chunkhound/compare/v2.7.0...HEAD
[2.7.0]: https://github.com/chunkhound/chunkhound/compare/v2.6.3...v2.7.0
[2.6.3]: https://github.com/chunkhound/chunkhound/compare/v2.6.2...v2.6.3
[2.6.2]: https://github.com/chunkhound/chunkhound/compare/v2.6.1...v2.6.2
[2.6.1]: https://github.com/chunkhound/chunkhound/compare/v2.6.0...v2.6.1
[2.6.0]: https://github.com/chunkhound/chunkhound/compare/v2.5.4...v2.6.0
[2.5.4]: https://github.com/chunkhound/chunkhound/compare/v2.5.3...v2.5.4
[2.5.3]: https://github.com/chunkhound/chunkhound/compare/v2.5.2...v2.5.3
[2.5.2]: https://github.com/chunkhound/chunkhound/compare/v2.5.1...v2.5.2
[2.5.1]: https://github.com/chunkhound/chunkhound/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/chunkhound/chunkhound/compare/v2.4.4...v2.5.0
[2.4.4]: https://github.com/chunkhound/chunkhound/compare/v2.4.3...v2.4.4
[2.4.3]: https://github.com/chunkhound/chunkhound/compare/v2.4.2...v2.4.3
[2.4.2]: https://github.com/chunkhound/chunkhound/compare/v2.4.1...v2.4.2
[2.4.1]: https://github.com/chunkhound/chunkhound/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/chunkhound/chunkhound/compare/v2.3.1...v2.4.0
[2.3.1]: https://github.com/chunkhound/chunkhound/compare/v2.3.0...v2.3.1
[2.3.0]: https://github.com/chunkhound/chunkhound/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/chunkhound/chunkhound/compare/v2.1.4...v2.2.0
[2.1.4]: https://github.com/chunkhound/chunkhound/compare/v2.1.3...v2.1.4
[2.1.3]: https://github.com/chunkhound/chunkhound/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/chunkhound/chunkhound/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/chunkhound/chunkhound/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/chunkhound/chunkhound/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/chunkhound/chunkhound/compare/v1.2.3...v2.0.0
[1.2.3]: https://github.com/chunkhound/chunkhound/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/chunkhound/chunkhound/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/chunkhound/chunkhound/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/chunkhound/chunkhound/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/chunkhound/chunkhound/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/chunkhound/chunkhound/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/chunkhound/chunkhound/releases/tag/v1.0.0