"""
Provider configuration discovery for multi-provider testing.

This module discovers available embedding providers that support reranking
and provides their configurations for parametrized testing.
"""

from typing import Any

import httpx

from .test_utils import get_api_key_for_tests


def services_available(auto_start_rerank: bool = True) -> bool:
    """
    Check if both Ollama and rerank service are available for testing.
    
    Args:
        auto_start_rerank: If True, will attempt to start mock rerank server if not running
    
    Returns:
        True if both services are available, False otherwise
    """
    # Check Ollama embeddings service
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
        ollama_ok = response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        ollama_ok = False
    
    if not ollama_ok:
        return False  # Need Ollama for embeddings
    
    # Check rerank service
    try:
        response = httpx.get("http://localhost:8001/health", timeout=1.0)
        rerank_ok = response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        rerank_ok = False
    
    # If rerank not running and auto-start enabled, try to start mock server
    if not rerank_ok and auto_start_rerank:
        import asyncio
        from tests.fixtures.rerank_server_manager import ensure_rerank_server_running
        
        async def try_start():
            manager = await ensure_rerank_server_running(start_if_needed=True)
            return manager is not None or await manager.is_running() if manager else False
        
        try:
            # Try to start mock server
            rerank_ok = asyncio.run(try_start())
        except Exception:
            rerank_ok = False
    
    return ollama_ok and rerank_ok


def get_reranking_providers() -> list[tuple[str, type, dict[str, Any]]]:
    """
    Discover available providers that support reranking.
    
    Returns:
        List of (provider_name, provider_class, config_dict) tuples for
        providers that are available and support reranking functionality.
    """
    providers = []
    
    # Check for VoyageAI provider
    api_key, provider_name = get_api_key_for_tests()
    if provider_name == "voyageai" and api_key:
        from chunkhound.providers.embeddings.voyageai_provider import VoyageAIEmbeddingProvider
        providers.append((
            "voyageai",
            VoyageAIEmbeddingProvider,
            {
                "api_key": api_key,
                "model": "voyage-3.5",
                "batch_size": 100,
                "timeout": 30,
                "retry_attempts": 3,
            }
        ))
    
    # Check for Ollama with reranking service
    # Important: Only include Ollama if it's ACTUALLY running (not just mock rerank server)
    # We need real Ollama for embeddings, mock rerank server alone isn't enough
    if services_available(auto_start_rerank=False):  # Don't auto-start, check actual availability
        from chunkhound.providers.embeddings.openai_provider import OpenAIEmbeddingProvider
        providers.append((
            "openai",  # Use standard provider name (configured for Ollama)
            OpenAIEmbeddingProvider,
            {
                "api_key": "dummy-key",  # Ollama doesn't require real API key
                "base_url": "http://localhost:11434/v1",
                "model": "nomic-embed-text",
                "rerank_model": "test-model",
                "rerank_url": "http://localhost:8001/rerank",
                "batch_size": 100,
                "timeout": 30,
                "retry_attempts": 3,
            }
        ))
    
    return providers


def get_provider_ids() -> list[str]:
    """Get list of available provider IDs for pytest parametrization."""
    return [provider_name for provider_name, _, _ in get_reranking_providers()]


def should_skip_if_no_providers() -> bool:
    """Check if tests should be skipped due to no available providers."""
    return len(get_reranking_providers()) == 0