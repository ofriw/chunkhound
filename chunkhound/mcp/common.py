"""Common utilities and error handling for MCP servers.

This module provides shared utilities used by both stdio and HTTP servers,
including error handling, response formatting, and validation helpers.
"""

import asyncio
import json
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class MCPError(Exception):
    """Base exception for MCP operations."""

    pass


class ServiceNotInitializedError(MCPError):
    """Raised when services are accessed before initialization."""

    pass


class EmbeddingTimeoutError(MCPError):
    """Raised when embedding operations timeout."""

    pass


class EmbeddingProviderError(MCPError):
    """Raised when embedding provider is not available."""

    pass


async def with_timeout(
    coro: Coroutine[Any, Any, T], timeout_seconds: float, error_message: str = "Operation timed out"
) -> T:
    """Execute coroutine with timeout and custom error message.

    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        error_message: Custom error message for timeout

    Returns:
        Result of the coroutine

    Raises:
        MCPError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise MCPError(error_message)


def format_error_response(
    error: Exception, include_traceback: bool = False
) -> dict[str, Any]:
    """Format exception as standardized error response.

    Args:
        error: Exception to format
        include_traceback: Whether to include full traceback (debug mode)

    Returns:
        Formatted error dict with type and message
    """
    error_type = type(error).__name__
    error_message = str(error)

    response = {
        "error": {
            "type": error_type,
            "message": error_message,
        }
    }

    if include_traceback:
        import traceback

        response["error"]["traceback"] = traceback.format_exc()

    return response


def validate_search_parameters(
    page_size: int | None = None,
    offset: int | None = None,
    max_tokens: int | None = None,
) -> tuple[int, int, int]:
    """Validate and constrain search parameters to acceptable ranges.

    Args:
        page_size: Requested page size (1-100)
        offset: Requested offset (>= 0)
        max_tokens: Requested max response tokens (1000-25000)

    Returns:
        Tuple of (page_size, offset, max_tokens) with validated values
    """
    # Apply constraints with defaults
    validated_page_size = max(1, min(page_size or 10, 100))
    validated_offset = max(0, offset or 0)
    validated_tokens = max(1000, min(max_tokens or 20000, 25000))

    return validated_page_size, validated_offset, validated_tokens


def format_json_response(data: Any) -> str:
    """Format data as JSON string for stdio protocol.

    Args:
        data: Data to format

    Returns:
        JSON string representation
    """
    return json.dumps(data, default=str, ensure_ascii=False)


def format_tool_response(result: Any, format_type: str = "dict") -> Any:
    """Format tool result based on server type.

    Args:
        result: Tool execution result
        format_type: "dict" for HTTP, "json" for stdio

    Returns:
        Formatted result
    """
    if format_type == "json":
        return format_json_response(result)
    elif format_type == "dict":
        # Ensure it's a proper dict (not a TypedDict)
        return dict(result) if hasattr(result, "__dict__") else result
    else:
        return result


def parse_mcp_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate MCP tool arguments.

    Handles common argument patterns and provides defaults.

    Args:
        args: Raw arguments from MCP request

    Returns:
        Parsed and validated arguments
    """
    # Create a copy to avoid modifying original
    parsed = args.copy()

    # Handle common search parameters
    if "page_size" in parsed:
        parsed["page_size"] = int(parsed["page_size"])
    if "offset" in parsed:
        parsed["offset"] = int(parsed["offset"])
    if "max_response_tokens" in parsed:
        parsed["max_response_tokens"] = int(parsed["max_response_tokens"])
    if "threshold" in parsed and parsed["threshold"] is not None:
        parsed["threshold"] = float(parsed["threshold"])

    return parsed


def add_common_mcp_arguments(parser: Any) -> None:
    """Add common MCP server arguments to a parser.

    This function adds all the configuration arguments that both
    stdio and HTTP MCP servers support.

    Args:
        parser: ArgumentParser to add arguments to
    """
    # Positional path argument
    from pathlib import Path
    
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Directory path to index (default: current directory)",
    )
    
    # Config file argument
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Database arguments
    parser.add_argument("--db", type=str, help="Database path")
    parser.add_argument(
        "--database-provider", choices=["duckdb", "lancedb"], help="Database provider"
    )

    # Embedding arguments
    parser.add_argument(
        "--provider",
        choices=["openai", "openai-compatible"],
        help="Embedding provider",
    )
    parser.add_argument("--model", type=str, help="Embedding model")
    parser.add_argument("--api-key", type=str, help="API key for embedding provider")
    parser.add_argument("--base-url", type=str, help="Base URL for embedding provider")

    # Debug flag
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
