# Test Fixtures for ChunkHound

## Overview

This directory contains test fixtures for ChunkHound, including **fake providers** that enable comprehensive end-to-end testing without external API dependencies.

## Files

### `fake_providers.py`

Deterministic fake implementations of LLM and embedding providers for CI/CD testing.

**Key Features:**
- **No API calls**: All responses are generated locally
- **Deterministic**: Same input always produces same output
- **Hash-based embeddings**: Text content hashed to generate consistent vectors
- **Pattern-based LLM responses**: Responses matched to prompt patterns
- **Full interface compliance**: Implements all provider protocol methods

**Providers:**

1. **FakeLLMProvider**
   - Returns scripted responses based on prompt keywords
   - Tracks usage stats (requests, tokens)
   - Simulates minimal latency (~1ms)
   - Token estimation: 4 chars/token

2. **FakeEmbeddingProvider**
   - Generates deterministic embeddings from text hash
   - Normalized unit vectors for cosine similarity
   - Supports reranking with deterministic scoring
   - Token estimation: 3 chars/token
   - Configurable dimensions (default: 1536)

## Usage

### Basic Usage

```python
from tests.fixtures.fake_providers import FakeLLMProvider, FakeEmbeddingProvider

# Create fake providers
fake_llm = FakeLLMProvider(
    model="fake-gpt",
    responses={
        "search": "semantic search implementation details",
        "code": "function definitions and classes",
    }
)

fake_embedding = FakeEmbeddingProvider(
    model="fake-embeddings",
    dims=1536,
    batch_size=100
)

# Use like real providers
embedding = await fake_embedding.embed_single("test text")
response = await fake_llm.complete("explain search")
```

### In Tests

```python
@pytest.fixture
async def test_setup():
    """Setup with fake providers."""
    embedding_provider = FakeEmbeddingProvider()
    llm_provider = FakeLLMProvider()

    # Register with managers
    embedding_manager.register_provider(embedding_provider)

    # Create services
    research_service = DeepResearchService(
        database_services=services,
        embedding_manager=embedding_manager,
        llm_manager=llm_manager,
    )

    yield research_service
```

## Benefits

### For CI/CD
- ✅ **No API keys required**: Tests run in any environment
- ✅ **Fast execution**: No network calls (~1ms per operation)
- ✅ **Deterministic**: Same results every run
- ✅ **Cost-free**: No API usage charges

### For Development
- ✅ **Rapid iteration**: No waiting for API responses
- ✅ **Offline testing**: Work without internet
- ✅ **Predictable**: Know exactly what responses to expect
- ✅ **Full coverage**: Test edge cases without API limits

### For Testing
- ✅ **Real code paths**: Tests exercise actual implementation
- ✅ **Minimal mocking**: Only providers are fake, not internals
- ✅ **Protocol compliance**: Validates interface contracts
- ✅ **Integration testing**: Tests full pipelines end-to-end

## Design Principles

### Determinism

Fake providers use hash-based generation to ensure consistency:

```python
# Same text always produces same embedding
text = "semantic search"
embedding1 = await provider.embed_single(text)
embedding2 = await provider.embed_single(text)
assert embedding1 == embedding2  # Always true
```

### Realistic Behavior

Providers simulate real provider characteristics:
- Token counting and tracking
- Batch processing
- Usage statistics
- Health checks
- Rate limit simulation (optional)

### Interface Compliance

All fake providers implement complete provider protocols:
- `LLMProvider` interface
- `EmbeddingProvider` protocol
- All required methods and properties
- Compatible with real service layers

## Testing Strategy

### What to Test With Fakes

✅ **Pipeline logic**: BFS traversal, aggregation, synthesis
✅ **Budget management**: Token counting, budget enforcement
✅ **Data flow**: Query → search → chunks → boundaries
✅ **Error handling**: Edge cases, empty results
✅ **Integration**: Services working together

### What NOT to Test With Fakes

❌ **API correctness**: Use real providers for API validation
❌ **Model quality**: Fake responses don't reflect real model behavior
❌ **Performance**: Network latency, throughput not realistic
❌ **Rate limits**: Fake providers don't enforce real limits

## Example: Code Research E2E Test

See `tests/test_code_research_e2e.py` for comprehensive example:

```python
async def test_full_research_pipeline(research_setup):
    """Test complete research pipeline from query to synthesis."""
    setup = research_setup
    research_service = setup["research_service"]

    # Perform research using fake providers
    result = await research_service.deep_research("How does semantic search work?")

    # Validate structure and metadata
    assert "answer" in result
    assert result["metadata"]["nodes_explored"] >= 1
    assert len(result["answer"]) > 0
```

## Best Practices

### 1. Use Realistic Test Data

Create test codebases that resemble real code:
```python
test_file.write_text('''
def search_semantic(query: str, limit: int = 10):
    """Perform semantic search using embeddings."""
    embedding = await provider.embed_single(query)
    return database.search(embedding, limit)
''')
```

### 2. Configure Appropriate Responses

Match fake LLM responses to expected patterns:
```python
fake_llm = FakeLLMProvider(responses={
    "synthesis": "## Overview\\nThe system implements...\\n## Architecture\\n...",
    "follow": "1. How is X implemented?\\n2. What is the Y algorithm?",
})
```

### 3. Validate Both Success and Failure

Test edge cases with fake providers:
```python
# Test empty results
empty_embedding = await provider.embed_single("")
assert len(empty_embedding) == provider.dims

# Test large batches
large_batch = ["text"] * 1000
embeddings = await provider.embed(large_batch)
assert len(embeddings) == 1000
```

### 4. Check Usage Stats

Verify fake providers were actually used:
```python
stats = fake_embedding.get_usage_stats()
assert stats["embeddings_generated"] > 0
assert stats["requests_made"] > 0
```

## Extending Fake Providers

### Adding New Response Patterns

```python
fake_llm = FakeLLMProvider(responses={
    "pattern1": "response1",
    "pattern2": "response2",
    # Add more patterns as needed
})
```

### Customizing Embedding Dimensions

```python
# For testing different embedding sizes
fake_embedding_small = FakeEmbeddingProvider(dims=384)
fake_embedding_large = FakeEmbeddingProvider(dims=3072)
```

### Simulating Errors

```python
class ErrorFakeLLMProvider(FakeLLMProvider):
    async def complete(self, prompt: str, **kwargs):
        if "error" in prompt:
            raise RuntimeError("Simulated API error")
        return await super().complete(prompt, **kwargs)
```

## Troubleshooting

### Issue: Tests fail with "Provider not configured"
**Solution**: Ensure providers are registered before creating services

### Issue: Embeddings don't match across runs
**Solution**: Check that you're using the same text input (whitespace matters)

### Issue: LLM responses are "Default test response"
**Solution**: Add appropriate patterns to the responses dict

### Issue: Tests are slow despite using fakes
**Solution**: Check for accidental use of real providers or network calls

## Future Enhancements

Potential improvements for fake providers:

- [ ] Configurable latency simulation
- [ ] Error injection for resilience testing
- [ ] Response recording/playback mode
- [ ] Compatibility with VCR-style fixtures
- [ ] Performance metrics collection
- [ ] Multi-language support for generated code

## Related Files

- `tests/test_code_research_e2e.py`: Comprehensive E2E tests using fake providers
- `tests/test_core_workflow.py`: Basic workflow tests with real components
- `tests/test_qa_deterministic.py`: QA tests with conditional real API usage

## Contributing

When adding new fake provider features:

1. Maintain determinism
2. Follow existing provider protocols
3. Add usage tracking
4. Document new capabilities
5. Add example tests
6. Update this README
