# ChunkHound Architecture

This document describes ChunkHound's service-layer architecture, designed for modularity, testability, and extensibility.

## Overview

ChunkHound uses a **service-layer architecture** with **dependency injection** through a registry pattern. This design enables clean separation of concerns, easy testing, and pluggable components.

## Architecture Principles

1. **Separation of Concerns** - Each layer has a single responsibility
2. **Dependency Injection** - Components are loosely coupled through interfaces
3. **Pluggable Providers** - Database, embedding, and parsing implementations are interchangeable
4. **Testability** - All components can be unit tested in isolation
5. **Performance** - Optimized for fast startup and efficient resource usage

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   run command   │  │  config command │  │ mcp command  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ IndexingService  │  │ EmbeddingService │  │SearchService│ │
│  └──────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     Provider Layer                          │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │DatabaseProvider  │  │EmbeddingProvider │  │ ParsingProvider│ │
│  │  - DuckDB        │  │  - OpenAI       │  │  - Python   │ │
│  │  - SQLite (planned)│ │  - TEI          │  │  - Java     │ │
│  │                  │  │  - BGE-IN-ICL   │  │  - C#       │ │
│  │                  │  │                 │  │  - TypeScript│ │
│  │                  │  │                 │  │  - JavaScript│ │
│  │                  │  │                 │  │  - Markdown │ │
│  └──────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                       Core Layer                            │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │     Models       │  │      Types      │  │ Exceptions  │ │
│  │  - Chunk         │  │  - Language     │  │  - Core     │ │
│  │  - Embedding     │  │  - Provider     │  │  - Provider │ │
│  │  - File          │  │  - Status       │  │  - Service  │ │
│  └──────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Module Structure

### Core Layer (`core/`)

The foundation layer containing shared models, types, and exceptions.

```python
core/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── chunk.py        # Code chunk data model
│   ├── embedding.py    # Embedding data model
│   └── file.py         # File metadata model
├── types/
│   ├── __init__.py
│   └── common.py       # Common type definitions
└── exceptions/
    ├── __init__.py
    └── core.py         # Base exception classes
```

**Responsibilities:**
- Define data models (Chunk, Embedding, File)
- Provide type definitions and enums
- Define exception hierarchy
- No business logic or external dependencies

### Interfaces Layer (`interfaces/`)

Abstract base classes defining contracts for all providers.

```python
interfaces/
├── __init__.py
├── database_provider.py    # Database operations contract
├── embedding_provider.py   # Embedding generation contract
└── language_parser.py      # Code parsing contract
```

**Key Interfaces:**

```python
class DatabaseProvider(ABC):
    @abstractmethod
    async def store_chunks(self, chunks: List[Chunk]) -> None: ...
    
    @abstractmethod
    async def search_semantic(self, query: str, limit: int) -> List[Chunk]: ...
    
    @abstractmethod
    async def search_regex(self, pattern: str, limit: int) -> List[Chunk]: ...

class EmbeddingProvider(ABC):
    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]: ...
    
    @abstractmethod
    def get_dimension(self) -> int: ...

class LanguageParser(ABC):
    @abstractmethod
    def parse_file(self, content: str, file_path: Path) -> List[Chunk]: ...
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]: ...
```

### Providers Layer (`providers/`)

Concrete implementations of the interface contracts.

```python
providers/
├── __init__.py
├── database/
│   ├── __init__.py
│   └── duckdb_provider.py      # DuckDB implementation
├── embeddings/
│   ├── __init__.py
│   └── openai_provider.py      # OpenAI API implementation
└── parsing/
    ├── __init__.py
    ├── python_parser.py        # Python tree-sitter parser
    ├── java_parser.py          # Java tree-sitter parser
    ├── csharp_parser.py        # C# tree-sitter parser
    ├── typescript_parser.py    # TypeScript tree-sitter parser
    ├── javascript_parser.py    # JavaScript tree-sitter parser
    └── markdown_parser.py      # Markdown parser
```

**Provider Features:**
- **Database Providers:** Support multiple backends (DuckDB, planned: SQLite, PostgreSQL)
- **Embedding Providers:** Support multiple APIs (OpenAI, TEI, BGE-IN-ICL, Ollama)
- **Language Parsers:** Tree-sitter based parsing for accurate syntax analysis

### Services Layer (`services/`)

Business logic layer orchestrating providers to implement features.

```python
services/
├── __init__.py
├── base_service.py         # Base service with common functionality
├── indexing_coordinator.py # Coordinates file indexing process
├── embedding_service.py    # Manages embedding generation
└── search_service.py       # Handles search requests
```

**Service Responsibilities:**

```python
class IndexingCoordinator(BaseService):
    """Orchestrates the entire indexing pipeline."""
    
    async def index_directory(self, path: Path) -> None:
        # 1. Discover files
        # 2. Parse code into chunks
        # 3. Generate embeddings
        # 4. Store in database
        # 5. Handle incremental updates

class EmbeddingService(BaseService):
    """Manages embedding generation and caching."""
    
    async def generate_batch(self, chunks: List[Chunk]) -> List[Embedding]:
        # 1. Batch chunks efficiently
        # 2. Generate embeddings via provider
        # 3. Handle rate limiting and retries
        # 4. Cache results

class SearchService(BaseService):
    """Handles all search operations."""
    
    async def semantic_search(self, query: str, limit: int) -> List[Chunk]:
        # 1. Generate query embedding
        # 2. Perform vector search
        # 3. Rank and filter results
    
    async def regex_search(self, pattern: str, limit: int) -> List[Chunk]:
        # 1. Validate regex pattern
        # 2. Search database
        # 3. Return matching chunks
```

### Registry Layer (`registry/`)

Dependency injection container managing component lifecycle and wiring.

```python
registry/
├── __init__.py
└── registry.py         # Service registry and DI container
```

**Registry Pattern:**

```python
class ServiceRegistry:
    """Central registry for dependency injection."""
    
    def __init__(self):
        self._providers = {}
        self._services = {}
        self._singletons = {}
    
    def register_provider(self, interface: type, implementation: type):
        """Register a provider implementation."""
        self._providers[interface] = implementation
    
    def get_provider(self, interface: type):
        """Get provider instance with dependency injection."""
        if interface in self._singletons:
            return self._singletons[interface]
        
        implementation = self._providers[interface]
        instance = implementation()
        self._singletons[interface] = instance
        return instance
    
    def get_service(self, service_type: type):
        """Get service instance with injected dependencies."""
        # Inject required providers automatically
        return service_type(
            database=self.get_provider(DatabaseProvider),
            embedding=self.get_provider(EmbeddingProvider),
            parsers=self.get_parsers()
        )
```

### API Layer (`chunkhound/api/`)

User-facing interfaces including CLI and MCP server.

```python
chunkhound/api/
├── __init__.py
├── cli/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── run.py              # Index command
│   │   ├── config.py           # Configuration management
│   │   └── mcp.py              # MCP server command
│   ├── parsers/                # Argument parsers
│   └── utils/                  # CLI utilities
└── mcp/
    ├── __init__.py
    ├── server.py               # MCP protocol server
    └── tools.py                # MCP tool implementations
```

## Data Flow

### Indexing Flow

```
1. CLI run command
   ↓
2. IndexingCoordinator.index_directory()
   ↓
3. File discovery and filtering
   ↓
4. LanguageParser.parse_file() for each file
   ↓
5. EmbeddingService.generate_batch() for chunks
   ↓
6. DatabaseProvider.store_chunks()
   ↓
7. File watching for incremental updates
```

### Search Flow

```
1. MCP client search request
   ↓
2. SearchService.semantic_search() or regex_search()
   ↓
3. EmbeddingProvider.generate_embeddings() (for semantic)
   ↓
4. DatabaseProvider.search_semantic() or search_regex()
   ↓
5. Result ranking and filtering
   ↓
6. Return to MCP client
```

## Configuration Management

ChunkHound uses a hierarchical configuration system:

```json
# ~/.chunkhound/config.json
{
  "embedding": {
    "provider": "openai",
    type: openai
    base_url: https://api.openai.com/v1
    model: text-embedding-3-small
    api_key: ${CHUNKHOUND_EMBEDDING_API_KEY}
    default: true
    enabled: true
    
  local-tei:
    type: tei
    base_url: http://localhost:8080
    batch_size: 32
    timeout: 60
    enabled: false

database:
  path: ~/.cache/chunkhound/chunks.duckdb
  connection_pool_size: 5

parsing:
  batch_size: 50
  max_concurrent: 3
  debounce_ms: 500
```

**Configuration Priority:**
1. Command-line arguments
2. Environment variables  
3. Project-specific config (`.chunkhound.json`)
4. User config (`~/.chunkhound/config.json`)
5. Default values

## Performance Optimizations

### Startup Performance

- **Lazy Loading:** Components loaded only when needed
- **Import Optimization:** Reduced import chain for CLI commands
- **Registry Caching:** Singleton pattern for expensive objects

### Runtime Performance

- **Incremental Parsing:** Only reparse changed files
- **Batch Processing:** Efficient embedding generation
- **Connection Pooling:** Database connections reused
- **Vector Indexing:** HNSW indexes for fast semantic search

### Memory Management

- **Streaming Processing:** Large files processed in chunks
- **Garbage Collection:** Explicit cleanup of temporary objects
- **Resource Limits:** Configurable memory and concurrency limits

## Extension Points

### Adding New Database Providers

1. Implement `DatabaseProvider` interface
2. Add provider to registry
3. Update configuration schema
4. Add tests and documentation

```python
class PostgreSQLProvider(DatabaseProvider):
    async def store_chunks(self, chunks: List[Chunk]) -> None:
        # Implementation specific to PostgreSQL
        pass
```

### Adding New Embedding Providers

1. Implement `EmbeddingProvider` interface
2. Handle provider-specific authentication
3. Add rate limiting and retry logic
4. Register in provider registry

```python
class OllamaProvider(EmbeddingProvider):
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Implementation for Ollama local embeddings
        pass
```

### Adding New Language Parsers

1. Implement `LanguageParser` interface
2. Add tree-sitter grammar dependency
3. Define chunk extraction rules
4. Register file extensions

```python
class RustParser(LanguageParser):
    def parse_file(self, content: str, file_path: Path) -> List[Chunk]:
        # Implementation for Rust code parsing
        pass
    
    def get_supported_extensions(self) -> List[str]:
        return ['.rs']
```

## Testing Strategy

### Unit Testing

Each layer is tested in isolation using mock dependencies:

```python
def test_indexing_coordinator():
    # Mock all provider dependencies
    mock_db = Mock(spec=DatabaseProvider)
    mock_embedding = Mock(spec=EmbeddingProvider)
    mock_parsers = {'py': Mock(spec=LanguageParser)}
    
    coordinator = IndexingCoordinator(
        database=mock_db,
        embedding=mock_embedding,
        parsers=mock_parsers
    )
    
    # Test business logic without external dependencies
    assert coordinator.should_reindex(file_path, last_modified)
```

### Integration Testing

Full pipeline testing with real providers:

```python
def test_end_to_end_indexing():
    # Use real DuckDB and OpenAI providers
    registry = ServiceRegistry()
    registry.register_provider(DatabaseProvider, DuckDBProvider)
    registry.register_provider(EmbeddingProvider, OpenAIProvider)
    
    coordinator = registry.get_service(IndexingCoordinator)
    await coordinator.index_directory(test_project_path)
    
    # Verify results in database
    chunks = await coordinator.database.search_semantic("test query", 10)
    assert len(chunks) > 0
```

### Performance Testing

Benchmarks for critical paths:

```python
def test_startup_performance():
    start_time = time.time()
    from chunkhound.api.cli.main import main
    startup_time = time.time() - start_time
    
    # Verify startup time under 0.5 seconds
    assert startup_time < 0.5

def test_indexing_performance():
    # Measure indexing throughput
    files_per_second = measure_indexing_rate(large_project_path)
    assert files_per_second > 100  # Files per second
```

## Error Handling

### Exception Hierarchy

```python
class ChunkHoundError(Exception):
    """Base exception for all ChunkHound errors."""
    pass

class ProviderError(ChunkHoundError):
    """Base exception for provider-related errors."""
    pass

class DatabaseError(ProviderError):
    """Database operation errors."""
    pass

class EmbeddingError(ProviderError):
    """Embedding generation errors."""
    pass

class ParsingError(ProviderError):
    """Code parsing errors."""
    pass
```

### Error Recovery

- **Graceful Degradation:** Continue operation when non-critical components fail
- **Retry Logic:** Automatic retries for transient failures
- **Fallback Providers:** Switch to backup providers when primary fails
- **User Feedback:** Clear error messages with actionable suggestions

## Security Considerations

### API Key Management

- Environment variables preferred over configuration files
- No API keys logged or exposed in error messages
- Support for external secret management systems

### Input Validation

- All user inputs validated and sanitized
- Path traversal protection for file operations
- SQL injection prevention through parameterized queries
- Regular expression DoS protection

### Network Security

- TLS/SSL for all external API communications
- Certificate validation for HTTPS requests
- Timeout and rate limiting for external requests
- No sensitive data in request logs

## Deployment Considerations

### Docker Deployment

```dockerfile
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install -e .
CMD ["chunkhound", "mcp"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chunkhound
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: chunkhound
        image: chunkhound:latest
        env:
        - name: CHUNKHOUND_EMBEDDING_API_KEY
          valueFrom:
            secretKeyRef:
              name: chunkhound-secrets
              key: openai-api-key
```

### Monitoring and Observability

- **Metrics:** Indexing rate, search latency, error rates
- **Logging:** Structured logging with correlation IDs
- **Health Checks:** Provider health monitoring
- **Alerting:** Critical error notifications

## Migration Guide

### From v1.0 to v1.1

The service-layer architecture is backward compatible for most use cases:

**CLI Commands:** No changes required
**Configuration:** Existing configs work with new format recommended
**MCP Integration:** No changes required
**Database:** Automatic schema migration on startup

**Recommended Updates:**
1. Update configuration to new format
2. Review provider settings for optimization
3. Test custom integrations with new interfaces

## Future Roadmap

### Planned Features

1. **Additional Database Providers:** PostgreSQL, SQLite, Elasticsearch
2. **More Embedding Providers:** Hugging Face Transformers, Azure OpenAI
3. **Language Support:** Go, Rust, PHP, Ruby, Swift
4. **Advanced Search:** Hybrid search, query expansion, result clustering
5. **Collaboration Features:** Shared indexes, team configurations

### Architecture Evolution

1. **Microservices:** Split into dedicated services for large deployments
2. **Async Processing:** Background job processing for large repositories
3. **Distributed Storage:** Shard indexes across multiple databases
4. **Real-time Sync:** Live collaboration with multiple clients

## Conclusion

ChunkHound's service-layer architecture provides a solid foundation for semantic code search with excellent performance, extensibility, and maintainability. The dependency injection pattern enables easy testing and customization, while the provider pattern allows seamless integration with different backends and services.

For questions or contributions, see the main README.md and contribution guidelines.