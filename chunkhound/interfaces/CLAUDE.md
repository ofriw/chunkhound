# Interfaces Module Context

## MODULE_PURPOSE
Defines abstract contracts (Protocols) that providers must implement.
Uses Python's Protocol typing for structural subtyping (duck typing with type safety).

## PROTOCOL_PATTERN_RATIONALE

### Why Protocols Instead of ABC?
```python
# TRADITIONAL (ABC):
class DatabaseProvider(ABC):
    @abstractmethod
    def connect(self): ...
    
# MODERN (Protocol):  
class DatabaseProvider(Protocol):
    def connect(self) -> None: ...
```

**Benefits:**
1. **No inheritance required** - Providers don't need to subclass
2. **Structural typing** - If it walks like a duck...
3. **Better for testing** - Easy to create test doubles
4. **Zero runtime overhead** - Pure type checking

## CORE_INTERFACES

### DatabaseProvider Protocol
```python
# CONTRACT: Defines all database operations
# IMPLEMENTATIONS: DuckDBProvider, LanceDBProvider
# WRAPPER: SerialDatabaseProvider adds thread safety

# REQUIRED_METHODS:
- connect/disconnect: Lifecycle management
- insert/update/delete: CRUD operations
- search_semantic/regex: Query operations
- begin/commit/rollback_transaction: ACID support

# PERFORMANCE_REQUIREMENTS:
- Batch operations must be optimized
- Vector search must use indexes
- Single-threaded access (enforced by wrapper)
```

### EmbeddingProvider Protocol
```python
# CONTRACT: Defines embedding generation interface
# IMPLEMENTATIONS: OpenAI, Ollama

# REQUIRED_METHODS:
- embed(texts) -> vectors: Batch embedding generation
- dimension: Vector dimension property
- max_batch_size: Provider-specific limit

# OPTIONAL_METHODS:
- create_token_aware_batches(): Smart batching
- estimate_tokens(): For rate limit management
```

### LanguageParser Protocol
```python
# CONTRACT: Defines code parsing interface
# IMPLEMENTATIONS: 20+ language-specific parsers

# REQUIRED_METHODS:
- parse_file(path) -> ParseResult: Extract AST
- language: Language enum property
- supported_chunk_types: What this parser extracts

# TREE_SITTER_INTEGRATION:
- All parsers use tree-sitter grammars
- Queries defined in .scm files
- Incremental parsing support
```

## IMPLEMENTATION_PATTERNS

### Self-Registration Pattern
```python
# PATTERN: Providers register themselves on import
@DatabaseProviderFactory.register("duckdb")
class DuckDBProvider:
    # Implementation auto-registered
    
# USAGE: Factory lookup by name
provider = DatabaseProviderFactory.create("duckdb")
```

### Capability Detection
```python
# PATTERN: Check for optional methods
if hasattr(provider, 'create_token_aware_batches'):
    batches = provider.create_token_aware_batches(texts)
else:
    batches = simple_batch(texts, provider.max_batch_size)
```

### Error Contract
```python
# PATTERN: Providers raise specific exceptions
class ProviderError(ChunkHoundError): ...
class ConnectionError(ProviderError): ...
class QueryError(ProviderError): ...

# USAGE: Catch at service layer
try:
    result = provider.search_semantic(...)
except ProviderError as e:
    logger.error(f"Provider failed: {e}")
    raise ServiceError("Search failed") from e
```

## TESTING_INTERFACES

### Mock Providers
```python
# PATTERN: Simple test doubles
class MockDatabaseProvider:
    def connect(self): pass
    def search_semantic(self, ...): 
        return [{"id": 1, "content": "test"}]
        
# TYPE_CHECKING: Validates mock implements protocol
provider: DatabaseProvider = MockDatabaseProvider()
```

### Compliance Testing
```python
# PATTERN: Test all implementations against protocol
@pytest.mark.parametrize("provider_class", [
    DuckDBProvider,
    LanceDBProvider,
])
def test_database_provider_protocol(provider_class):
    # Verify all required methods exist
    assert hasattr(provider_class, 'connect')
    assert hasattr(provider_class, 'search_semantic')
```

## EXTENDING_INTERFACES

### Adding New Methods
```python
# STEP 1: Add to Protocol
class DatabaseProvider(Protocol):
    def new_method(self) -> str: ...
    
# STEP 2: Implement in all providers
# STEP 3: Update SerialDatabaseProvider wrapper
# STEP 4: Add tests
```

### Adding New Provider Type
```python
# STEP 1: Create new Protocol
class CacheProvider(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    
# STEP 2: Create implementations
# STEP 3: Create factory if multiple implementations
```

## PROTOCOL_VERSIONING

### Backward Compatibility
```python
# PATTERN: Optional methods for new features
class DatabaseProvider(Protocol):
    # Required (all versions)
    def search_semantic(self, ...) -> list: ...
    
    # Optional (v2.0+)
    def search_hybrid(self, ...) -> list | None:
        return None  # Default implementation
```

### Feature Detection
```python
# PATTERN: Check capabilities at runtime
if hasattr(provider, 'search_hybrid'):
    # Use new hybrid search
else:
    # Fall back to semantic search
```

## PERFORMANCE_CONTRACTS

### Batching Requirements
- EmbeddingProvider: Must handle up to max_batch_size
- DatabaseProvider: Must optimize for batch_size parameter
- LanguageParser: Should parse incrementally if possible

### Threading Contracts  
- DatabaseProvider: Implementations need not be thread-safe
- SerialDatabaseProvider: Wrapper ensures thread safety
- EmbeddingProvider: Should be thread-safe (stateless)
- LanguageParser: Must be thread-safe (read-only)

## COMMON_ANTI_PATTERNS

- DONT: Check isinstance() for protocols (use hasattr)
- DONT: Inherit from Protocol (it's for typing only)
- DONT: Add state to Protocol definitions
- DONT: Make all methods required (use optional for extensions)
- DONT: Forget to test protocol compliance