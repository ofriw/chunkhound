#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol
"""

import threading
import time
import os
import json
import asyncio
import logging
import sys
from io import StringIO

from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from pydantic import ValidationError



# Disable all logging for MCP server to prevent interference with JSON-RPC
logging.disable(logging.CRITICAL)
for logger_name in ['', 'mcp', 'server', 'fastmcp']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

# Disable loguru logger used by database module
try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
    logger = loguru_logger
except ImportError:
    # Create a minimal logger fallback
    import logging
    logger = logging.getLogger(__name__)

try:
    from .database import Database
    from .embeddings import EmbeddingManager
    from .signal_coordinator import SignalCoordinator
    from .file_watcher import FileWatcherManager
except ImportError:
    # Handle running as standalone script
    from database import Database
    from embeddings import EmbeddingManager
    from signal_coordinator import SignalCoordinator
    from file_watcher import FileWatcherManager

# Global database, embedding manager, and file watcher instances
# Global state management
_database: Optional[Database] = None
_embedding_manager: Optional[EmbeddingManager] = None
_file_watcher: Optional[FileWatcherManager] = None

# CONNECTION_REFRESH_FIX: Global variables for connection refresh mechanism
_refresh_thread: Optional[threading.Thread] = None
_refresh_active = False
_refresh_interval = 3.0  # Refresh every 3 seconds

def _connection_refresh_worker():
    """Background worker that periodically refreshes database connection."""
    global _database, _refresh_active

    while _refresh_active:
        time.sleep(_refresh_interval)

        if _database and _database.is_connected():
            try:
                # Brief disconnect/reconnect cycle
                print(f"MCP_SERVER_DEBUG: Connection refresh cycle starting")
                db_path = _database.db_path if hasattr(_database, 'db_path') else 'Unknown'
                print(f"MCP_SERVER_DEBUG: Current database path: {db_path}")

                _database.disconnect()
                time.sleep(0.1)  # 100ms window for CLI access
                _database.reconnect()

                # Log stats after reconnection
                try:
                    stats = _database.get_stats()
                    print(f"MCP_SERVER_DEBUG: Post-refresh database stats: {stats}")
                except Exception as stats_e:
                    print(f"MCP_SERVER_DEBUG: Failed to get stats after refresh: {stats_e}")

            except Exception as e:
                # Log the error but continue
                print(f"MCP_SERVER_DEBUG: Connection refresh error: {e}")
                # Continue anyway - connection will be restored on next request
                pass

def _start_connection_refresh():
    """Start the connection refresh background thread."""
    global _refresh_thread, _refresh_active

    if _refresh_thread and _refresh_thread.is_alive():
        print("MCP_SERVER_DEBUG: Connection refresh thread already running")
        return

    _refresh_active = True
    _refresh_thread = threading.Thread(target=_connection_refresh_worker, daemon=True)
    _refresh_thread.start()
    print(f"MCP_SERVER_DEBUG: Connection refresh thread started: {_refresh_thread.is_alive()}")



def _stop_connection_refresh():
    """Stop the connection refresh background thread."""
    global _refresh_active, _refresh_thread

    _refresh_active = False
    if _refresh_thread:
        _refresh_thread.join(timeout=1.0)


_signal_coordinator: Optional[SignalCoordinator] = None

# Initialize MCP server with explicit stdio
server = Server("ChunkHound Code Search")


def setup_signal_coordination(db_path: Path, database: Database):
    """Setup signal coordination for process coordination."""
    global _signal_coordinator

    try:
        _signal_coordinator = SignalCoordinator(db_path, database)
        _signal_coordinator.setup_mcp_signal_handling()
        # Signal coordination initialized (logging disabled for MCP server)
    except Exception:
        # Failed to setup signal coordination (logging disabled for MCP server)
        raise


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    global _database, _embedding_manager, _file_watcher, _signal_coordinator

    try:
        # Initialize database path
        db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # DEBUG: Log database path information for QA testing bug investigation
        print(f"MCP_SERVER_DEBUG: Using database path: {db_path} (absolute: {db_path.absolute()})")
        print(f"MCP_SERVER_DEBUG: Database file exists: {db_path.exists()}")
        if db_path.exists():
            print(f"MCP_SERVER_DEBUG: Database file size: {db_path.stat().st_size} bytes")

        _database = Database(db_path)
        try:
            _database.connect()
            # DEBUG: Log database connection and stats
            print(f"MCP_SERVER_DEBUG: Database connected successfully")
            print(f"MCP_SERVER_DEBUG: Database stats: {_database.get_stats() if _database else 'None'}")

        except Exception as db_exc:
            print(f"MCP_SERVER_DEBUG: Database connection failed: {db_exc}")
            raise

        # Setup signal coordination for process coordination
        setup_signal_coordination(db_path, _database)

        # Initialize embedding manager
        _embedding_manager = EmbeddingManager()

        # Try to register OpenAI provider as default (optional)
        try:
            try:
                from .embeddings import create_openai_provider
            except ImportError:
                from embeddings import create_openai_provider
            openai_provider = create_openai_provider()
            _embedding_manager.register_provider(openai_provider, set_default=True)

        except Exception as emb_exc:
            # Silently fail - MCP server will run without semantic search capabilities
            pass

        # Initialize filesystem watcher with offline catch-up
        _file_watcher = FileWatcherManager()

        # Initialize file watcher with timeout protection to prevent IDE timeouts
        try:
            # Use asyncio.wait_for to prevent hanging during initialization
            await asyncio.wait_for(
                _file_watcher.initialize(process_file_change),
                timeout=5.0  # 5 second timeout to prevent IDE issues
            )
            print("MCP_SERVER_DEBUG: File watcher initialized successfully")
        except asyncio.TimeoutError:
            print("MCP_SERVER_DEBUG: File watcher initialization timed out, continuing without real-time indexing")
        except Exception as watcher_exc:
            print(f"MCP_SERVER_DEBUG: File watcher initialization failed: {watcher_exc}")

        # DEBUG: Check database state before yielding
        db_path = _database.db_path if hasattr(_database, 'db_path') else 'Unknown'
        print(f"MCP_SERVER_DEBUG: Pre-yield database path: {db_path}")
        print(f"MCP_SERVER_DEBUG: Pre-yield database connected: {_database.is_connected() if _database else False}")

        # CONNECTION_REFRESH_FIX: Delay connection refresh to avoid IDE timeout interference
        yield {"db": _database, "embeddings": _embedding_manager, "watcher": _file_watcher}

        # Force reconnection to ensure latest database state
        print("MCP_SERVER_DEBUG: Post-yield forcing database reconnection")
        if _database:
            try:
                _database.reconnect()
                print(f"MCP_SERVER_DEBUG: Forced reconnection stats: {_database.get_stats()}")
            except Exception as e:
                print(f"MCP_SERVER_DEBUG: Forced reconnection failed: {e}")

        # Start connection refresh after successful handshake (1 second delay - IDE timeout fix)
        await asyncio.sleep(1.0)
        _start_connection_refresh()


    except Exception as e:
        raise Exception(f"Failed to initialize database and embeddings: {e}")
    finally:
        # Cleanup coordination files
        # CONNECTION_REFRESH_FIX: Stop connection refresh
        _stop_connection_refresh()
        if _signal_coordinator:
            _signal_coordinator.cleanup_coordination_files()
            pass

        # Cleanup filesystem watcher
        if _file_watcher:
            try:
                await _file_watcher.cleanup()
            except Exception:
                pass

        # Cleanup database
        if _database:
            try:
                _database.close()
            except Exception:
                pass


async def process_file_change(file_path: Path, event_type: str):
    """
    Process a file change event by updating the database.

    This function is called by the filesystem watcher when files change.
    It runs in the main thread to ensure single-threaded database access.
    """
    global _database, _embedding_manager

    # DEBUG: Always log callback invocation to trace execution
    print(f"CALLBACK_DEBUG: process_file_change called at {time.time():.6f} - {event_type} {file_path}")

    if not _database:
        print(f"CALLBACK_DEBUG: No database available, returning early")
        return

    processing_start = time.time()
    try:
        print(f"CALLBACK_DEBUG: Processing started at {processing_start:.6f} - {event_type} {file_path}")
        logger.debug(f"TIMING: Processing started at {processing_start:.6f} - {event_type} {file_path}")

        if event_type == 'deleted':
            # Remove file from database with cleanup tracking
            # Normalize path to handle symlinks consistently (resolve /var -> /private/var on macOS)
            normalized_file_path = file_path.resolve()
            delete_start = time.time()
            logger.debug(f"TIMING: Delete operation started at {delete_start:.6f} - {file_path}")
            logger.debug(f"TIMING: Normalized path for deletion: {normalized_file_path}")
            result = _database.delete_file_completely(str(normalized_file_path))
            delete_end = time.time()
            logger.debug(f"TIMING: Delete completed at {delete_end:.6f} (took {delete_end - delete_start:.6f}s) - {file_path}")
            logger.debug(f"File deletion result: {result}")
        else:
            # Process file (created, modified, moved)
            if file_path.exists() and file_path.is_file():
                # Get file stats for debugging
                try:
                    file_stat = file_path.stat()
                    current_mtime = file_stat.st_mtime
                    size_bytes = file_stat.st_size
                    logger.debug(f"TIMING: File stats at {time.time():.6f} - {file_path} (mtime={current_mtime}, size={size_bytes} bytes)")

                    # Check if file exists in database
                    existing_file = _database.get_file_by_path(str(file_path))
                    if existing_file:
                        db_mtime = existing_file.get('mtime', 'unknown')
                        logger.debug(f"TIMING: File exists in database - {file_path} (database mtime={db_mtime})")
                        if isinstance(db_mtime, (int, float)) and isinstance(current_mtime, (int, float)):
                            mtime_diff = current_mtime - db_mtime
                            logger.debug(f"TIMING: Mtime difference: {mtime_diff:.6f}s (current={current_mtime:.6f}, db={db_mtime:.6f})")
                    else:
                        logger.debug(f"TIMING: New file, not in database yet - {file_path}")
                except Exception as e:
                    logger.debug(f"Error getting file stats: {e}")

                # Use incremental processing for 10-100x performance improvement
                process_start = time.time()
                logger.debug(f"TIMING: Incremental processing started at {process_start:.6f} - {file_path}")
                result = await _database.process_file_incremental(file_path=file_path)
                process_end = time.time()
                logger.debug(f"TIMING: Incremental processing completed at {process_end:.6f} (took {process_end - process_start:.6f}s) - {file_path}")
                logger.debug(f"Incremental processing result: {result}")

                # Check for errors and provide user notifications
                if result.get("status") == "error":
                    error_msg = result.get("error", "Unknown error")
                    if result.get("rollback_performed"):
                        logger.info(f"FILE INDEXING RECOVERED: {file_path} - Re-indexing failed but original content preserved: {error_msg}")
                        print(f"INDEXING RECOVERED: {file_path} - Original content preserved after indexing failure")
                    else:
                        logger.error(f"FILE INDEXING FAILED: {file_path} - {error_msg}")
                        print(f"INDEXING FAILED: {file_path} - {error_msg}")
                elif result.get("status") == "critical_error":
                    critical_error = result.get("error", "Unknown critical error")
                    logger.error(f"CRITICAL INDEXING ERROR: {file_path} - {critical_error}")
                    print(f"CRITICAL ERROR: {file_path} - Data may be lost - {critical_error}")
                elif result.get("status") == "success" and result.get("transaction_safe"):
                    chunks_inserted = result.get("chunks_inserted", 0)
                    chunks_deleted = result.get("chunks_deleted", 0)
                    logger.info(f"FILE INDEXING SUCCESS: {file_path} - {chunks_inserted} chunks indexed, {chunks_deleted} old chunks replaced")
    except Exception as e:
        # Log error but don't crash the MCP server
        print(f"CALLBACK_DEBUG: Error in process_file_change: {e}")
        logger.error(f"Error processing file change {file_path} ({event_type}): {e}")
        # Provide user-visible error notification
        print(f"FILE PROCESSING ERROR: {file_path} - {str(e)}")
    finally:
        processing_end = time.time()
        print(f"CALLBACK_DEBUG: Processing completed at {processing_end:.6f} (took {processing_end - processing_start:.6f}s)")
        logger.debug(f"TIMING: Total processing time: {processing_end - processing_start:.6f}s - {event_type} {file_path}")


def convert_to_ndjson(results: List[Dict[str, Any]]) -> str:
    """Convert search results to NDJSON format."""
    lines = []
    for result in results:
        lines.append(json.dumps(result, ensure_ascii=False))
    return "\n".join(lines)


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
    """Handle tool calls"""
    if not _database:
        if _signal_coordinator and _signal_coordinator.is_coordination_active():
            raise Exception("Database temporarily unavailable during coordination")
        else:
            raise Exception("Database not initialized")

    if name == "search_regex":
        pattern = arguments.get("pattern", "")
        limit = max(1, min(arguments.get("limit", 10), 100))

        try:
            # Force reconnection to ensure latest database state
            print(f"MCP_SERVER_DEBUG: Refreshing database connection for search_regex")
            _database.reconnect()

            results = _database.search_regex(pattern=pattern, limit=limit)
            stats = _database.get_stats()
            print(f"MCP_SERVER_DEBUG: search_regex stats after reconnect: {stats}")

            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
            print(f"MCP_SERVER_DEBUG: search_regex failed: {str(e)}")
            raise Exception(f"Search failed: {str(e)}")

    elif name == "search_semantic":
        query = arguments.get("query", "")
        limit = max(1, min(arguments.get("limit", 10), 100))
        provider = arguments.get("provider", "openai")
        model = arguments.get("model", "text-embedding-3-small")
        threshold = arguments.get("threshold")

        if not _embedding_manager or not _embedding_manager.list_providers():
            raise Exception("No embedding providers available. Set OPENAI_API_KEY to enable semantic search.")

        try:
            # Force reconnection to ensure latest database state
            print(f"MCP_SERVER_DEBUG: Refreshing database connection for search_semantic")
            _database.reconnect()

            result = await _embedding_manager.embed_texts([query], provider)
            query_vector = result.embeddings[0]

            results = _database.search_semantic(
                query_vector=query_vector,
                provider=provider,
                model=model,
                limit=limit,
                threshold=threshold
            )

            stats = _database.get_stats()
            print(f"MCP_SERVER_DEBUG: search_semantic stats after reconnect: {stats}")

            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
            print(f"MCP_SERVER_DEBUG: search_semantic failed: {str(e)}")
            raise Exception(f"Semantic search failed: {str(e)}")

    elif name == "get_stats":
        try:
            # Force reconnection to ensure latest database state
            print(f"MCP_SERVER_DEBUG: Refreshing database connection for get_stats")
            _database.reconnect()

            db_path = _database.db_path if hasattr(_database, 'db_path') else 'Unknown'
            print(f"MCP_SERVER_DEBUG: get_stats called, database path: {db_path}")
            print(f"MCP_SERVER_DEBUG: Database connected: {_database.is_connected() if _database else False}")

            stats = _database.get_stats()
            print(f"MCP_SERVER_DEBUG: get_stats result: {stats}")
            return [types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False))]
        except Exception as e:
            print(f"MCP_SERVER_DEBUG: get_stats error: {e}")
            raise Exception(f"Failed to get stats: {str(e)}")

    elif name == "health_check":
        health_status = {
            "status": "healthy",
            "version": "1.0.1",
            "database_connected": _database is not None,
            "embedding_providers": _embedding_manager.list_providers() if _embedding_manager else []
        }
        return [types.TextContent(type="text", text=json.dumps(health_status, ensure_ascii=False))]

    else:
        raise ValueError(f"Tool not found: {name}")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="search_regex",
            description="Search code using regular expression patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regular expression pattern to search for"},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (1-100)", "default": 10}
                },
                "required": ["pattern"]
            }
        ),
        types.Tool(
            name="search_semantic",
            description="Search code using semantic similarity (vector search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (1-100)", "default": 10},
                    "provider": {"type": "string", "description": "Embedding provider to use", "default": "openai"},
                    "model": {"type": "string", "description": "Embedding model to use", "default": "text-embedding-3-small"},
                    "threshold": {"type": "number", "description": "Distance threshold for filtering results (optional)"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_stats",
            description="Get database statistics including file, chunk, and embedding counts",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="health_check",
            description="Check server health status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


def send_error_response(message_id: Any, code: int, message: str, data: Optional[dict] = None):
    """Send a JSON-RPC error response to stdout."""
    error_response = {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
            "data": data
        }
    }
    print(json.dumps(error_response, ensure_ascii=False), flush=True)


def validate_mcp_initialize_message(message_text: str) -> Tuple[bool, Optional[dict], Optional[str]]:
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
        return False, message, f"Invalid jsonrpc version: '{message.get('jsonrpc')}' (must be '2.0')"

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
        return False, message, f"Initialize method missing required fields: {', '.join(missing_fields)}"

    return True, message, None


def provide_mcp_example():
    """Provide a helpful example of correct MCP initialize message."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "your-mcp-client",
                "version": "1.0.0"
            }
        }
    }


async def handle_mcp_with_validation():
    """Handle MCP with improved error messages for protocol issues."""
    try:

        # Use the official MCP Python SDK stdio server pattern
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):

            # Initialize with lifespan context

            try:
                async with server_lifespan(server) as _:

                    await server.run(
                        read_stream,
                        write_stream,
                        InitializationOptions(
                            server_name="ChunkHound Code Search",
                            server_version="1.0.1",
                            capabilities=server.get_capabilities(
                                notification_options=NotificationOptions(),
                                experimental_capabilities={},
                            ),
                        ),
                    )
            except Exception as lifespan_error:
                raise
    except Exception as e:
        # Analyze error for common protocol issues with recursive search
        error_str = str(e).lower()
        error_details = str(e)



        def find_validation_error(error, depth=0):
            """Recursively search for ValidationError in exception chain."""
            if depth > 10:  # Prevent infinite recursion
                return False, ""

            error_str = str(error).lower()

            # Check for validation error indicators
            validation_keywords = [
                'protocolversion', 'field required', 'validation error',
                'validationerror', 'literal_error', 'input should be',
                'missing', 'pydantic'
            ]

            if any(keyword in error_str for keyword in validation_keywords):
                return True, str(error)

            # Check exception chain
            if hasattr(error, '__cause__') and error.__cause__:
                found, details = find_validation_error(error.__cause__, depth + 1)
                if found:
                    return found, details

            if hasattr(error, '__context__') and error.__context__:
                found, details = find_validation_error(error.__context__, depth + 1)
                if found:
                    return found, details

            # Check exception groups (anyio/asyncio task groups)
            if hasattr(error, 'exceptions') and error.exceptions:
                for exc in error.exceptions:
                    found, details = find_validation_error(exc, depth + 1)
                    if found:
                        return found, details

            return False, ""

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
                    "required_fields": ["protocolVersion", "capabilities", "clientInfo"],
                    "correct_example": provide_mcp_example(),
                    "validation_error": error_details,
                    "help": [
                        "Ensure your MCP client includes 'protocolVersion': '2024-11-05'",
                        "Include all required fields in the initialize request",
                        "Verify your MCP client library is up to date"
                    ]
                }
            )
        else:
            # Handle other initialization or runtime errors
            send_error_response(
                None,
                -32603,
                "MCP server error",
                {
                    "details": str(e),
                    "suggestion": "Check that the database path is accessible and environment variables are correct."
                }
            )


async def main():
    """Main entry point for the MCP server with robust error handling."""
    await handle_mcp_with_validation()


if __name__ == "__main__":
    asyncio.run(main())
