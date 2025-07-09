# Embedding Provider Token Limit Handling

This module provides utilities for handling token limit exceeded errors across all embedding providers. The shared logic ensures consistent behavior when API requests exceed token limits.

## Quick Start

For new embedding providers, use the decorator approach:

```python
from .batch_utils import with_openai_token_handling, with_generic_token_handling

class MyEmbeddingProvider:
    # Implement required methods for TokenLimitHandler protocol
    def estimate_batch_tokens(self, texts: List[str]) -> int:
        # Estimate total tokens for the batch
        pass
    
    def get_model_token_limit(self) -> int:
        # Return the model's maximum token limit
        pass
    
    def chunk_text_by_tokens(self, text: str, token_limit: int) -> List[str]:
        # Split oversized text into chunks
        pass
    
    # Apply decorator to embedding methods
    @with_openai_token_handling()  # or @with_generic_token_handling()
    async def embed(self, texts: List[str]) -> List[List[float]]:
        # Your embedding implementation
        # Token limit errors will be automatically handled
        pass
```

## Available Decorators

- `@with_openai_token_handling()` - For OpenAI-specific errors
- `@with_anthropic_token_handling()` - For Anthropic-specific errors  
- `@with_generic_token_handling()` - For any provider with generic token limit messages

## Manual Error Handling

For providers that need custom error handling:

```python
from .batch_utils import handle_token_limit_error

async def my_embed_method(self, texts: List[str]) -> List[List[float]]:
    try:
        return await self._actual_embed(texts)
    except SomeTokenLimitError as e:
        total_tokens = self.estimate_batch_tokens(texts)
        token_limit = self.get_model_token_limit() - 100
        
        return await handle_token_limit_error(
            texts=texts,
            total_tokens=total_tokens,
            token_limit=token_limit,
            embed_function=self._actual_embed,
            chunk_text_function=self.chunk_text_by_tokens
        )
```

## Key Features

- **Optimal Batch Splitting**: Uses ceiling division to calculate minimum required splits
- **Even Distribution**: Distributes texts evenly across batches with remainder handling
- **Single Text Chunking**: Handles oversized individual texts by token-based chunking
- **Configurable Fallback**: Option to use first chunk as representative for oversized texts
- **Safety Margins**: Configurable safety margin subtracted from token limits
- **Generic Error Detection**: Supports multiple providers with different error formats

## Protocol Requirements

To use the token limit handling utilities, your provider must implement the `TokenLimitHandler` protocol:

1. `estimate_batch_tokens(texts)` - Estimate total tokens for a batch
2. `get_model_token_limit()` - Return the model's maximum token limit  
3. `chunk_text_by_tokens(text, limit)` - Split a single text by token count

## Error Handling Logic

When a token limit error is detected:

1. **Multiple texts**: Split batch into optimal number of sub-batches based on token estimates
2. **Single text**: Chunk the text by tokens and either:
   - Return embedding of first chunk (fallback mode)
   - Return embeddings of all chunks (full mode)
3. **Unsplittable text**: Raise `ValidationError` if text cannot be chunked further

This ensures no provider fails on oversized batches, providing consistent behavior across all embedding backends.