# Provider Implementation Context

## PROVIDER_ARCHITECTURE
Providers are concrete implementations of interfaces defined in chunkhound/interfaces/
Two types: DatabaseProvider and EmbeddingProvider
CRITICAL: All providers must be thread-safe or wrapped with SerialDatabaseProvider

## DATABASE_PROVIDER_PATTERN
```python
# REQUIRED: Register with factory
@DatabaseProviderFactory.register("provider_name")
class NewDatabaseProvider(DatabaseProvider):
    # CRITICAL: Single connection per instance
    _connection: Any  # Provider-specific connection type
    
    # REQUIRED: Batch size discovery
    OPTIMAL_BATCH_SIZE = 5000  # Determine via benchmarking
    VECTOR_INDEX_THRESHOLD = 50  # When to drop/recreate indexes
    
    # PATTERN: Connection lifecycle
    async def connect(self):
        # CONSTRAINT: Must be idempotent
        # CONSTRAINT: Must handle reconnection
        pass
    
    # PATTERN: Bulk operations with index optimization
    async def insert_chunks_batch(self, chunks: list[Chunk], batch_size: int = None):
        batch_size = batch_size or self.OPTIMAL_BATCH_SIZE
        
        # OPTIMIZATION: Drop indexes for large batches
        if len(chunks) >= self.VECTOR_INDEX_THRESHOLD:
            await self.drop_vector_index()
            try:
                await self._bulk_insert(chunks, batch_size)
            finally:
                await self.create_vector_index()
        else:
            await self._regular_insert(chunks, batch_size)
```

## EMBEDDING_PROVIDER_PATTERN
```python
# REQUIRED: Register with factory
@EmbeddingProviderFactory.register("provider_name")
class NewEmbeddingProvider(EmbeddingProvider):
    # REQUIRED: Provider limits
    MAX_BATCH_SIZE = 2048  # API limit
    MAX_TOKENS_PER_BATCH = 50000  # Token limit
    RATE_LIMIT_RPM = 3000  # Requests per minute
    
    # PATTERN: Smart batching
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # OPTIMIZATION: Token-aware batching
        batches = self._create_token_aware_batches(texts)
        
        # CONSTRAINT: Respect rate limits
        results = []
        for batch in batches:
            embeddings = await self._embed_batch(batch)
            results.extend(embeddings)
            await self._respect_rate_limit()
        
        return results
```

## PROVIDER_SPECIFIC_CONSTRAINTS

### DuckDB
- THREAD_SAFETY: Single connection only, no concurrent access
- WAL_MODE: Write-Ahead Logging can corrupt with multiple writers
- HNSW_INDEX: Drop before bulk insert (60s → 5s for 10k embeddings)
- OPTIMAL_BATCH: 5000 rows (benchmarked)
- TRANSACTION_SIZE: Keep under 100MB to avoid memory issues

### LanceDB
- THREAD_SAFETY: Read-during-write causes corruption
- ARROW_FORMAT: Columnar storage optimized for batches
- OPTIMAL_BATCH: 1000 rows (Arrow buffer size)
- VECTOR_INDEX: IVF index needs retraining after major updates
- MEMORY_MAPPED: Uses mmap - watch system memory

### OpenAI Embeddings
- BATCH_LIMIT: 2048 texts per request
- TOKEN_LIMIT: 8192 tokens per text
- RATE_LIMIT: 3000 RPM, 1M TPM
- RETRY_STRATEGY: Exponential backoff on 429
- DIMENSION: 1536 (text-embedding-3-small)

### Ollama Embeddings
- BATCH_LIMIT: 10-50 depending on model size
- MEMORY_CONSTRAINT: Local GPU memory limits
- NO_RATE_LIMIT: But CPU/GPU bound
- STARTUP_TIME: First request slow (model loading)

### TEI (Text Embeddings Inference)
- BATCH_LIMIT: 100 optimal for throughput
- MEMORY_CONSTRAINT: Depends on deployment
- ENDPOINT_HEALTH: Check /health before use
- WARMUP_REQUIRED: Send dummy request on startup

## PERFORMANCE_BENCHMARKS
| Provider | Operation | Single | Batched | Optimal Batch |
|----------|-----------|---------|----------|---------------|
| DuckDB | Insert chunks | 50ms | 0.2ms/chunk | 5000 |
| DuckDB | Vector search | 5ms | - | - |
| LanceDB | Insert chunks | 30ms | 0.5ms/chunk | 1000 |
| LanceDB | Vector search | 3ms | - | - |
| OpenAI | Embeddings | 100ms | 0.5ms/text | 2048 |
| Ollama | Embeddings | 200ms | 20ms/text | 50 |
| TEI | Embeddings | 50ms | 1ms/text | 100 |

## SERIAL_WRAPPER_REQUIREMENT
```python
# CRITICAL: Wrap any database provider that isn't thread-safe
if provider_name in ["duckdb", "lancedb"]:
    provider = SerialDatabaseProvider(provider)
```

## TESTING_REQUIREMENTS
Each provider must have:
1. Thread safety test (concurrent operations)
2. Batch optimization test (measure speedup)
3. Error recovery test (connection failures)
4. Memory usage test (large batches)
5. Performance benchmark (vs baseline)

## COMMON_PITFALLS
- DONT: Assume thread safety - test it
- DONT: Use fixed batch sizes - make configurable
- DONT: Ignore memory constraints - monitor usage
- DONT: Skip index optimization - huge performance impact
- DONT: Forget cleanup in error paths - use try/finally

## ADDING_NEW_PROVIDER_CHECKLIST
1. Implement interface from chunkhound/interfaces/
2. Register with appropriate factory
3. Benchmark to find optimal batch size
4. Add thread safety wrapper if needed
5. Document specific constraints in this file
6. Add performance numbers to benchmark table
7. Create comprehensive test suite
8. Update provider selection logic in Config