# Service Layer Context

## WHY_SERVICE_LAYER_EXISTS
Services orchestrate complex multi-step operations that require:
1. Different concurrency models per phase (parse→parallel, store→serial)
2. Provider-specific optimizations (batching strategies)
3. Transaction boundaries across components
4. Coordination between CPU-bound and IO-bound operations

## SERVICE_ARCHITECTURE
```
IndexingCoordinator (orchestrates file processing)
    ├── Uses: EmbeddingService (manages batching)
    ├── Uses: ChunkService (handles storage)
    ├── Uses: SearchService (query optimization)
    └── Ensures: Thread safety + optimal performance
```

## CONCURRENCY_MODEL
```python
# PATTERN: Three-phase processing with different concurrency
async def process_file(file_path):
    # Phase 1: PARSE (CPU-bound, parallelizable)
    # - Tree-sitter parsing is thread-safe
    # - Can process multiple files concurrently
    chunks = await parse_file_async(file_path)
    
    # Phase 2: EMBED (IO-bound, rate-limited)
    # - Concurrent API calls with semaphore
    # - Batched for 100x performance
    embeddings = await generate_embeddings_concurrent(chunks)
    
    # Phase 3: STORE (Database-bound, serial)
    # - MUST be serial for DuckDB/LanceDB
    # - Batched for 250x performance  
    await store_serial(chunks, embeddings)
```

## INDEXING_COORDINATOR_PATTERNS

### File Processing Safety
```python
# PATTERN: File-level locking prevents race conditions
file_locks: dict[Path, asyncio.Lock] = {}

async def process_file_safe(file_path: Path):
    # CRITICAL: One file processed at a time
    async with file_locks[file_path]:
        # ATOMIC: All-or-nothing update
        await process_with_transaction(file_path)
```

### Transaction Pattern
```python
# PATTERN: Ensure atomic updates
async def _process_file_transactional(file_path: Path):
    # Step 1: Start transaction (provider-specific)
    transaction = await db.begin_transaction()
    
    try:
        # Step 2: Delete old data
        await db.delete_file_data(file_path)
        
        # Step 3: Insert new data
        await db.insert_chunks(new_chunks)
        await db.insert_embeddings(new_embeddings)
        
        # Step 4: Commit
        await transaction.commit()
    except Exception:
        # CRITICAL: Rollback on any error
        await transaction.rollback()
        raise
```

## EMBEDDING_SERVICE_PATTERNS

### Intelligent Batching
```python
# PATTERN: Multi-level batching optimization
class EmbeddingService:
    # Level 1: API batch size (provider limit)
    api_batch_size = 2048  # OpenAI limit
    
    # Level 2: Concurrent batch limit (rate limit)
    max_concurrent_batches = 8  # Semaphore control
    
    # Level 3: Database batch size (transaction size)
    db_batch_size = 5000  # Optimal for DuckDB
```

### Rate Limit Management
```python
# PATTERN: Respect provider limits
async def _process_with_rate_limit(self, batch):
    async with self.rate_limiter:
        # Track tokens/requests
        self.tokens_used += estimate_tokens(batch)
        self.requests_made += 1
        
        # Wait if approaching limit
        if self.tokens_used > self.token_limit * 0.9:
            await self._wait_for_limit_reset()
```

## SEARCH_SERVICE_PATTERNS

### Query Optimization
```python
# PATTERN: Provider-specific query optimization
async def search_semantic(query: str, limit: int):
    # Step 1: Generate query embedding (cached)
    query_embedding = await self._get_or_create_embedding(query)
    
    # Step 2: Provider-specific optimization
    if self.provider_type == "duckdb":
        # Use HNSW index with pre-filtering
        return await self._search_duckdb_optimized(query_embedding, limit)
    elif self.provider_type == "lancedb":
        # Use IVF index with post-filtering
        return await self._search_lancedb_optimized(query_embedding, limit)
```

## CHUNK_SERVICE_PATTERNS

### Bulk Operations
```python
# PATTERN: Optimize for analytical databases
async def store_chunks_batch(chunks: list[Chunk]):
    # CRITICAL: Analytical DBs hate single inserts
    if len(chunks) < 50:
        # Small batch: Keep indexes
        await self._insert_with_indexes(chunks)
    else:
        # Large batch: Drop/recreate indexes
        await self._insert_optimized(chunks)
```

## PERFORMANCE_CRITICAL_PATHS
1. **File Processing**: Sequential to prevent DB contention
2. **Embedding Generation**: Parallel with batching (100x speedup)
3. **Database Writes**: Serial with transactions (data integrity)
4. **Search Queries**: Optimized per provider (index usage)

## SERVICE_LAYER_BENEFITS
- **Separation of Concerns**: Each service has single responsibility
- **Performance**: Optimal batching/concurrency per operation
- **Reliability**: Proper error handling and recovery
- **Flexibility**: Easy to swap providers without changing logic
- **Observability**: Central place for metrics/logging

## ANTI_PATTERNS_TO_AVOID
- DONT: Call providers directly from high-level code
- DONT: Mix concurrency models within a service method  
- DONT: Assume batch sizes work across providers
- DONT: Skip transaction boundaries for "performance"
- DONT: Implement provider-specific logic outside services

## PERFORMANCE_METRICS
| Service | Operation | Time | Throughput |
|---------|-----------|------|------------|
| IndexingCoordinator | Process 1K file codebase | 60s | 17 files/sec |
| EmbeddingService | Generate 10K embeddings | 10s | 1K embeddings/sec |
| ChunkService | Store 50K chunks | 20s | 2.5K chunks/sec |
| SearchService | Semantic search | 5ms | 200 queries/sec |

## TESTING_SERVICE_LAYER
1. **Concurrency Tests**: Verify thread safety
2. **Performance Tests**: Validate batching benefits
3. **Error Recovery**: Test transaction rollback
4. **Memory Tests**: Large codebase processing
5. **Integration Tests**: End-to-end workflows