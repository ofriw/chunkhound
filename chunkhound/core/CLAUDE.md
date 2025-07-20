# Core Module Context

## MODULE_PURPOSE
Core contains the foundational types, models, and configuration that all other modules depend on.
This is the "pure" domain layer with no external dependencies.

## TYPE_SYSTEM_ARCHITECTURE

### Common Types (`types/common.py`)
```python
# PATTERN: NewType for type safety without runtime overhead
FileId = NewType('FileId', int)
ChunkId = NewType('ChunkId', int)
LineNumber = NewType('LineNumber', int)

# BENEFIT: Prevents mixing IDs, line numbers, etc.
# USAGE: chunk_id: ChunkId = ChunkId(42)
```

### Language Enum
```python
# PATTERN: Centralized language support
# CONSTRAINT: Adding a language requires:
#   1. Enum value in Language
#   2. File pattern in get_file_patterns()
#   3. Parser implementation in providers/
#   4. Tree-sitter grammar installation
```

### ChunkType Enum
```python
# SEMANTIC_UNITS:
- FUNCTION: Standalone functions
- METHOD: Class methods
- CLASS: Class definitions
- MODULE: File-level/module docs
- UNKNOWN: Fallback for unrecognized

# MARKDOWN_UNITS:
- HEADER_1-6: Document structure
- PARAGRAPH: Content blocks
```

## DATA_MODELS (`models.py`)

### Design Principles
1. **Immutable by default** - Use frozen dataclasses
2. **Type-safe** - Leverage NewType wrappers
3. **Serializable** - to_dict() / from_dict() methods
4. **Validation** - Pydantic for configs, dataclasses for domain

### Core Models
```python
@dataclass(frozen=True)
class File:
    # IDENTITY: Unique by path
    # MUTABILITY: Only mtime and size_bytes change
    # RELATIONSHIPS: One-to-many with Chunks
    
@dataclass(frozen=True)
class Chunk:
    # IDENTITY: Unique by file_id + content hash
    # SEARCH_KEY: code field for full-text search
    # METADATA: language, type for filtering
    
@dataclass(frozen=True)
class Embedding:
    # IDENTITY: Unique by chunk_id + provider + model
    # DIMENSION: Varies by model (1536 for OpenAI)
    # STORAGE: Vector as JSON array or binary
```

## CONFIGURATION_SYSTEM

### Hierarchy and Precedence
1. CLI arguments (highest)
2. Environment variables
3. Local .chunkhound.json
4. Config file via --config
5. Default values (lowest)

### Environment Variable Pattern
```bash
# PATTERN: Double underscore for nesting
CHUNKHOUND_DATABASE__PROVIDER=duckdb
CHUNKHOUND_EMBEDDING__API_KEY=sk-...
CHUNKHOUND_INDEXING__EXCLUDE=["*.pyc", "__pycache__"]
```

### Config Validation
```python
# PATTERN: Command-specific validation
config.validate_for_command("index")  # Requires embedding provider
config.validate_for_command("search") # Embedding optional
```

### Provider Configuration
```python
# PRINCIPLE: Provider-specific settings in nested config
config.database.duckdb.batch_size = 5000
config.database.lancedb.batch_size = 1000

# MIGRATION: Legacy flat config auto-converted
```

## EXCEPTION_HIERARCHY

### Base Exceptions
```python
ChunkHoundError          # Base for all custom exceptions
├── ConfigurationError   # Invalid config, missing requirements
├── ProviderError       # Provider-specific failures
│   ├── DatabaseError   # Connection, query failures
│   └── EmbeddingError  # API errors, rate limits
└── ProcessingError     # File parsing, chunking failures
```

### Error Handling Pattern
```python
# PATTERN: Wrap provider errors with context
try:
    result = provider.operation()
except ProviderSpecificError as e:
    raise ChunkHoundError(f"Operation failed: {e}") from e
```

## FACTORY_PATTERNS

### DatabaseProviderFactory
```python
# REGISTRY: Providers self-register with @register decorator
# SELECTION: Based on config.database.provider
# WRAPPING: Automatic SerialDatabaseProvider for thread safety
```

### EmbeddingProviderFactory
```python
# API_KEY_RESOLUTION:
# 1. Config system (CHUNKHOUND_EMBEDDING__API_KEY)
# 2. Legacy support (OPENAI_API_KEY)
# 3. Provider-specific (ANTHROPIC_API_KEY, etc.)
```

## TESTING_PATTERNS

### Type Safety Tests
```python
# PATTERN: Verify NewType prevents mixing
with pytest.raises(TypeError):
    file_id: FileId = 42  # Must use FileId(42)
```

### Config Precedence Tests
```python
# PATTERN: Test each precedence level
os.environ["CHUNKHOUND_DATABASE__PATH"] = "env.db"
config = Config(database={"path": "config.db"})
assert config.database.path == "env.db"  # Env wins
```

### Model Serialization Tests
```python
# PATTERN: Round-trip serialization
chunk = Chunk(...)
assert Chunk.from_dict(chunk.to_dict()) == chunk
```

## PERFORMANCE_CONSIDERATIONS

1. **NewType has zero runtime cost** - Pure type checking
2. **Dataclasses are faster than dicts** - Attribute access
3. **Frozen dataclasses enable caching** - Hashable
4. **Pydantic validation has overhead** - Use only for user input

## COMMON_PITFALLS

- DONT: Mix raw ints with typed IDs (FileId, ChunkId)
- DONT: Mutate frozen dataclasses (create new instances)
- DONT: Use dicts for domain models (use dataclasses)
- DONT: Skip validation for user-provided config
- DONT: Add provider-specific logic to core (keep it pure)