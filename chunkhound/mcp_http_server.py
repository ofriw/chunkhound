#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP
"""

import asyncio
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from chunkhound.version import __version__

# Import dependencies (with relative imports fallback)
try:
    from .core.config import EmbeddingProviderFactory
    from .core.config.config import Config
    from .api.cli.utils.config_helpers import validate_config_for_command
    from .database import Database
    from .database_factory import create_database_with_dependencies
    from .embeddings import EmbeddingManager
    from .file_watcher import FileWatcherManager
    from .periodic_indexer import PeriodicIndexManager
    from .process_detection import ProcessDetector
    from .signal_coordinator import SignalCoordinator
    from .task_coordinator import TaskCoordinator
    from .utils.project_detection import find_project_root
except ImportError:
    from chunkhound.core.config import EmbeddingProviderFactory
    from chunkhound.core.config.config import Config
    from chunkhound.api.cli.utils.config_helpers import validate_config_for_command
    from chunkhound.database import Database
    from chunkhound.database_factory import create_database_with_dependencies
    from chunkhound.embeddings import EmbeddingManager
    from chunkhound.file_watcher import FileWatcherManager
    from chunkhound.periodic_indexer import PeriodicIndexManager
    from chunkhound.process_detection import ProcessDetector
    from chunkhound.signal_coordinator import SignalCoordinator
    from chunkhound.task_coordinator import TaskCoordinator
    from chunkhound.utils.project_detection import find_project_root

# Global components - initialized lazily
_database: Database | None = None
_embedding_manager: EmbeddingManager | None = None
_file_watcher: FileWatcherManager | None = None
_task_coordinator: TaskCoordinator | None = None
_periodic_indexer: PeriodicIndexManager | None = None
_signal_coordinator: SignalCoordinator | None = None
_initialization_lock = None
_server_config: "Config" | None = None  # Store initial config for consistency


async def ensure_initialization():
    """Ensure components are initialized (lazy initialization)"""
    global _database, _embedding_manager, _file_watcher, _task_coordinator, _periodic_indexer, _signal_coordinator, _initialization_lock, _server_config
    
    if _database is not None and _embedding_manager is not None:
        return
    
    # Create lock on first use
    if _initialization_lock is None:
        _initialization_lock = asyncio.Lock()
    
    async with _initialization_lock:
        if _database is not None and _embedding_manager is not None:
            return
        
        # Set MCP mode to suppress stderr output that interferes with JSON-RPC
        os.environ["CHUNKHOUND_MCP_MODE"] = "1"
        
        # Check debug flag from environment
        debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
        
        try:
            # Always detect project root using unified logic
            project_root = find_project_root()
            
            # Load configuration with unified project detection
            # Must match stdio server pattern for consistency
            config = Config(target_dir=project_root)  # Always use detected project root
            # Store config globally for file change processing consistency
            _server_config = config
            debug_mode = config.debug or debug_mode
            
            # Validate configuration for MCP HTTP server
            # This ensures same validation as stdio server and CLI
            try:
                # Validate configuration for MCP server
                validation_errors = config.validate_for_command("mcp")
                if validation_errors and debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass
            except Exception as validation_error:
                if debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass
            
            # Get database path from config
            db_path = Path(config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check for existing MCP server instances
            process_detector = ProcessDetector(db_path)
            existing_server = process_detector.find_mcp_server()
            
            if existing_server:
                raise Exception(
                    f"Another ChunkHound MCP server is already running for database '{db_path}' "
                    f"(PID {existing_server['pid']}). Only one MCP server instance per database is allowed. "
                    f"Please stop the existing server first or use a different database path."
                )
            
            # Register this MCP server instance
            process_detector.register_mcp_server(os.getpid())
            
            # Initialize embedding manager
            _embedding_manager = EmbeddingManager()
            
            # Setup embedding provider (optional - continue if it fails)
            try:
                provider = EmbeddingProviderFactory.create_provider(config.embedding)
                _embedding_manager.register_provider(provider, set_default=True)
            except (ValueError, Exception) as e:
                # API key or configuration issue - continue without embedding provider
                if debug_mode:
                    print(f"Embedding provider setup failed: {e}", file=sys.stderr)
            
            # Create database using unified factory for consistency with stdio server
            # This ensures same initialization across all MCP servers
            _database = create_database_with_dependencies(
                db_path=db_path,
                config=config,
                embedding_manager=_embedding_manager,
            )
            
            # Connect to database
            _database.connect()
            
            # Setup signal coordination
            _signal_coordinator = SignalCoordinator(db_path, _database)
            _signal_coordinator.setup_mcp_signal_handling_no_register()
            
            # Initialize task coordinator
            _task_coordinator = TaskCoordinator(max_queue_size=1000)
            await _task_coordinator.start()
            
            # Initialize file watcher for HTTP server
            try:
                _file_watcher = FileWatcherManager()
                # Enable file watcher for HTTP server to support real-time updates
                watcher_success = await _file_watcher.initialize(process_file_change)
            except Exception as fw_error:
                # Non-fatal for HTTP server
                if debug_mode:
                    print(f"File watcher initialization skipped: {fw_error}", file=sys.stderr)
                _file_watcher = None
            
            # Initialize periodic indexer (optional)
            try:
                indexing_coordinator = _database._indexing_coordinator
                _periodic_indexer = PeriodicIndexManager.from_environment(
                    indexing_coordinator=indexing_coordinator,
                    task_coordinator=_task_coordinator,
                )
                await _periodic_indexer.start()
            except Exception as pi_error:
                # Non-fatal error - continue without periodic indexing
                if debug_mode:
                    print(f"Periodic indexer initialization failed: {pi_error}", file=sys.stderr)
                _periodic_indexer = None
                
        except Exception as e:
            raise Exception(f"Failed to initialize database and embeddings: {e}")


async def process_file_change(file_path: Path, event_type: str):
    """
    Process a file change event by updating the database.
    
    This function is called by the filesystem watcher when files change.
    Uses the task coordinator to ensure file processing doesn't block search operations.
    """
    from chunkhound.file_watcher import debug_log
    
    debug_log("http_process_file_change_entry", file_path=str(file_path), event_type=event_type)
    
    global _database, _embedding_manager, _task_coordinator
    
    if not _database:
        return
    
    async def _execute_file_processing():
        """Execute the actual file processing logic."""
        try:
            if event_type == "deleted":
                # Remove file and its chunks using same approach as CLI indexer
                # This ensures consistent transaction handling and prevents race conditions
                removed_chunks = await _database._indexing_coordinator.remove_file(str(file_path))
                
                # Log deletion result for debugging
                debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
                if debug_mode and removed_chunks > 0:
                    print(f"[MCP-HTTP-SERVER] Removed {removed_chunks} chunks from deleted file: {file_path}", file=sys.stderr)
            else:
                # Process file (created, modified, moved)
                if file_path.exists() and file_path.is_file():
                    # Check if file should be excluded before processing
                    # Use stored server config for consistency
                    exclude_patterns = _server_config.indexing.exclude or []
                    
                    from fnmatch import fnmatch
                    
                    should_exclude = False
                    
                    # Get relative path for pattern matching
                    try:
                        project_root = find_project_root()
                        rel_path = file_path.relative_to(project_root)
                    except ValueError:
                        rel_path = file_path
                    
                    # Check exclude patterns
                    for pattern in exclude_patterns:
                        if fnmatch(str(rel_path), pattern):
                            should_exclude = True
                            break
                    
                    if not should_exclude:
                        # Process file through IndexingCoordinator for atomic transaction handling
                        result = await _database._indexing_coordinator.process_file(file_path)
                        
                        # Handle processing results with same logic as CLI indexer
                        if result["status"] not in ["success", "up_to_date", "skipped", "no_content", "no_chunks"]:
                            # Log processing errors for debugging
                            debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
                            if debug_mode:
                                print(f"[MCP-HTTP-SERVER] File processing failed: {result}", file=sys.stderr)
        except Exception as e:
            # Log error but don't crash the server
            debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
            if debug_mode:
                print(f"Error processing file {file_path}: {e}", file=sys.stderr)
    
    # Execute file processing
    if _task_coordinator:
        await _task_coordinator.add_task(_execute_file_processing())
    else:
        await _execute_file_processing()


# Initialize FastMCP 2.0 server
mcp = FastMCP("ChunkHound Code Search")


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """Get database statistics including file, chunk, and embedding counts"""
    await ensure_initialization()
    
    if not _database:
        raise Exception("Database not initialized")
    
    return _database.get_stats()


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check server health status"""
    await ensure_initialization()
    
    health_status = {
        "status": "healthy",
        "version": __version__,
        "database_connected": _database is not None,
        "embedding_providers": [],
        "task_coordinator_running": _task_coordinator is not None,
        "file_watcher_active": _file_watcher is not None,
        "periodic_indexer_running": _periodic_indexer is not None,
    }
    
    if _embedding_manager:
        health_status["embedding_providers"] = _embedding_manager.list_providers()
    
    return health_status


@mcp.tool()
async def search_regex(
    pattern: str,
    page_size: int = 10,
    offset: int = 0,
    max_response_tokens: int = 20000,
    path: str | None = None,
) -> dict[str, Any]:
    """Search code chunks using regex patterns with pagination support."""
    await ensure_initialization()
    
    if not _database:
        raise Exception("Database not initialized")
    
    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)
    max_response_tokens = max(1000, min(max_response_tokens, 25000))
    
    # Perform search
    results, pagination = _database.search_regex(
        pattern=pattern,
        page_size=page_size,
        offset=offset,
        path_filter=path,
    )
    
    return {"results": results, "pagination": pagination}


@mcp.tool()
async def search_semantic(
    query: str,
    page_size: int = 10,
    offset: int = 0,
    max_response_tokens: int = 20000,
    provider: str | None = None,
    model: str | None = None,
    threshold: float | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Search code using semantic similarity with pagination support."""
    await ensure_initialization()
    
    if not _database or not _embedding_manager:
        raise Exception("Database or embedding manager not initialized")
    
    if not _embedding_manager.list_providers():
        raise Exception(
            "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
        )
    
    # Use explicit provider/model from arguments, otherwise get from configured provider
    if not provider or not model:
        try:
            default_provider_obj = _embedding_manager.get_provider()
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
    max_response_tokens = max(1000, min(max_response_tokens, 25000))
    
    # Get embedding for query
    try:
        result = await asyncio.wait_for(
            _embedding_manager.embed_texts([query], provider), timeout=12.0
        )
        query_vector = result.embeddings[0]
    except asyncio.TimeoutError:
        raise Exception(
            "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
        )
    
    # Perform search
    results, pagination = _database.search_semantic(
        query_vector=query_vector,
        provider=provider,
        model=model,
        page_size=page_size,
        offset=offset,
        threshold=threshold,
        path_filter=path,
    )
    
    return {"results": results, "pagination": pagination}


def is_main_thread() -> bool:
    """Check if running in main thread"""
    return threading.current_thread() is threading.main_thread()


def main():
    """Main entry point for HTTP server"""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="ChunkHound MCP HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Set debug mode
    if args.debug:
        os.environ["CHUNKHOUND_DEBUG"] = "1"
    
    # Set MCP mode to suppress stderr output
    # os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    
    # Check if we're in main thread for signal handling
    if not is_main_thread():
        # Running in non-main thread, skip signal setup
        pass
    
    # Create HTTP app with proper JSON response configuration
    print(f"About to start FastMCP server on {args.host}:{args.port}", file=sys.stderr)
    
    # Create a new MCP instance for the HTTP app to avoid conflicts with module-level instance
    local_mcp = FastMCP("ChunkHound Code Search")
    
    # Register the same tools on the new instance
    @local_mcp.tool()
    async def get_stats_local() -> dict[str, Any]:
        """Get database statistics including file, chunk, and embedding counts"""
        await ensure_initialization()
        
        if not _database:
            raise Exception("Database not initialized")
        
        return _database.get_stats()
    
    @local_mcp.tool()
    async def health_check_local() -> dict[str, Any]:
        """Check server health status"""
        await ensure_initialization()
        
        health_status = {
            "status": "healthy",
            "version": __version__,
            "database_connected": _database is not None,
            "embedding_providers": [],
            "task_coordinator_running": _task_coordinator is not None,
            "file_watcher_active": _file_watcher is not None,
            "periodic_indexer_running": _periodic_indexer is not None,
        }
        
        if _embedding_manager:
            health_status["embedding_providers"] = _embedding_manager.list_providers()
        
        return health_status
    
    @local_mcp.tool()
    async def search_regex_local(
        pattern: str,
        page_size: int = 10,
        offset: int = 0,
        max_response_tokens: int = 20000,
        path: str | None = None,
    ) -> dict[str, Any]:
        """Search code chunks using regex patterns with pagination support."""
        await ensure_initialization()
        
        if not _database:
            raise Exception("Database not initialized")
        
        # Validate and constrain parameters
        page_size = max(1, min(page_size, 100))
        offset = max(0, offset)
        max_response_tokens = max(1000, min(max_response_tokens, 25000))
        
        # Perform search
        results, pagination = _database.search_regex(
            pattern=pattern,
            page_size=page_size,
            offset=offset,
            path_filter=path,
        )
        
        return {"results": results, "pagination": pagination}
    
    @local_mcp.tool()
    async def search_semantic_local(
        query: str,
        page_size: int = 10,
        offset: int = 0,
        max_response_tokens: int = 20000,
        provider: str | None = None,
        model: str | None = None,
        threshold: float | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        """Search code using semantic similarity with pagination support."""
        await ensure_initialization()
        
        if not _database or not _embedding_manager:
            raise Exception("Database or embedding manager not initialized")
        
        if not _embedding_manager.list_providers():
            raise Exception(
                "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
            )
        
        # Use explicit provider/model from arguments, otherwise get from configured provider
        if not provider or not model:
            try:
                default_provider_obj = _embedding_manager.get_provider()
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
        max_response_tokens = max(1000, min(max_response_tokens, 25000))
        
        # Get embedding for query
        try:
            result = await asyncio.wait_for(
                _embedding_manager.embed_texts([query], provider), timeout=12.0
            )
            query_vector = result.embeddings[0]
        except asyncio.TimeoutError:
            raise Exception(
                "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
            )
        
        # Perform search
        results, pagination = _database.search_semantic(
            query_vector=query_vector,
            provider=provider,
            model=model,
            page_size=page_size,
            offset=offset,
            threshold=threshold,
            path_filter=path,
        )
        
        return {"results": results, "pagination": pagination}
    
    # Use the correct FastMCP configuration for JSON responses
    app = local_mcp.http_app(
        path="/mcp",
        json_response=True,      # Force JSON responses instead of SSE
        stateless_http=True,     # Enable stateless HTTP for proper JSON-RPC
        transport="http"         # Use HTTP transport
    )
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()