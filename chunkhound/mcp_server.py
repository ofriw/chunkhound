#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol
"""

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
except ImportError:
    pass

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

        print(f"DEBUG: Initializing database at {db_path}")
        _database = Database(db_path)
        try:
            _database.connect()
            print("DEBUG: Database connected successfully")
        except Exception as db_exc:
            print(f"DEBUG ERROR: Database connection failed: {db_exc}")
            print(f"DEBUG ERROR: Exception type: {type(db_exc).__name__}")
            import traceback
            print(f"DEBUG ERROR: Traceback: {traceback.format_exc()}")
            raise
        
        # Setup signal coordination for process coordination
        print("DEBUG: Setting up signal coordination")
        setup_signal_coordination(db_path, _database)
        print("DEBUG: Signal coordination setup complete")
        
        # Initialize embedding manager
        print("DEBUG: Initializing embedding manager")
        _embedding_manager = EmbeddingManager()
        
        # Try to register OpenAI provider as default (optional)
        try:
            try:
                from .embeddings import create_openai_provider
            except ImportError:
                from embeddings import create_openai_provider
            openai_provider = create_openai_provider()
            _embedding_manager.register_provider(openai_provider, set_default=True)
            print("DEBUG: OpenAI provider registered successfully")
        except Exception as emb_exc:
            print(f"DEBUG: OpenAI provider registration failed: {emb_exc}")
            # Silently fail - MCP server will run without semantic search capabilities
            pass
        
        # Initialize filesystem watcher with offline catch-up
        print("DEBUG: Initializing file watcher")
        _file_watcher = FileWatcherManager()
        try:
            await _file_watcher.initialize(process_file_change)
            print("DEBUG: File watcher initialized successfully")
        except Exception as fw_exc:
            print(f"DEBUG: File watcher initialization failed: {fw_exc}")
            # Silently fail - MCP server will run without filesystem watching
            pass
        
        print("DEBUG: All initialization complete, yielding context")
        yield {"db": _database, "embeddings": _embedding_manager, "watcher": _file_watcher}
        print("DEBUG: Context yielded successfully")
        
    except Exception as e:
        print(f"DEBUG CRITICAL ERROR: Initialization failed: {e}")
        print(f"DEBUG CRITICAL ERROR: Exception type: {type(e).__name__}")
        import traceback
        print(f"DEBUG CRITICAL ERROR: Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to initialize database and embeddings: {e}")
    finally:
        # Cleanup coordination files
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
    
    if not _database:
        return
    
    try:
        logger.debug(f"Processing file change: {file_path} (event_type={event_type})")
        
        if event_type == 'deleted':
            # Remove file from database with cleanup tracking
            logger.debug(f"Deleting file completely: {file_path}")
            result = _database.delete_file_completely(str(file_path))
            logger.debug(f"File deletion result: {result}")
        else:
            # Process file (created, modified, moved)
            if file_path.exists() and file_path.is_file():
                # Get file stats for debugging
                try:
                    file_stat = file_path.stat()
                    current_mtime = file_stat.st_mtime
                    size_bytes = file_stat.st_size
                    logger.debug(f"File stats: {file_path} (mtime={current_mtime}, size={size_bytes} bytes)")
                    
                    # Check if file exists in database
                    existing_file = _database.get_file_by_path(str(file_path))
                    if existing_file:
                        logger.debug(f"File exists in database: {file_path} (database mtime={existing_file.get('mtime', 'unknown')})")
                    else:
                        logger.debug(f"New file, not in database yet: {file_path}")
                except Exception as e:
                    logger.debug(f"Error getting file stats: {e}")
                
                # Use incremental processing for 10-100x performance improvement
                logger.debug(f"Starting incremental processing for: {file_path}")
                result = await _database.process_file_incremental(file_path=file_path)
                logger.debug(f"Incremental processing result: {result}")
    except Exception as e:
        # Log error but don't crash the MCP server
        logger.error(f"Error processing file change {file_path} ({event_type}): {e}")


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
            results = _database.search_regex(pattern=pattern, limit=limit)
            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
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
            result = await _embedding_manager.embed_texts([query], provider)
            query_vector = result.embeddings[0]
            
            results = _database.search_semantic(
                query_vector=query_vector,
                provider=provider,
                model=model,
                limit=limit,
                threshold=threshold
            )
            
            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
            raise Exception(f"Semantic search failed: {str(e)}")
    
    elif name == "get_stats":
        try:
            stats = _database.get_stats()
            return [types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False))]
        except Exception as e:
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
        print("DEBUG: Starting MCP server with validation")
        # Use the official MCP Python SDK stdio server pattern
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            print("DEBUG: Stdio server initialized, streams ready")
            # Initialize with lifespan context
            print("DEBUG: Entering server_lifespan context")
            try:
                async with server_lifespan(server) as _:
                    print("DEBUG: Lifespan context active, server ready to run")
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
                print(f"DEBUG CRITICAL ERROR: Error in lifespan: {lifespan_error}")
                print(f"DEBUG CRITICAL ERROR: Lifespan error type: {type(lifespan_error).__name__}")
                import traceback
                print(f"DEBUG CRITICAL ERROR: Lifespan traceback: {traceback.format_exc()}")
                raise
    except Exception as e:
        # Analyze error for common protocol issues with recursive search
        error_str = str(e).lower()
        error_details = str(e)
        
        print(f"DEBUG ERROR: MCP server error: {error_str}")
        print(f"DEBUG ERROR: Error type: {type(e).__name__}")
        import traceback
        print(f"DEBUG ERROR: Full traceback: {traceback.format_exc()}")
        
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