"""Shared MCP tool implementations for both stdio and HTTP servers.

This module contains the core business logic for MCP tools, extracted to eliminate
duplication between stdio and HTTP server implementations. Functions are pure and
stateless - they take explicit dependencies and return raw data.
"""

import asyncio
import json
from typing import Any, TypedDict, cast

try:
    from typing import NotRequired  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    from typing_extensions import NotRequired

from chunkhound.database_factory import DatabaseServices
from chunkhound.embeddings import EmbeddingManager
from chunkhound.version import __version__

# Response size limits (tokens)
MAX_RESPONSE_TOKENS = 20000
MIN_RESPONSE_TOKENS = 1000
MAX_ALLOWED_TOKENS = 25000


# Type definitions for return values
class PaginationInfo(TypedDict):
    """Pagination metadata for search results."""
    offset: int
    page_size: int
    has_more: bool
    total: NotRequired[int | None]
    next_offset: NotRequired[int | None]


class SearchResponse(TypedDict):
    """Response structure for search operations."""
    results: list[dict[str, Any]]
    pagination: PaginationInfo


class HealthStatus(TypedDict):
    """Health check response structure."""
    status: str
    version: str
    database_connected: bool
    embedding_providers: list[str]


def estimate_tokens(text: str) -> int:
    """Estimate token count using simple heuristic (3 chars ≈ 1 token for safety)."""
    return len(text) // 3


def limit_response_size(
    response_data: SearchResponse, max_tokens: int = MAX_RESPONSE_TOKENS
) -> SearchResponse:
    """Limit response size to fit within token limits by reducing results."""
    if not response_data.get("results"):
        return response_data

    # Start with full response and iteratively reduce until under limit
    limited_results = response_data["results"][:]

    while limited_results:
        # Create test response with current results
        test_response = {
            "results": limited_results,
            "pagination": response_data["pagination"],
        }

        # Estimate token count
        response_text = json.dumps(test_response, default=str)
        token_count = estimate_tokens(response_text)

        if token_count <= max_tokens:
            # Update pagination to reflect actual returned results
            actual_count = len(limited_results)
            updated_pagination = response_data["pagination"].copy()
            updated_pagination["page_size"] = actual_count
            updated_pagination["has_more"] = updated_pagination.get(
                "has_more", False
            ) or actual_count < len(response_data["results"])
            if actual_count < len(response_data["results"]):
                updated_pagination["next_offset"] = (
                    updated_pagination.get("offset", 0) + actual_count
                )

            return {"results": limited_results, "pagination": updated_pagination}

        # Remove results from the end to reduce size
        # Remove in chunks for efficiency
        reduction_size = max(1, len(limited_results) // 4)
        limited_results = limited_results[:-reduction_size]

    # If even empty results exceed token limit, return minimal response
    return {
        "results": [],
        "pagination": {
            "offset": response_data["pagination"].get("offset", 0),
            "page_size": 0,
            "has_more": len(response_data["results"]) > 0,
            "total": response_data["pagination"].get("total", 0),
            "next_offset": None,
        },
    }


async def search_regex_impl(
    services: DatabaseServices,
    pattern: str,
    page_size: int = 10,
    offset: int = 0,
    path_filter: str | None = None,
) -> SearchResponse:
    """Core regex search implementation.

    Args:
        services: Database services bundle
        pattern: Regex pattern to search for
        page_size: Number of results per page (1-100)
        offset: Starting offset for pagination
        path_filter: Optional path filter

    Returns:
        Dict with 'results' and 'pagination' keys
    """
    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)

    # Check database connection
    if services and not services.provider.is_connected:
        services.provider.connect()

    # Perform search
    results, pagination = services.provider.search_regex(
        pattern=pattern,
        page_size=page_size,
        offset=offset,
        path_filter=path_filter,
    )

    return cast(SearchResponse, {"results": results, "pagination": pagination})


async def search_semantic_impl(
    services: DatabaseServices,
    embedding_manager: EmbeddingManager,
    query: str,
    page_size: int = 10,
    offset: int = 0,
    provider: str | None = None,
    model: str | None = None,
    threshold: float | None = None,
    path_filter: str | None = None,
) -> SearchResponse:
    """Core semantic search implementation.

    Args:
        services: Database services bundle
        embedding_manager: Embedding manager instance
        query: Search query text
        page_size: Number of results per page (1-100)
        offset: Starting offset for pagination
        provider: Embedding provider name (optional)
        model: Embedding model name (optional)
        threshold: Distance threshold for filtering (optional)
        path_filter: Optional path filter

    Returns:
        Dict with 'results' and 'pagination' keys

    Raises:
        Exception: If no embedding providers available or configured
        asyncio.TimeoutError: If embedding request times out
    """
    # Validate embedding manager and providers
    if not embedding_manager or not embedding_manager.list_providers():
        raise Exception(
            "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
        )

    # Use explicit provider/model from arguments, otherwise get from configured provider
    if not provider or not model:
        try:
            default_provider_obj = embedding_manager.get_provider()
            if not provider:
                provider = default_provider_obj.name
            if not model:
                model = default_provider_obj.model
        except ValueError:
            raise Exception(
                "No default embedding provider configured. "
                "Either specify provider and model explicitly, or configure a default provider."
            )

    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)

    # Check database connection
    if services and not services.provider.is_connected:
        services.provider.connect()

    # Get embedding for query with timeout
    try:
        result = await asyncio.wait_for(
            embedding_manager.embed_texts([query], provider), timeout=12.0
        )
        query_vector = result.embeddings[0]
    except asyncio.TimeoutError:
        raise Exception(
            "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
        )

    # Perform search
    results, pagination = services.provider.search_semantic(
        query_embedding=query_vector,
        provider=provider,
        model=model,
        page_size=page_size,
        offset=offset,
        threshold=threshold,
        path_filter=path_filter,
    )

    return cast(SearchResponse, {"results": results, "pagination": pagination})


async def get_stats_impl(services: DatabaseServices) -> dict[str, Any]:
    """Core stats implementation.

    Args:
        services: Database services bundle

    Returns:
        Dict with database statistics
    """
    stats: dict[str, Any] = services.provider.get_stats()
    return stats


async def health_check_impl(services: DatabaseServices, embedding_manager: EmbeddingManager) -> HealthStatus:
    """Core health check implementation.

    Args:
        services: Database services bundle
        embedding_manager: Embedding manager instance

    Returns:
        Dict with health status information
    """
    health_status = {
        "status": "healthy",
        "version": __version__,
        "database_connected": services is not None and services.provider.is_connected,
        "embedding_providers": embedding_manager.list_providers()
        if embedding_manager
        else [],
    }

    return cast(HealthStatus, health_status)
