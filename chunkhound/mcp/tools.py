"""Declarative tool registry for MCP servers.

This module defines all MCP tools in a single location, allowing both
stdio and HTTP servers to use the same tool implementations with their
protocol-specific wrappers.

The registry pattern eliminates duplication and ensures consistent behavior
across server types.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Import the existing tool implementations
from chunkhound.mcp_tools import (
    get_stats_impl,
    health_check_impl,
    limit_response_size,
    search_regex_impl,
    search_semantic_impl,
)


@dataclass
class Tool:
    """Tool definition with metadata and implementation."""

    name: str
    description: str
    parameters: dict[str, Any]
    implementation: Callable
    requires_embeddings: bool = False


# Define all tools declaratively
TOOL_DEFINITIONS = [
    Tool(
        name="get_stats",
        description="Get database statistics including file, chunk, and embedding counts",
        parameters={
            "properties": {},
            "type": "object",
        },
        implementation=get_stats_impl,
        requires_embeddings=False,
    ),
    Tool(
        name="health_check",
        description="Check server health status",
        parameters={
            "properties": {},
            "type": "object",
        },
        implementation=health_check_impl,
        requires_embeddings=False,
    ),
    Tool(
        name="search_regex",
        description="Search code chunks using regex patterns with pagination support.",
        parameters={
            "properties": {
                "pattern": {
                    "description": "Regular expression pattern to search for",
                    "type": "string",
                },
                "page_size": {
                    "default": 10,
                    "description": "Number of results per page (1-100)",
                    "type": "integer",
                },
                "offset": {
                    "default": 0,
                    "description": "Starting position for pagination",
                    "type": "integer",
                },
                "max_response_tokens": {
                    "default": 20000,
                    "description": "Maximum response size in tokens (1000-25000)",
                    "type": "integer",
                },
                "path": {
                    "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                    "type": "string",
                },
            },
            "required": ["pattern"],
            "type": "object",
        },
        implementation=search_regex_impl,
        requires_embeddings=False,
    ),
    Tool(
        name="search_semantic",
        description="Search code using semantic similarity with pagination support.",
        parameters={
            "properties": {
                "query": {
                    "description": "Natural language search query",
                    "type": "string",
                },
                "page_size": {
                    "default": 10,
                    "description": "Number of results per page (1-100)",
                    "type": "integer",
                },
                "offset": {
                    "default": 0,
                    "description": "Starting position for pagination",
                    "type": "integer",
                },
                "max_response_tokens": {
                    "default": 20000,
                    "description": "Maximum response size in tokens (1000-25000)",
                    "type": "integer",
                },
                "path": {
                    "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                    "type": "string",
                },
                "provider": {
                    "default": "openai",
                    "description": "Embedding provider to use",
                    "type": "string",
                },
                "model": {
                    "default": "text-embedding-3-small",
                    "description": "Embedding model to use",
                    "type": "string",
                },
                "threshold": {
                    "description": "Distance threshold for filtering results (optional)",
                    "type": "number",
                },
            },
            "required": ["query"],
            "type": "object",
        },
        implementation=search_semantic_impl,
        requires_embeddings=True,
    ),
]

# Create registry as a dict for easy lookup
TOOL_REGISTRY: dict[str, Tool] = {tool.name: tool for tool in TOOL_DEFINITIONS}


async def execute_tool(
    tool_name: str,
    services: Any,
    embedding_manager: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool from the registry with proper argument handling.

    Args:
        tool_name: Name of the tool to execute
        services: DatabaseServices instance
        embedding_manager: EmbeddingManager instance
        arguments: Tool arguments from the request

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool not found in registry
        Exception: If tool execution fails
    """
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool = TOOL_REGISTRY[tool_name]

    # Extract implementation-specific arguments
    if tool_name == "get_stats":
        return await tool.implementation(services)

    elif tool_name == "health_check":
        return await tool.implementation(services, embedding_manager)

    elif tool_name == "search_regex":
        # Apply response size limiting
        result = await tool.implementation(
            services=services,
            pattern=arguments["pattern"],
            page_size=arguments.get("page_size", 10),
            offset=arguments.get("offset", 0),
            path_filter=arguments.get("path"),
        )
        max_tokens = arguments.get("max_response_tokens", 20000)
        return dict(limit_response_size(result, max_tokens))

    elif tool_name == "search_semantic":
        # Apply response size limiting
        result = await tool.implementation(
            services=services,
            embedding_manager=embedding_manager,
            query=arguments["query"],
            page_size=arguments.get("page_size", 10),
            offset=arguments.get("offset", 0),
            provider=arguments.get("provider"),
            model=arguments.get("model"),
            threshold=arguments.get("threshold"),
            path_filter=arguments.get("path"),
        )
        max_tokens = arguments.get("max_response_tokens", 20000)
        return dict(limit_response_size(result, max_tokens))

    else:
        raise ValueError(f"Tool {tool_name} not implemented in execute_tool")
