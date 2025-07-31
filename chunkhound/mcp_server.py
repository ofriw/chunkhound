#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol

# FILE_CONTEXT: MCP stdio server for AI assistant integration
# CRITICAL: NO stdout output allowed - breaks JSON-RPC protocol
# ARCHITECTURE: Global state required for stdio communication model
# CONSTRAINT: Single instance per database (enforced via ProcessDetector)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions

from chunkhound.mcp_shared import add_common_mcp_arguments
from chunkhound.mcp_tools import (
    MAX_ALLOWED_TOKENS,
    estimate_tokens,
    get_stats_impl,
    health_check_impl,
    limit_response_size,
    search_regex_impl,
    search_semantic_impl,
)
from chunkhound.version import __version__

# CRITICAL: Disable ALL logging to prevent JSON-RPC corruption
# REASON: Any stdout output breaks the protocol
# PATTERN: All debug output must use stderr or be disabled
logging.disable(logging.CRITICAL)
for logger_name in ["", "mcp", "server", "fastmcp"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)


# Disable loguru logger used by database module
try:
    from loguru import logger as loguru_logger

    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
except ImportError:
    pass

try:
    from .api.cli.utils.config_factory import (
        create_default_config,
        create_validated_config,
    )
    from .api.cli.utils.config_helpers import validate_config_for_command
    from .core.config import EmbeddingProviderFactory
    from .core.config.config import Config
    from .database import Database
    from .database_factory import create_database_with_dependencies
    from .embeddings import EmbeddingManager
    from .registry import configure_registry, get_registry
except ImportError:
    # Handle running as standalone script or PyInstaller binary
    from chunkhound.api.cli.utils.config_factory import (
        create_default_config,
        create_validated_config,
    )
    from chunkhound.core.config import EmbeddingProviderFactory
    from chunkhound.core.config.config import Config
    from chunkhound.database import Database
    from chunkhound.database_factory import create_database_with_dependencies
    from chunkhound.embeddings import EmbeddingManager

# SECTION: Global_State_Management
# RATIONALE: MCP stdio protocol requires persistent state across requests
# CONSTRAINT: Cannot use dependency injection - no request context in stdio
# PATTERN: Initialize once in lifespan, reuse for all operations
_database: Database | None = None
_embedding_manager: EmbeddingManager | None = None
_server_config: Config | None = None
_initialization_complete: asyncio.Event = asyncio.Event()

# Initialize MCP server with explicit stdio
server: Server = Server("ChunkHound Code Search")


def _log_processing_error(e: Exception, event_type: str, file_path: Path) -> None:
    """Log file processing errors without corrupting JSON-RPC.

    # CRITICAL: Must use stderr, never stdout
    # PATTERN: Only log in debug mode to minimize output
    # FORMAT: [MCP-SERVER] prefix for grep filtering
    """
    debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
    if debug_mode:
        print(
            f"[MCP-SERVER] Error processing {event_type} for {file_path}: {e}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)

    # Also log to logger if available
    try:
        from loguru import logger

        logger.error(f"File processing failed for {event_type} {file_path}: {e}")
    except ImportError:
        pass


def log_environment_diagnostics() -> None:
    """Log environment diagnostics for API key debugging - only in non-MCP mode."""
    import os

    # Skip diagnostics in MCP mode to maintain clean JSON-RPC communication
    if os.environ.get("CHUNKHOUND_MCP_MODE"):
        return
    # print("=== MCP SERVER ENVIRONMENT DIAGNOSTICS ===", file=sys.stderr)

    # Check for API key using config system
    from chunkhound.core.config.embedding_config import EmbeddingConfig

    # Check config system
    try:
        temp_config = EmbeddingConfig(provider="openai")
        has_key = temp_config.api_key is not None
        # print(f"CHUNKHOUND_EMBEDDING_API_KEY configured: {has_key}", file=sys.stderr)

        if has_key:
            key_value = temp_config.api_key.get_secret_value()
            # print(f"API key length: {len(key_value)}", file=sys.stderr)
            # print(f"API key prefix: {key_value[:7]}...", file=sys.stderr)
    except Exception:
        has_key = False
        # print(f"CHUNKHOUND_EMBEDDING_API_KEY not configured: {e}", file=sys.stderr)

    if not has_key:
        # print("WARNING: No API key found. Set CHUNKHOUND_EMBEDDING_API_KEY environment variable.", file=sys.stderr)
        pass

    # print("===============================================", file=sys.stderr)


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle.

    # LIFECYCLE: Initialize → Serve requests → Cleanup
    # CRITICAL: All initialization must complete before serving
    # CLEANUP: Must close DB
    # ERROR_HANDLING: Continue on non-critical failures (e.g., embeddings)
    """
    global _database, _embedding_manager, _initialization_complete

    # ENVIRONMENT: Set MCP mode flag for other components
    # PURPOSE: Suppress any output that might break JSON-RPC
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    # PATTERN: Debug mode with commented prints
    # REASON: Even stderr output can interfere with some MCP clients
    # USAGE: Uncomment specific prints when debugging issues
    # ALTERNATIVE: Use debug_log() for structured logging
    debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
    if debug_mode:
        # print("Server lifespan: Starting initialization", file=sys.stderr)
        pass

    try:
        # Log environment diagnostics for API key debugging
        log_environment_diagnostics()

        # Import project detection utilities
        try:
            from .utils.project_detection import find_project_root
        except ImportError:
            pass

        # Use pre-created and validated config from main()
        global _config, _server_config
        config = _config
        _server_config = config

        if config:
            debug_mode = config.debug or debug_mode
            if debug_mode:
                # print(
                #     f"Server lifespan: Using pre-validated config with database path: {config.database.path}",
                #     file=sys.stderr,
                # )
                pass
        else:
            # Fallback to default config
            config = create_default_config()
            _server_config = config

        # Get database path from config (always set by validation)
        if not config:
            raise ValueError("Configuration not initialized")
        db_path = Path(config.database.path)

        db_path.parent.mkdir(parents=True, exist_ok=True)

        if debug_mode:
            # print(f"Server lifespan: Using database at {db_path}", file=sys.stderr)

            pass

        # Initialize embedding configuration BEFORE database creation
        _embedding_manager = EmbeddingManager()
        if debug_mode:
            # print("Server lifespan: Embedding manager initialized", file=sys.stderr)

            pass
        if debug_mode:
            # print(
            #     "Server lifespan: Using Config object directly for unified factory",
            #     file=sys.stderr,
            # )
            pass
        # SECTION: Embedding_Provider_Setup (OPTIONAL)
        # PATTERN: Continue without embeddings if setup fails
        # COMMON_FAILURE: Missing API key - expected for search-only usage
        try:
            # Create provider using unified factory
            if config.embedding:
                provider = EmbeddingProviderFactory.create_provider(config.embedding)
            else:
                raise ValueError("No embedding configuration available")
            _embedding_manager.register_provider(provider, set_default=True)

            if debug_mode:
                # print(
                #     f"Server lifespan: Embedding provider registered successfully: {config.embedding.provider} with model {config.embedding.model}",
                #     file=sys.stderr,
                # )

                pass
        except ValueError:
            # API key or configuration issue - only log in non-MCP mode
            if debug_mode:
                # print(
                #     f"Server lifespan: Embedding provider setup failed (expected): {e}",
                #     file=sys.stderr,
                # )
                pass
            if debug_mode and not os.environ.get("CHUNKHOUND_MCP_MODE"):
                # print(f"Embedding provider setup failed: {e}", file=sys.stderr)
                # print("Configuration help:", file=sys.stderr)
                # print(
                #     "- Set CHUNKHOUND_EMBEDDING__PROVIDER (openai|openai-compatible|tei|bge-in-icl)",
                #     file=sys.stderr,
                # )
                # print(
                #     "- Set CHUNKHOUND_EMBEDDING__API_KEY or legacy OPENAI_API_KEY",
                #     file=sys.stderr,
                # )
                # print("- Set CHUNKHOUND_EMBEDDING__MODEL (optional)", file=sys.stderr)
                # print(
                #     "- For OpenAI-compatible: Set CHUNKHOUND_EMBEDDING__BASE_URL",
                #     file=sys.stderr,
                # )
                pass
        except Exception:
            # Unexpected error - log for debugging but continue
            if debug_mode:
                # print(
                #     f"Server lifespan: Unexpected error setting up embedding provider: {e}",
                #     file=sys.stderr,
                # )
                pass

                # traceback.print_exc(file=sys.stderr)

        # Create database using unified factory for consistency with CLI commands
        # This ensures same initialization across all execution paths
        _database = create_database_with_dependencies(
            db_path=db_path,
            config=config.to_dict(),
            embedding_manager=_embedding_manager,
        )
        try:
            # CRITICAL: Thread-safe database initialization
            # CONSTRAINT: Must connect before any async tasks start
            # PREVENTS: Concurrent operations during initialization
            # USES: SerialDatabaseProvider for thread safety
            _database.connect()
            if debug_mode:
                # print(
                #     "Server lifespan: Database connected successfully", file=sys.stderr
                # )
                # Verify IndexingCoordinator has embedding provider
                try:
                    # Use the same instance from _database to avoid creating duplicates
                    indexing_coordinator = _database._indexing_coordinator
                    has_embedding_provider = (
                        indexing_coordinator._embedding_provider is not None
                    )
                    # print(
                    #     f"Server lifespan: IndexingCoordinator embedding provider available: {has_embedding_provider}",
                    #     file=sys.stderr,
                    # )
                except Exception:
                    # print(
                    #     f"Server lifespan: Debug check failed: {debug_error}",
                    #     file=sys.stderr,
                    # )
                    pass
        except Exception:
            if debug_mode:
                # print(
                #     f"Server lifespan: Database connection error: {db_error}",
                #     file=sys.stderr,
                # )
                pass

                # traceback.print_exc(file=sys.stderr)
            raise

        if debug_mode:
            # print(
            #     "Server lifespan: All components initialized successfully",
            #     file=sys.stderr,
            # )

            pass

        # Mark initialization as complete
        _initialization_complete.set()

        # Return server context to the caller
        yield {
            "db": _database,
            "embeddings": _embedding_manager,
        }

    except Exception as e:
        if debug_mode:
            # print(f"Server lifespan: Initialization failed: {e}", file=sys.stderr)
            pass

            # traceback.print_exc(file=sys.stderr)
        raise Exception(f"Failed to initialize database and embeddings: {e}")
    finally:
        # Reset initialization flag
        _initialization_complete.clear()

        if debug_mode:
            # print("Server lifespan: Entering cleanup phase", file=sys.stderr)

            pass
        # Cleanup database
        if _database:
            try:
                if debug_mode:
                    # print(
                    #     "Server lifespan: Closing database connection...",
                    #     file=sys.stderr,
                    # )

                    pass
                # Force final checkpoint before closing to minimize WAL size
                try:
                    _database.execute_database_operation_sync("maybe_checkpoint", True)
                    if debug_mode:
                        # print(
                        #     "Server lifespan: Final checkpoint completed",
                        #     file=sys.stderr,
                        # )
                        pass
                except Exception:
                    if debug_mode:
                        # print(
                        #     f"Server lifespan: Final checkpoint failed: {checkpoint_error}",
                        #     file=sys.stderr,
                        # )

                        pass
                # Close database (skip built-in checkpoint as we just did it)
                _database.disconnect()
                if debug_mode:
                    # print(
                    #     "Server lifespan: Database connection closed successfully",
                    #     file=sys.stderr,
                    # )
                    pass
            except Exception:
                if debug_mode:
                    # print(
                    #     f"Server lifespan: Error closing database: {db_close_error}",
                    #     file=sys.stderr,
                    # )

                    pass

        if debug_mode:
            # print("Server lifespan: Cleanup complete", file=sys.stderr)

            pass


def truncate_code(code: str, max_chars: int = 1000) -> tuple[str, bool]:
    """Truncate code content with smart line breaking."""
    if len(code) <= max_chars:
        return code, False

    # Try to break at line boundaries
    lines = code.split("\n")
    truncated_lines = []
    char_count = 0

    for line in lines:
        if char_count + len(line) + 1 > max_chars:
            break
        truncated_lines.append(line)
        char_count += len(line) + 1

    return "\n".join(truncated_lines) + "\n...", True


def convert_to_ndjson(results: list[dict[str, Any]]) -> str:
    """Convert search results to NDJSON format."""
    lines = []
    for result in results:
        lines.append(json.dumps(result, ensure_ascii=False))
    return "\n".join(lines)


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    # Wait for server initialization to complete
    try:
        await asyncio.wait_for(_initialization_complete.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        # Continue anyway - individual resource checks will handle missing resources
        pass
    if not _database:
        raise Exception("Database not initialized")

    if name == "search_regex":
        pattern = arguments.get("pattern", "")
        page_size = arguments.get("page_size", 10)
        offset = arguments.get("offset", 0)
        path_filter = arguments.get("path")

        # Use shared implementation
        response_data = await search_regex_impl(
            database=_database,
            pattern=pattern,
            page_size=page_size,
            offset=offset,
            path_filter=path_filter,
        )

        # Apply response size limiting
        limited_response = limit_response_size(response_data)
        response_text = json.dumps(limited_response, default=str)

        # Final safety check - ensure we never exceed MCP limit
        if estimate_tokens(response_text) > MAX_ALLOWED_TOKENS:
            # Emergency fallback - return minimal response
            emergency_response = {
                "results": [],
                "pagination": {
                    "offset": offset,
                    "page_size": 0,
                    "has_more": True,
                    "total": limited_response["pagination"].get("total", 0),
                },
            }
            response_text = json.dumps(emergency_response, default=str)

        return [types.TextContent(type="text", text=response_text)]

    elif name == "search_semantic":
        query = arguments.get("query", "")
        page_size = arguments.get("page_size", 10)
        offset = arguments.get("offset", 0)
        provider = arguments.get("provider")
        model = arguments.get("model")
        threshold = arguments.get("threshold")
        path_filter = arguments.get("path")

        # Use shared implementation
        try:
            if not _database:
                raise Exception("Database not initialized")
            if not _embedding_manager:
                raise Exception("No embedding providers available")

            response_data = await search_semantic_impl(
                database=_database,
                embedding_manager=_embedding_manager,
                query=query,
                page_size=page_size,
                offset=offset,
                provider=provider,
                model=model,
                threshold=threshold,
                path_filter=path_filter,
            )

            # Apply response size limiting
            limited_response = limit_response_size(response_data)
            response_text = json.dumps(limited_response, default=str)

            # Final safety check - ensure we never exceed MCP limit
            if estimate_tokens(response_text) > 25000:
                # Emergency fallback - return minimal response
                emergency_response = {
                    "results": [],
                    "pagination": {
                        "offset": offset,
                        "page_size": 0,
                        "has_more": True,
                        "total": limited_response["pagination"].get("total", 0),
                    },
                }
                response_text = json.dumps(emergency_response, default=str)

            return [types.TextContent(type="text", text=response_text)]

        except asyncio.TimeoutError:
            # Handle MCP timeout gracefully with informative error
            raise Exception(
                "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
            )

    elif name == "search_fuzzy":
        query = arguments.get("query", "")
        page_size = max(1, min(arguments.get("page_size", 10), 100))
        offset = max(0, arguments.get("offset", 0))
        max_tokens = max(1000, min(arguments.get("max_response_tokens", 20000), 25000))
        path_filter = arguments.get("path")

        # Check connection instead of forcing reconnection (fixes race condition)
        if _database and not _database.is_connected():
            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(
                #     "Database not connected, reconnecting before fuzzy search",
                #     file=sys.stderr,
                # )
                pass
            _database.reconnect()

        # Check if provider supports fuzzy search
        if not hasattr(_database._provider, "search_fuzzy"):
            raise Exception("Fuzzy search not supported by current database provider")

        results, pagination = _database._provider.search_fuzzy(
            query=query, page_size=page_size, offset=offset, path_filter=path_filter
        )

        # Format response with pagination metadata
        response_data = {"results": results, "pagination": pagination}

        # Apply response size limiting
        limited_response = limit_response_size(response_data, max_tokens)
        response_text = json.dumps(limited_response, default=str)

        # Final safety check - ensure we never exceed MCP limit
        if estimate_tokens(response_text) > MAX_ALLOWED_TOKENS:
            # Emergency fallback - return minimal response
            emergency_response = {
                "results": [],
                "pagination": {
                    "offset": offset,
                    "page_size": 0,
                    "has_more": True,
                    "total": limited_response["pagination"].get("total", 0),
                },
            }
            response_text = json.dumps(emergency_response, default=str)

        return [types.TextContent(type="text", text=response_text)]

    elif name == "get_stats":
        # Use shared implementation
        if not _database:
            raise Exception("Database not initialized")

        stats = await get_stats_impl(_database)
        return [
            types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False))
        ]

    elif name == "health_check":
        # Use shared implementation
        if not _database:
            raise Exception("Database not initialized")
        if not _embedding_manager:
            raise Exception("No embedding providers available")

        health_status = await health_check_impl(_database, _embedding_manager)
        return [
            types.TextContent(
                type="text", text=json.dumps(health_status, ensure_ascii=False)
            )
        ]

    else:
        raise ValueError(f"Tool not found: {name}")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List tools based on what the database provider supports."""
    # Wait for server initialization to complete
    try:
        await asyncio.wait_for(_initialization_complete.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        pass

    tools = []

    # Always available tools
    tools.extend(
        [
            types.Tool(
                name="get_stats",
                description="Get database statistics including file, chunk, and embedding counts",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="health_check",
                description="Check server health status",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
    )

    # Check provider capabilities and add supported tools
    if _database and hasattr(_database, "_provider"):
        provider = _database._provider

        # Check semantic search support
        if provider.supports_semantic_search():
            tools.append(
                types.Tool(
                    name="search_semantic",
                    description="Search code using semantic similarity with pagination support.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language search query",
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Number of results per page (1-100)",
                                "default": 10,
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position for pagination",
                                "default": 0,
                            },
                            "max_response_tokens": {
                                "type": "integer",
                                "description": "Maximum response size in tokens (1000-25000)",
                                "default": 20000,
                            },
                            "provider": {
                                "type": "string",
                                "description": "Embedding provider to use",
                                "default": "openai",
                            },
                            "model": {
                                "type": "string",
                                "description": "Embedding model to use",
                                "default": "text-embedding-3-small",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Distance threshold for filtering results (optional)",
                            },
                            "path": {
                                "type": "string",
                                "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                            },
                        },
                        "required": ["query"],
                    },
                )
            )

        # Check regex search support
        if provider.supports_regex_search():
            tools.append(
                types.Tool(
                    name="search_regex",
                    description="Search code chunks using regex patterns with pagination support.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Regular expression pattern to search for",
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Number of results per page (1-100)",
                                "default": 10,
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position for pagination",
                                "default": 0,
                            },
                            "max_response_tokens": {
                                "type": "integer",
                                "description": "Maximum response size in tokens (1000-25000)",
                                "default": 20000,
                            },
                            "path": {
                                "type": "string",
                                "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                            },
                        },
                        "required": ["pattern"],
                    },
                )
            )

        # Check fuzzy search support
        if provider.supports_fuzzy_search():
            tools.append(
                types.Tool(
                    name="search_fuzzy",
                    description="Perform fuzzy text search using advanced text matching capabilities.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Text query to search for using fuzzy matching",
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Number of results per page (1-100)",
                                "default": 10,
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position for pagination",
                                "default": 0,
                            },
                            "max_response_tokens": {
                                "type": "integer",
                                "description": "Maximum response size in tokens (1000-25000)",
                                "default": 20000,
                            },
                            "path": {
                                "type": "string",
                                "description": "Optional relative path to limit search scope (e.g., 'src/', 'tests/')",
                            },
                        },
                        "required": ["query"],
                    },
                )
            )

    return tools


def send_error_response(
    message_id: Any, code: int, message: str, data: dict | None = None
) -> None:
    """Send a JSON-RPC error response to stdout."""
    error_response = {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message, "data": data},
    }
    print(json.dumps(error_response, ensure_ascii=False), flush=True)


def validate_mcp_initialize_message(
    message_text: str,
) -> tuple[bool, dict | None, str | None]:
    """
    Validate MCP initialize message for common protocol issues.
    Returns (is_valid, parsed_message, error_description)
    """
    try:
        message = json.loads(message_text.strip())
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {str(e)}"

    if not isinstance(message, dict):
        return False, None, "Message must be a JSON object"

    # Check required JSON-RPC fields
    if message.get("jsonrpc") != "2.0":
        return (
            False,
            message,
            f"Invalid jsonrpc version: '{message.get('jsonrpc')}' (must be '2.0')",
        )

    if message.get("method") != "initialize":
        return True, message, None  # Only validate initialize messages

    # Validate initialize method specifically
    params = message.get("params", {})
    if not isinstance(params, dict):
        return False, message, "Initialize method 'params' must be an object"

    missing_fields = []
    if "protocolVersion" not in params:
        missing_fields.append("protocolVersion")
    if "capabilities" not in params:
        missing_fields.append("capabilities")
    if "clientInfo" not in params:
        missing_fields.append("clientInfo")

    if missing_fields:
        return (
            False,
            message,
            f"Initialize method missing required fields: {', '.join(missing_fields)}",
        )

    return True, message, None


def provide_mcp_example() -> dict[str, Any]:
    """Provide a helpful example of correct MCP initialize message."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "your-mcp-client", "version": "1.0.0"},
        },
    }


async def handle_mcp_with_validation() -> None:
    """Handle MCP with improved error messages for protocol issues."""
    try:
        # Use the official MCP Python SDK stdio server pattern
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            # Initialize with lifespan context
            try:
                # Debug output to help diagnose initialization issues
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print("MCP server: Starting server initialization", file=sys.stderr)

                    pass
                async with server_lifespan(server) as server_context:
                    # Initialize the server
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        # print(
                        #     "MCP server: Server lifespan established, running server...",
                        #     file=sys.stderr,
                        # )

                        pass
                    try:
                        await server.run(
                            read_stream,
                            write_stream,
                            InitializationOptions(
                                server_name="ChunkHound Code Search",
                                server_version=__version__,
                                capabilities=server.get_capabilities(
                                    notification_options=NotificationOptions(),
                                    experimental_capabilities={},
                                ),
                            ),
                        )

                        if "CHUNKHOUND_DEBUG" in os.environ:
                            # print(
                            #     "MCP server: Server.run() completed, entering keepalive mode",
                            #     file=sys.stderr,
                            # )

                            pass
                        # Keep the process alive until client disconnects
                        # The MCP SDK handles the connection lifecycle, so we just need to wait
                        # for the server to be terminated by the client or signal
                        try:
                            # Wait indefinitely - the MCP SDK will handle cleanup when client disconnects
                            await asyncio.Event().wait()
                        except (asyncio.CancelledError, KeyboardInterrupt):
                            if "CHUNKHOUND_DEBUG" in os.environ:
                                # print(
                                #     "MCP server: Received shutdown signal",
                                #     file=sys.stderr,
                                # )
                                pass
                        except Exception:
                            if "CHUNKHOUND_DEBUG" in os.environ:
                                # print(
                                #     f"MCP server unexpected error: {e}", file=sys.stderr
                                # )
                                pass

                                # traceback.print_exc(file=sys.stderr)
                    except Exception:
                        if "CHUNKHOUND_DEBUG" in os.environ:
                            # print(
                            #     f"MCP server.run() error: {server_run_error}",
                            #     file=sys.stderr,
                            # )
                            pass

                            # traceback.print_exc(file=sys.stderr)
                        raise
            except Exception:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     f"MCP server lifespan error: {lifespan_error}", file=sys.stderr
                    # )
                    pass

                    # traceback.print_exc(file=sys.stderr)
                raise
    except Exception as e:
        # Analyze error for common protocol issues with recursive search
        error_details = str(e)
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print(f"MCP server top-level error: {e}", file=sys.stderr)
            pass

            # traceback.print_exc(file=sys.stderr)

        def find_validation_error(error: Exception, depth: int = 0) -> tuple[bool, str]:
            """Recursively search for ValidationError in exception chain."""
            if depth > 10:  # Prevent infinite recursion
                return False, ""

            error_str = str(error).lower()

            # Check for validation error indicators
            validation_keywords = [
                "protocolversion",
                "field required",
                "validation error",
                "validationerror",
                "literal_error",
                "input should be",
                "missing",
                "pydantic",
            ]

            if any(keyword in error_str for keyword in validation_keywords):
                return True, str(error)

            # Check exception chain
            if hasattr(error, "__cause__") and error.__cause__:
                found, details = find_validation_error(error.__cause__, depth + 1)
                if found:
                    return found, details

            if hasattr(error, "__context__") and error.__context__:
                found, details = find_validation_error(error.__context__, depth + 1)
                if found:
                    return found, details

            # Check exception groups (anyio/asyncio task groups)
            if hasattr(error, "exceptions") and error.exceptions:
                for exc in error.exceptions:
                    found, details = find_validation_error(exc, depth + 1)
                    if found:
                        return found, details

            return False, ""

        def extract_taskgroup_details(error: Exception, depth: int = 0) -> list[str]:
            """Extract detailed information from TaskGroup errors."""
            if depth > 10:  # Prevent infinite recursion
                return []

            details = []

            # Add current error details
            details.append(f"Level {depth}: {type(error).__name__}: {str(error)}")

            # Check exception chain
            if hasattr(error, "__cause__") and error.__cause__:
                details.extend(extract_taskgroup_details(error.__cause__, depth + 1))

            if hasattr(error, "__context__") and error.__context__:
                details.extend(extract_taskgroup_details(error.__context__, depth + 1))

            # Check exception groups (anyio/asyncio task groups)
            if hasattr(error, "exceptions") and error.exceptions:
                for i, exc in enumerate(error.exceptions):
                    details.append(f"TaskGroup exception {i + 1}:")
                    details.extend(extract_taskgroup_details(exc, depth + 1))

            return details

        is_validation_error, validation_details = find_validation_error(e)
        if validation_details:
            error_details = validation_details

        if is_validation_error:
            # Send helpful protocol validation error
            send_error_response(
                1,  # Assume initialize request
                -32602,
                "Invalid MCP protocol message",
                {
                    "details": "The MCP initialization message is missing required fields or has invalid format.",
                    "common_issue": "Missing 'protocolVersion' field in initialize request parameters",
                    "required_fields": [
                        "protocolVersion",
                        "capabilities",
                        "clientInfo",
                    ],
                    "correct_example": provide_mcp_example(),
                    "validation_error": error_details,
                    "help": [
                        "Ensure your MCP client includes 'protocolVersion': '2024-11-05'",
                        "Include all required fields in the initialize request",
                        "Verify your MCP client library is up to date",
                    ],
                },
            )
        else:
            # Handle other initialization or runtime errors
            # Extract detailed TaskGroup information for debugging
            taskgroup_details = extract_taskgroup_details(e)

            send_error_response(
                None,
                -32603,
                "MCP server error",
                {
                    "details": str(e),
                    "suggestion": "Check that the database path is accessible and environment variables are correct.",
                    "taskgroup_analysis": taskgroup_details,
                    "error_type": type(e).__name__,
                },
            )


async def main(args: argparse.Namespace | None = None) -> None:
    """Main entry point for the MCP server with robust error handling.

    Args:
        args: Pre-parsed arguments. If None, will parse from sys.argv.
    """
    import argparse

    if args is None:
        # Direct invocation - parse arguments
        parser = argparse.ArgumentParser(
            description="ChunkHound MCP stdio server",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # Add common MCP arguments
        add_common_mcp_arguments(parser)

        # Parse arguments
        args = parser.parse_args()

    # Create and store Config globally for use in server_lifespan
    global _config
    if args:
        config, validation_errors = create_validated_config(args, "mcp")
        if validation_errors:
            # Log validation errors but continue (MCP server can work with partial config)
            debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
            if debug_mode:
                for error in validation_errors:
                    print(f"[MCP-SERVER] Config validation warning: {error}", file=sys.stderr)
        _config = config
    else:
        _config = create_default_config()

    await handle_mcp_with_validation()


# Global to store Config for server_lifespan
_config: Config | None = None


if __name__ == "__main__":
    asyncio.run(main())
