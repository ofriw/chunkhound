"""ChunkHound CLI - Command-line interface for directory watching and indexing."""

import argparse
import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
import time
import yaml
from pathlib import Path
from typing import Optional

from loguru import logger

from . import __version__
from .database import Database
from .embeddings import EmbeddingManager, create_openai_provider, create_openai_compatible_provider, create_tei_provider
from .signal_coordinator import CLICoordinator
from .file_watcher import FileWatcherManager
from .config import get_config_manager, reset_config_manager, ServerConfig


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="chunkhound",
        description="Local-first semantic code search with vector and regex capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chunkhound run /path/to/project
  chunkhound run . --db ./chunks.duckdb
  chunkhound run /code --include "*.py" --exclude "*/tests/*"
        """,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"chunkhound {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command - main operation
    run_parser = subparsers.add_parser(
        "run",
        help="Watch directory and index code for search",
    )
    run_parser.add_argument(
        "path",
        type=Path,
        help="Directory path to watch and index",
    )
    run_parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".cache" / "chunkhound" / "chunks.duckdb",
        help="DuckDB database file path (default: ~/.cache/chunkhound/chunks.duckdb)",
    )

    run_parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="File patterns to include (can be specified multiple times)",
    )
    run_parser.add_argument(
        "--exclude",
        action="append", 
        default=[],
        help="File patterns to exclude (can be specified multiple times)",
    )
    run_parser.add_argument(
        "--debounce-ms",
        type=int,
        default=500,
        help="File change debounce time in milliseconds (default: 500)",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    run_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "openai-compatible", "tei"],
        help="Embedding provider to use (default: openai)",
    )
    run_parser.add_argument(
        "--model",
        help="Embedding model to use (defaults to provider default)",
    )
    run_parser.add_argument(
        "--api-key",
        help="API key for embedding provider (uses env var if not specified)",
    )
    run_parser.add_argument(
        "--base-url",
        help="Base URL for embedding API (uses env var if not specified)",
    )
    run_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation (index code only)",
    )
    run_parser.add_argument(
        "--watch",
        action="store_true",
        help="Enable continuous file watching and real-time indexing",
    )
    

    # MCP command - Model Context Protocol server
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Start MCP server for AI assistant integration (stdin/stdout)",
    )
    mcp_parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".cache" / "chunkhound" / "chunks.duckdb",
        help="Database file path",
    )
    mcp_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    # Config command - Configuration management
    config_parser = subparsers.add_parser(
        "config",
        help="Manage embedding server configurations",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Configuration commands")
    
    # Config list command
    list_parser = config_subparsers.add_parser(
        "list",
        help="List all configured servers",
    )
    list_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    list_parser.add_argument(
        "--show-health",
        action="store_true",
        help="Show health status for each server",
    )
    
    # Config add command
    add_parser = config_subparsers.add_parser(
        "add",
        help="Add a new embedding server",
    )
    add_parser.add_argument(
        "name",
        help="Server name",
    )
    add_parser.add_argument(
        "--type",
        required=True,
        choices=["openai", "openai-compatible", "tei"],
        help="Server type",
    )
    add_parser.add_argument(
        "--base-url",
        required=True,
        help="Server base URL",
    )
    add_parser.add_argument(
        "--model",
        help="Model name (auto-detected for TEI if not specified)",
    )
    add_parser.add_argument(
        "--api-key",
        help="API key for authentication",
    )
    add_parser.add_argument(
        "--default",
        action="store_true",
        help="Set as default server",
    )
    add_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    add_parser.add_argument(
        "--batch-size",
        type=int,
        help="Batch size for embeddings",
    )
    add_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    add_parser.add_argument(
        "--health-check-interval",
        type=int,
        default=300,
        help="Health check interval in seconds (default: 300)",
    )
    
    # Config remove command
    remove_parser = config_subparsers.add_parser(
        "remove",
        help="Remove an embedding server",
    )
    remove_parser.add_argument(
        "name",
        help="Server name to remove",
    )
    remove_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    
    # Config health command
    health_parser = config_subparsers.add_parser(
        "health",
        help="Check server health status",
    )
    health_parser.add_argument(
        "name",
        nargs="?",
        help="Server name to check (all servers if not specified)",
    )
    health_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    health_parser.add_argument(
        "--monitor",
        action="store_true",
        help="Start continuous health monitoring",
    )
    
    # Config test command
    test_parser = config_subparsers.add_parser(
        "test",
        help="Test embedding server connectivity",
    )
    test_parser.add_argument(
        "name",
        nargs="?",
        help="Server name to test (default server if not specified)",
    )
    test_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    test_parser.add_argument(
        "--text",
        default="test embedding",
        help="Text to use for embedding test (default: 'test embedding')",
    )
    
    # Config enable command
    enable_parser = config_subparsers.add_parser(
        "enable",
        help="Enable a server",
    )
    enable_parser.add_argument(
        "name",
        help="Server name to enable",
    )
    enable_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    
    # Config disable command
    disable_parser = config_subparsers.add_parser(
        "disable",
        help="Disable a server",
    )
    disable_parser.add_argument(
        "name",
        help="Server name to disable",
    )
    disable_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    
    # Config set-default command
    set_default_parser = config_subparsers.add_parser(
        "set-default",
        help="Set default server",
    )
    set_default_parser.add_argument(
        "name",
        help="Server name to set as default",
    )
    set_default_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    
    # Config validate command
    validate_parser = config_subparsers.add_parser(
        "validate",
        help="Validate configuration and all servers",
    )
    validate_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    validate_parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix validation issues automatically",
    )
    
    # Config benchmark command
    benchmark_parser = config_subparsers.add_parser(
        "benchmark",
        help="Benchmark server performance",
    )
    benchmark_parser.add_argument(
        "name",
        nargs="?",
        help="Server name to benchmark (all servers if not specified)",
    )
    benchmark_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    benchmark_parser.add_argument(
        "--samples",
        type=int,
        default=10,
        help="Number of test samples (default: 10)",
    )
    benchmark_parser.add_argument(
        "--batch-sizes",
        type=int,
        nargs="+",
        default=[1, 5, 10, 20],
        help="Batch sizes to test (default: 1 5 10 20)",
    )
    
    # Config switch command
    switch_parser = config_subparsers.add_parser(
        "switch",
        help="Switch to a different provider with validation",
    )
    switch_parser.add_argument(
        "name",
        help="Server name to switch to",
    )
    switch_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    switch_parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Validate server before switching (default: true)",
    )
    switch_parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Skip validation before switching",
    )
    
    # Config discover command
    discover_parser = config_subparsers.add_parser(
        "discover",
        help="Discover and validate configuration files",
    )
    discover_parser.add_argument(
        "--path",
        type=Path,
        help="Start discovery from this path (default: current directory)",
    )
    discover_parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all discovered paths, not just valid configs",
    )
    
    # Config export command
    export_parser = config_subparsers.add_parser(
        "export",
        help="Export configuration to file",
    )
    export_parser.add_argument(
        "output",
        help="Output file path",
    )
    export_parser.add_argument(
        "--config",
        type=Path,
        help="Source configuration file path",
    )
    export_parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Export format (default: yaml)",
    )
    
    # Config import command
    import_parser = config_subparsers.add_parser(
        "import",
        help="Import configuration from file",
    )
    import_parser.add_argument(
        "input",
        help="Input file path",
    )
    import_parser.add_argument(
        "--config",
        type=Path,
        help="Target configuration file path",
    )
    import_parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge with existing configuration",
    )
    import_parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup of existing config (default: true)",
    )
    
    # Config template command
    template_parser = config_subparsers.add_parser(
        "template",
        help="Generate configuration templates",
    )
    template_parser.add_argument(
        "--type",
        choices=["basic", "advanced", "local", "production"],
        default="basic",
        help="Template type (default: basic)",
    )
    template_parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (prints to stdout if not specified)",
    )
    
    # Config batch-test command
    batch_test_parser = config_subparsers.add_parser(
        "batch-test",
        help="Test all servers in parallel",
    )
    batch_test_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    batch_test_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Test timeout per server in seconds (default: 30)",
    )
    batch_test_parser.add_argument(
        "--text",
        default="test embedding",
        help="Text to use for embedding test (default: 'test embedding')",
    )
    
    return parser


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    logger.remove()  # Remove default handler
    
    log_level = "DEBUG" if verbose else "INFO"
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=log_format,
        level=log_level,
        colorize=True,
    )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""
    if args.command == "run":
        if not args.path.exists():
            logger.error(f"Path does not exist: {args.path}")
            sys.exit(1)
            
        if not args.path.is_dir():
            logger.error(f"Path is not a directory: {args.path}")
            sys.exit(1)
            
        # Validate provider-specific arguments
        if args.provider in ["openai-compatible", "tei"] and not args.base_url:
            logger.error(f"--base-url is required for {args.provider} provider")
            sys.exit(1)
            
        # Ensure database directory exists
        args.db.parent.mkdir(parents=True, exist_ok=True)
    
    elif args.command == "mcp":
        # Ensure database directory exists
        args.db.parent.mkdir(parents=True, exist_ok=True)



def mcp_command(args: argparse.Namespace) -> None:
    """Execute the MCP server command."""
    import os
    
    # Set database path in environment for MCP server
    os.environ["CHUNKHOUND_DB_PATH"] = str(args.db)
    
    # No logging output for MCP server - must maintain clean stdin/stdout for JSON-RPC
    
    # Import and run MCP server
    from .mcp_server import main as run_mcp_server
    asyncio.run(run_mcp_server())


# Legacy coordination functions are replaced by CLICoordinator class
# These are kept for backwards compatibility but delegate to CLICoordinator

def detect_mcp_server(db_path: str) -> Optional[int]:
    """Detect if an MCP server is running for the given database."""
    try:
        coordinator = CLICoordinator(Path(db_path))
        return coordinator.signal_coordinator.process_detector.get_server_pid()
    except Exception as e:
        logger.debug(f"Error detecting MCP server: {e}")
        return None


def coordinate_database_access(db_path: str, mcp_pid: int) -> bool:
    """Coordinate database access with MCP server."""
    try:
        coordinator = CLICoordinator(Path(db_path))
        return coordinator.request_database_access()
    except Exception as e:
        logger.warning(f"⚠️  Failed to coordinate with MCP server: {e}")
        return False


def restore_database_access(db_path: str, mcp_pid: int) -> None:
    """Restore database access to MCP server."""
    try:
        coordinator = CLICoordinator(Path(db_path))
        coordinator.release_database_access()
    except Exception as e:
        logger.warning(f"⚠️  Failed to restore database access: {e}")


async def run_command(args: argparse.Namespace) -> None:
    """Execute the run command."""
    logger.info(f"Starting ChunkHound v{__version__}")
    logger.info(f"Processing directory: {args.path}")
    logger.info(f"Database: {args.db}")
    
    # Initialize CLI coordinator for database access coordination
    cli_coordinator = CLICoordinator(Path(args.db))
    
    # Check for running MCP server and coordinate if needed
    if cli_coordinator.signal_coordinator.is_mcp_server_running():
        mcp_pid = cli_coordinator.signal_coordinator.process_detector.get_server_pid()
        logger.info(f"🔍 Detected running MCP server (PID {mcp_pid})")
        
        if not cli_coordinator.request_database_access():
            logger.error("❌ Failed to coordinate database access. Please stop the MCP server or use a different database file.")
            sys.exit(1)
    
    # Default file patterns for Python, Java, and C# files if none specified
    if not args.include:
        args.include = ["*.py", "*.java", "*.cs"]
    
    # Default exclusion patterns
    default_excludes = [
        "*/.git/*", ".git/*",
        "*/__pycache__/*", "__pycache__/*",
        "*/venv/*", "venv/*",
        "*/env/*", "env/*",
        "*/.venv/*", ".venv/*",
        "*/node_modules/*", "node_modules/*",
        "*/dist/*", "dist/*",
        "*/build/*", "build/*",
        # Python dependency directories
        "*/site-packages/*", "site-packages/*",
        "*/.tox/*", ".tox/*",
        "*/.pytest_cache/*", ".pytest_cache/*",
        "*/eggs/*", "eggs/*",
        "*/.eggs/*", ".eggs/*",
        "*/pip-cache/*", "pip-cache/*",
        "*/.mypy_cache/*", ".mypy_cache/*",
    ]
    args.exclude.extend(default_excludes)
    
    logger.info(f"Include patterns: {args.include}")
    logger.info(f"Exclude patterns: {args.exclude}")
    
    # Initialize embedding manager if embeddings are enabled
    embedding_manager = None
    if not args.no_embeddings:
        try:
            if args.provider == "openai":
                model = args.model or "text-embedding-3-small"
                provider = create_openai_provider(
                    api_key=args.api_key,
                    base_url=args.base_url,
                    model=model,
                )
                embedding_manager = EmbeddingManager()
                embedding_manager.register_provider(provider, set_default=True)
                logger.info(f"✅ Embedding provider: {args.provider}/{model}")
            elif args.provider == "openai-compatible":
                model = args.model or "auto-detected"
                provider = create_openai_compatible_provider(
                    base_url=args.base_url,
                    model=model,
                    api_key=args.api_key,
                )
                embedding_manager = EmbeddingManager()
                embedding_manager.register_provider(provider, set_default=True)
                logger.info(f"✅ Embedding provider: {args.provider}/{model} at {args.base_url}")
            elif args.provider == "tei":
                provider = create_tei_provider(
                    base_url=args.base_url,
                    model=args.model,
                )
                embedding_manager = EmbeddingManager()
                embedding_manager.register_provider(provider, set_default=True)
                logger.info(f"✅ Embedding provider: {args.provider} at {args.base_url}")
            else:
                logger.warning(f"Unknown embedding provider: {args.provider}")
        except Exception as e:
            logger.warning(f"Failed to initialize embedding provider: {e}")
            logger.info("Continuing without embeddings...")
    else:
        logger.info("Embeddings disabled")
    
    # Initialize database
    try:
        db = Database(args.db, embedding_manager)
        db.connect()
        logger.info(f"✅ Database: {args.db}")
        
        # Get initial stats
        stats = db.get_stats()
        logger.info(f"Database stats: {stats['files']} files, {stats['chunks']} chunks, {stats['embeddings']} embeddings")
        
        # Process directory - include Python, Java, C#, and Markdown files
        logger.info("Starting file processing...")
        result = await db.process_directory(args.path, patterns=["**/*.py", "**/*.java", "**/*.cs", "**/*.md", "**/*.markdown"], exclude_patterns=args.exclude)
        
        if result["status"] == "complete":
            logger.info(f"✅ Processing complete:")
            logger.info(f"   • Processed: {result['processed']} files")
            logger.info(f"   • Skipped: {result['skipped']} files")
            logger.info(f"   • Errors: {result['errors']} files")
            logger.info(f"   • Total chunks: {result['total_chunks']}")
            
            # Report cleanup statistics
            cleanup = result.get('cleanup', {})
            if cleanup.get('deleted_files', 0) > 0 or cleanup.get('deleted_chunks', 0) > 0:
                logger.info(f"🧹 Cleanup summary:")
                logger.info(f"   • Deleted files: {cleanup.get('deleted_files', 0)}")
                logger.info(f"   • Removed chunks: {cleanup.get('deleted_chunks', 0)}")
            
            # Show updated stats
            final_stats = db.get_stats()
            logger.info(f"Final database stats: {final_stats['files']} files, {final_stats['chunks']} chunks, {final_stats['embeddings']} embeddings")
        
            # Generate missing embeddings if embedding manager is available
            if embedding_manager:
                logger.info("Checking for missing embeddings...")
                embed_result = await db.generate_missing_embeddings()
                if embed_result["status"] == "success":
                    logger.info(f"✅ Generated {embed_result['generated']} missing embeddings")
                elif embed_result["status"] == "up_to_date":
                    logger.info("All embeddings up to date")
                else:
                    logger.warning(f"Embedding generation failed: {embed_result}")
        
            # Check if watch mode is enabled
            if args.watch:
                logger.info("Initial indexing complete. Starting watch mode...")
                await watch_mode(args, db)
        else:
            logger.error(f"Processing failed: {result}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        cli_coordinator.release_database_access()
        sys.exit(1)
    finally:
        # Restore database access to MCP server if coordination was active
        cli_coordinator.release_database_access()


async def watch_mode(args: argparse.Namespace, db: Database) -> None:
    """Run in continuous file watching mode."""
    logger.info("🔍 Starting file watching mode...")
    
    # Initialize file watcher
    file_watcher = FileWatcherManager()
    
    async def process_file_change(file_path: Path, event_type: str):
        """Process file changes detected by the watcher."""
        try:
            if event_type == 'deleted':
                # Remove file from database
                db.cleanup_deleted_file(str(file_path))
                logger.info(f"🗑️  Removed deleted file: {file_path}")
            else:
                # Process file (created, modified, moved)
                if file_path.exists() and file_path.is_file():
                    # Use incremental processing for performance
                    result = await db.process_file_incremental(file_path=file_path)
                    if result.get("status") == "success":
                        if result.get("incremental"):
                            logger.info(f"📝 Updated file incrementally: {file_path} ({result.get('chunks', 0)} chunks)")
                        else:
                            logger.info(f"📝 Processed file: {file_path} ({result.get('chunks', 0)} chunks)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to process {file_path}: {e}")
    
    # Set up watch paths - use the run directory as the watch path
    watch_paths = [args.path]
    
    try:
        # Initialize file watcher with the callback
        success = await file_watcher.initialize(process_file_change, watch_paths)
        
        if success:
            logger.info(f"👀 Watching for changes in: {args.path}")
            logger.info("Press Ctrl+C to stop watching...")
            
            # Keep the watcher running
            while True:
                await asyncio.sleep(1)
                
        else:
            logger.error("❌ Failed to initialize file watcher")
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping file watcher...")
    finally:
        await file_watcher.cleanup()


async def config_list_command(args) -> None:
    """Handle config list command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        servers = config_manager.registry.list_servers()
        
        if not servers:
            print("No servers configured.")
            return
        
        print(f"Configured servers ({len(servers)}):")
        print()
        
        for name in servers:
            server = config_manager.registry.get_server(name)
            default_marker = " (default)" if config_manager.registry._default_server == name else ""
            enabled_marker = "" if server.enabled else " (disabled)"
            
            print(f"  {name}{default_marker}{enabled_marker}")
            print(f"    Type: {server.type}")
            print(f"    URL:  {server.base_url}")
            print(f"    Model: {server.model or 'auto-detected'}")
            
            if args.show_health:
                try:
                    health = await config_manager.registry.check_server_health(name)
                    status = "✅ healthy" if health.is_healthy else "❌ unhealthy"
                    print(f"    Health: {status} ({health.response_time_ms:.1f}ms)")
                    if health.error_message:
                        print(f"    Error: {health.error_message}")
                except Exception as e:
                    print(f"    Health: ❓ unknown ({e})")
            
            print()
            
    except Exception as e:
        logger.error(f"Failed to list servers: {e}")
        sys.exit(1)


async def config_add_command(args) -> None:
    """Handle config add command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Validate model requirement
        if args.type != 'tei' and not args.model:
            print(f"Error: --model is required for {args.type} servers")
            sys.exit(1)
        
        config_manager.add_server(
            name=args.name,
            server_type=args.type,
            base_url=args.base_url,
            model=args.model or "",
            api_key=args.api_key,
            set_default=args.default,
            batch_size=args.batch_size,
            timeout=args.timeout,
            health_check_interval=args.health_check_interval
        )
        
        # Save configuration
        config_manager.save_config()
        
        print(f"✅ Added server '{args.name}' ({args.type})")
        if args.default:
            print(f"✅ Set '{args.name}' as default server")
            
    except Exception as e:
        logger.error(f"Failed to add server: {e}")
        sys.exit(1)


async def config_remove_command(args) -> None:
    """Handle config remove command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            print(f"Error: Server '{args.name}' not found")
            sys.exit(1)
        
        config_manager.remove_server(args.name)
        config_manager.save_config()
        
        print(f"✅ Removed server '{args.name}'")
        
    except Exception as e:
        logger.error(f"Failed to remove server: {e}")
        sys.exit(1)


async def config_health_command(args) -> None:
    """Handle config health command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.monitor:
            print("Starting health monitoring... (Press Ctrl+C to stop)")
            await config_manager.start_monitoring()
            try:
                while True:
                    await asyncio.sleep(10)
                    # Print health updates every 10 seconds
                    health_status = config_manager.registry.get_health_status()
                    for name, health in health_status.items():
                        status = "✅" if health.is_healthy else "❌"
                        print(f"{status} {name}: {health.response_time_ms:.1f}ms")
            except KeyboardInterrupt:
                print("\nStopping health monitoring...")
            finally:
                await config_manager.stop_monitoring()
        else:
            if args.name:
                # Check specific server
                health = await config_manager.registry.check_server_health(args.name)
                status = "✅ healthy" if health.is_healthy else "❌ unhealthy"
                print(f"{args.name}: {status} ({health.response_time_ms:.1f}ms)")
                if health.error_message:
                    print(f"Error: {health.error_message}")
            else:
                # Check all servers
                servers = config_manager.registry.list_servers()
                if not servers:
                    print("No servers configured.")
                    return
                
                print("Checking server health...")
                for name in servers:
                    try:
                        health = await config_manager.registry.check_server_health(name)
                        status = "✅ healthy" if health.is_healthy else "❌ unhealthy"
                        print(f"  {name}: {status} ({health.response_time_ms:.1f}ms)")
                        if health.error_message:
                            print(f"    Error: {health.error_message}")
                    except Exception as e:
                        print(f"  {name}: ❓ unknown ({e})")
                        
    except Exception as e:
        logger.error(f"Failed to check health: {e}")
        sys.exit(1)


async def config_test_command(args) -> None:
    """Handle config test command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        server_name = args.name
        if not server_name:
            server_name = config_manager.registry._default_server
            if not server_name:
                print("Error: No default server configured and no server specified")
                sys.exit(1)
        
        print(f"Testing server '{server_name}'...")
        
        # Get provider and test embedding
        provider = await config_manager.registry.get_provider(server_name)
        
        start_time = time.time()
        embeddings = await provider.embed([args.text])
        end_time = time.time()
        
        print(f"✅ Test successful!")
        print(f"   Server: {server_name}")
        print(f"   Model: {provider.model}")
        print(f"   Response time: {(end_time - start_time) * 1000:.1f}ms")
        print(f"   Embedding dimensions: {len(embeddings[0])}")
        print(f"   Sample values: {embeddings[0][:5]}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)


async def config_enable_command(args) -> None:
    """Handle config enable command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            print(f"Error: Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if server.enabled:
            print(f"Server '{args.name}' is already enabled")
            return
        
        server.enabled = True
        config_manager.save_config()
        
        print(f"✅ Enabled server '{args.name}'")
        
    except Exception as e:
        logger.error(f"Failed to enable server: {e}")
        sys.exit(1)


async def config_disable_command(args) -> None:
    """Handle config disable command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            print(f"Error: Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if not server.enabled:
            print(f"Server '{args.name}' is already disabled")
            return
        
        # Check if this is the default server
        if config_manager.registry._default_server == args.name:
            print(f"Warning: Disabling default server '{args.name}'")
            print("You may want to set a new default server with 'config set-default'")
        
        server.enabled = False
        config_manager.save_config()
        
        print(f"✅ Disabled server '{args.name}'")
        
    except Exception as e:
        logger.error(f"Failed to disable server: {e}")
        sys.exit(1)


async def config_set_default_command(args) -> None:
    """Handle config set-default command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            print(f"Error: Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if not server.enabled:
            print(f"Error: Cannot set disabled server '{args.name}' as default")
            print(f"Enable it first with: chunkhound config enable {args.name}")
            sys.exit(1)
        
        old_default = config_manager.registry._default_server
        config_manager.registry._default_server = args.name
        config_manager.save_config()
        
        if old_default:
            print(f"✅ Changed default server from '{old_default}' to '{args.name}'")
        else:
            print(f"✅ Set '{args.name}' as default server")
        
    except Exception as e:
        logger.error(f"Failed to set default server: {e}")
        sys.exit(1)


async def config_validate_command(args) -> None:
    """Handle config validate command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Use enhanced validation
        validation_result = config_manager.validate_config_file(args.config)
        
        print(f"Validating configuration: {validation_result.get('config_path', 'default')}")
        print()
        
        # Show basic validation results
        if validation_result['valid']:
            print("✅ Configuration file structure is valid")
        else:
            print("❌ Configuration file has structural issues")
        
        # Show server count
        server_count = validation_result.get('server_count', 0)
        if server_count == 0:
            print("⚠️  No servers configured")
        else:
            print(f"📊 Found {server_count} server(s)")
        
        print()
        
        # Show issues
        if validation_result.get('issues'):
            print("🔴 Issues found:")
            for issue in validation_result['issues']:
                print(f"  • {issue}")
            print()
        
        # Show warnings
        if validation_result.get('warnings'):
            print("🟡 Warnings:")
            for warning in validation_result['warnings']:
                print(f"  • {warning}")
            print()
        
        # Show recommendations
        if validation_result.get('recommendations'):
            print("💡 Recommendations:")
            for rec in validation_result['recommendations']:
                print(f"  • {rec}")
            print()
        
        # Test server connectivity if basic validation passed
        if validation_result['valid'] and server_count > 0:
            print("🔍 Testing server connectivity...")
            servers = config_manager.registry.list_servers()
            healthy_count = 0
            
            for name in servers:
                server = config_manager.registry.get_server(name)
                print(f"  Testing '{name}'...")
                
                if not server.enabled:
                    print(f"    ⚪ Skipped (disabled)")
                    continue
                
                try:
                    health = await config_manager.registry.check_server_health(name)
                    if health.is_healthy:
                        print(f"    ✅ Healthy ({health.response_time_ms:.1f}ms)")
                        healthy_count += 1
                    else:
                        print(f"    ❌ Unhealthy: {health.error_message}")
                except Exception as e:
                    print(f"    ❌ Connection failed: {e}")
            
            print()
            print(f"📈 Health Summary: {healthy_count}/{len(servers)} servers are healthy")
            validation_result['healthy_servers'] = healthy_count
        
        # Auto-fix if requested
        if args.fix and (validation_result.get('issues') or validation_result.get('warnings')):
            print("🔧 Attempting automatic fixes...")
            fixed_count = 0
            
            # Fix disabled servers (except default)
            servers = config_manager.registry.list_servers()
            for name in servers:
                server = config_manager.registry.get_server(name)
                if not server.enabled and name != config_manager.registry._default_server:
                    print(f"  Enabling server '{name}'...")
                    server.enabled = True
                    fixed_count += 1
            
            # Set default server if none specified
            if not config_manager.registry._default_server and servers:
                first_enabled = next((name for name in servers 
                                    if config_manager.registry.get_server(name).enabled), 
                                   servers[0])
                print(f"  Setting '{first_enabled}' as default server...")
                config_manager.registry._default_server = first_enabled
                fixed_count += 1
            
            if fixed_count > 0:
                config_manager.save_config()
                print(f"✅ Fixed {fixed_count} issue(s)")
            else:
                print("ℹ️  No automatic fixes available")
            print()
        
        # Final summary
        if validation_result['valid'] and validation_result.get('healthy_servers', 0) > 0:
            print("🎉 Configuration is ready for use!")
        elif not validation_result['valid']:
            print("❌ Configuration needs attention before use")
            sys.exit(1)
        elif server_count == 0:
            print("⚠️  Add servers to complete configuration")
        else:
            print("⚠️  Fix server connectivity issues")
            if not args.fix:
                print("💡 Try using --fix to attempt automatic repairs")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


async def config_benchmark_command(args) -> None:
    """Handle config benchmark command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name:
            servers_to_test = [args.name]
            if args.name not in config_manager.registry.list_servers():
                print(f"Error: Server '{args.name}' not found")
                sys.exit(1)
        else:
            servers_to_test = [name for name in config_manager.registry.list_servers() 
                             if config_manager.registry.get_server(name).enabled]
        
        if not servers_to_test:
            print("No enabled servers to benchmark")
            return
        
        print(f"Benchmarking {len(servers_to_test)} server(s) with {args.samples} samples each...")
        print(f"Testing batch sizes: {args.batch_sizes}")
        print()
        
        results = {}
        
        for server_name in servers_to_test:
            print(f"Benchmarking '{server_name}'...")
            
            try:
                provider = await config_manager.registry.get_provider(server_name)
                server_results = {}
                
                for batch_size in args.batch_sizes:
                    print(f"  Testing batch size {batch_size}...")
                    
                    # Prepare test texts
                    test_texts = [f"benchmark test text {i}" for i in range(batch_size)]
                    times = []
                    
                    for sample in range(args.samples):
                        start_time = time.time()
                        await provider.embed(test_texts)
                        end_time = time.time()
                        times.append(end_time - start_time)
                    
                    avg_time = sum(times) / len(times)
                    embeddings_per_sec = batch_size / avg_time
                    
                    server_results[batch_size] = {
                        'avg_time': avg_time,
                        'embeddings_per_sec': embeddings_per_sec,
                        'times': times
                    }
                    
                    print(f"    {embeddings_per_sec:.1f} embeddings/sec ({avg_time*1000:.1f}ms avg)")
                
                results[server_name] = server_results
                print(f"  ✅ {server_name} benchmark complete")
                
            except Exception as e:
                print(f"  ❌ {server_name} benchmark failed: {e}")
                results[server_name] = {'error': str(e)}
            
            print()
        
        # Summary
        print("Benchmark Results Summary:")
        print("-" * 60)
        
        for server_name, server_results in results.items():
            if 'error' in server_results:
                print(f"{server_name}: Failed - {server_results['error']}")
                continue
            
            print(f"{server_name}:")
            best_performance = max(server_results.values(), key=lambda x: x['embeddings_per_sec'])
            best_batch_size = next(k for k, v in server_results.items() if v == best_performance)
            
            for batch_size, metrics in server_results.items():
                marker = " 🏆" if batch_size == best_batch_size else ""
                print(f"  Batch {batch_size:2d}: {metrics['embeddings_per_sec']:6.1f} emb/sec{marker}")
            print()
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


async def config_switch_command(args) -> None:
    """Handle config switch command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            print(f"Error: Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        
        if not server.enabled:
            print(f"Error: Server '{args.name}' is disabled")
            print(f"Enable it first with: chunkhound config enable {args.name}")
            sys.exit(1)
        
        old_default = config_manager.registry._default_server
        if old_default == args.name:
            print(f"'{args.name}' is already the default server")
            return
        
        if args.validate:
            print(f"🔍 Validating server '{args.name}'...")
            
            # Basic health check
            try:
                health = await config_manager.registry.check_server_health(args.name)
                if not health.is_healthy:
                    print(f"❌ Server validation failed: {health.error_message}")
                    print("Use --no-validate to skip validation")
                    sys.exit(1)
                print(f"✅ Server is healthy ({health.response_time_ms:.1f}ms)")
            except Exception as e:
                print(f"❌ Server validation failed: {e}")
                print("Use --no-validate to skip validation")
                sys.exit(1)
            
            # Performance comparison if there's a current default
            if old_default:
                print(f"\n📊 Comparing performance: '{old_default}' vs '{args.name}'...")
                try:
                    # Get providers for both servers
                    old_provider = await config_manager.registry.get_provider(old_default)
                    new_provider = await config_manager.registry.get_provider(args.name)
                    
                    # Test both with same text
                    test_text = "benchmark comparison test"
                    
                    # Test old provider
                    old_start = time.time()
                    old_embeddings = await old_provider.embed([test_text])
                    old_time = (time.time() - old_start) * 1000
                    
                    # Test new provider
                    new_start = time.time()
                    new_embeddings = await new_provider.embed([test_text])
                    new_time = (time.time() - new_start) * 1000
                    
                    # Compare results
                    print(f"  Current ({old_default}): {old_time:.1f}ms, {len(old_embeddings[0])} dimensions")
                    print(f"  New     ({args.name}):     {new_time:.1f}ms, {len(new_embeddings[0])} dimensions")
                    
                    if new_time < old_time:
                        improvement = ((old_time - new_time) / old_time) * 100
                        print(f"  🚀 Performance improvement: {improvement:.1f}% faster")
                    else:
                        regression = ((new_time - old_time) / old_time) * 100
                        print(f"  ⚠️  Performance impact: {regression:.1f}% slower")
                    
                    # Check dimension compatibility
                    if len(old_embeddings[0]) != len(new_embeddings[0]):
                        print(f"  ⚠️  Warning: Different embedding dimensions may affect search results")
                        print(f"     Consider reindexing if switching permanently")
                    
                except Exception as e:
                    print(f"  ⚠️  Performance comparison failed: {e}")
                    print(f"     Proceeding with switch...")
            
            # Compatibility check
            print(f"\n🔧 Checking provider compatibility...")
            try:
                new_provider = await config_manager.registry.get_provider(args.name)
                model_info = getattr(new_provider, 'model', 'unknown')
                print(f"  Model: {model_info}")
                print(f"  Type: {server.type}")
                print(f"  ✅ Provider is compatible")
            except Exception as e:
                print(f"  ⚠️  Compatibility check failed: {e}")
        
        # Perform the switch
        config_manager.registry._default_server = args.name
        config_manager.save_config()
        
        print(f"\n🎯 Provider switched successfully!")
        if old_default:
            print(f"   From: {old_default}")
            print(f"   To:   {args.name}")
        else:
            print(f"   Default server set to: {args.name}")
        
        # Show next steps
        print(f"\n💡 Next steps:")
        print(f"   • Test the new provider: chunkhound config test {args.name}")
        print(f"   • Verify embedding quality with your data")
        if old_default:
            old_server = config_manager.registry.get_server(old_default)
            print(f"   • Previous server '{old_default}' is still available")
            if old_server.enabled:
                print(f"   • Switch back anytime: chunkhound config switch {old_default}")
        
    except Exception as e:
        logger.error(f"Failed to switch server: {e}")
        sys.exit(1)


async def config_discover_command(args) -> None:
    """Handle config discover command."""
    try:
        from .config import ConfigManager
        
        start_path = args.path or Path.cwd()
        print(f"Discovering configuration files from '{start_path}'...")
        print()
        
        # Use enhanced discovery
        discovered = ConfigManager.discover_config_files(start_path, include_invalid=args.show_all)
        
        if not discovered:
            print("No configuration files found.")
            print("\nTo create a new configuration:")
            recommended_path = ConfigManager.get_recommended_config_path(start_path)
            print(f"  chunkhound config template --output {recommended_path}")
            return
        
        print(f"Found {len(discovered)} configuration file(s):")
        print()
        
        # Group by priority for better display
        current_priority = None
        for config_info in discovered:
            # Show priority grouping
            if config_info['priority'] != current_priority:
                current_priority = config_info['priority']
                priority_names = {
                    1: "Project-specific (.chunkhound/)",
                    2: "Project-level (chunkhound/)", 
                    3: "Other project configs",
                    4: "User configs (~/.chunkhound/)",
                    5: "System configs (/etc/chunkhound/)"
                }
                if current_priority in priority_names:
                    print(f"── {priority_names[current_priority]} ──")
            
            path = config_info['path']
            if config_info['valid']:
                count = config_info['server_count']
                default = f" (default: {config_info['default_server']})" if config_info['default_server'] else ""
                servers_list = ', '.join(config_info['servers']) if config_info['servers'] else 'none'
                print(f"✅ {path}")
                print(f"   {count} server(s): {servers_list}{default}")
            else:
                print(f"❌ {path}")
                print(f"   Error: {config_info['error']}")
            print()
        
        # Show recommendation with validation
        valid_configs = [c for c in discovered if c['valid']]
        if valid_configs:
            recommended = valid_configs[0]  # Highest priority valid config
            print(f"🎯 Recommended: Use '{recommended['path']}' (priority {recommended['priority']})")
            print(f"   chunkhound --config {recommended['path']} config list")
            
            # Additional recommendations
            if len(valid_configs) > 1:
                print(f"\n💡 Alternative configs available ({len(valid_configs)-1} others)")
            
            # Suggest validation
            print(f"\n🔍 Validate this config:")
            print(f"   chunkhound --config {recommended['path']} config validate")
        else:
            print("⚠️  No valid configurations found.")
            recommended_path = ConfigManager.get_recommended_config_path(start_path)
            print(f"\n💡 Create a new config:")
            print(f"   chunkhound config template --output {recommended_path}")
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        sys.exit(1)


async def config_export_command(args) -> None:
    """Handle config export command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Get current configuration
        servers_data = {}
        for name in config_manager.registry.list_servers():
            server = config_manager.registry.get_server(name)
            servers_data[name] = {
                'type': server.type,
                'base_url': server.base_url,
                'model': server.model,
                'enabled': server.enabled,
                'batch_size': server.batch_size,
                'timeout': server.timeout,
                'health_check_interval': server.health_check_interval
            }
            if server.api_key:
                servers_data[name]['api_key'] = server.api_key
        
        export_data = {
            'servers': servers_data,
            'default_server': config_manager.registry._default_server
        }
        
        if args.format == 'yaml':
            import yaml
            output = yaml.dump(export_data, default_flow_style=False, sort_keys=True)
        else:
            import json
            output = json.dumps(export_data, indent=2, sort_keys=True)
        
        with open(args.output, 'w') as f:
            f.write(output)
        
        print(f"✅ Configuration exported to '{args.output}' ({args.format} format)")
        print(f"   Exported {len(servers_data)} server(s)")
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


async def config_import_command(args) -> None:
    """Handle config import command."""
    try:
        # Read import file
        with open(args.input, 'r') as f:
            content = f.read()
        
        # Parse based on file extension
        if args.input.endswith(('.yaml', '.yml')):
            import yaml
            import_data = yaml.safe_load(content)
        else:
            import json
            import_data = json.loads(content)
        
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Backup existing config if requested
        if args.backup and hasattr(config_manager, '_config_file') and Path(config_manager._config_file).exists():
            backup_path = f"{config_manager._config_file}.backup"
            import shutil
            shutil.copy2(config_manager._config_file, backup_path)
            print(f"✅ Created backup: {backup_path}")
        
        if not args.merge:
            # Clear existing configuration
            config_manager.registry._servers.clear()
            config_manager.registry._providers.clear()
            config_manager.registry._health_status.clear()
        
        # Import servers
        servers_imported = 0
        if 'servers' in import_data:
            for name, server_data in import_data['servers'].items():
                config_manager.add_server(
                    name=name,
                    server_type=server_data['type'],
                    base_url=server_data['base_url'],
                    model=server_data.get('model', ''),
                    api_key=server_data.get('api_key'),
                    set_default=False,
                    batch_size=server_data.get('batch_size'),
                    timeout=server_data.get('timeout', 30),
                    health_check_interval=server_data.get('health_check_interval', 300)
                )
                
                # Set enabled status
                if 'enabled' in server_data:
                    server = config_manager.registry.get_server(name)
                    server.enabled = server_data['enabled']
                
                servers_imported += 1
        
        # Set default server
        if 'default_server' in import_data and import_data['default_server']:
            config_manager.registry._default_server = import_data['default_server']
        
        config_manager.save_config()
        
        print(f"✅ Configuration imported from '{args.input}'")
        print(f"   Imported {servers_imported} server(s)")
        if 'default_server' in import_data:
            print(f"   Default server: {import_data['default_server']}")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


async def config_template_command(args) -> None:
    """Handle config template command."""
    try:
        templates = {
            'basic': {
                'servers': {
                    'openai': {
                        'type': 'openai',
                        'base_url': 'https://api.openai.com/v1',
                        'model': 'text-embedding-3-small',
                        'enabled': True
                    }
                },
                'default_server': 'openai'
            },
            'local': {
                'servers': {
                    'local-tei': {
                        'type': 'tei',
                        'base_url': 'http://localhost:8080',
                        'model': '',  # Auto-detected
                        'enabled': True
                    },
                    'openai-fallback': {
                        'type': 'openai',
                        'base_url': 'https://api.openai.com/v1',
                        'model': 'text-embedding-3-small',
                        'enabled': False
                    }
                },
                'default_server': 'local-tei'
            },
            'advanced': {
                'servers': {
                    'primary-tei': {
                        'type': 'tei',
                        'base_url': 'http://localhost:8080',
                        'model': '',
                        'enabled': True,
                        'batch_size': 32,
                        'timeout': 60,
                        'health_check_interval': 120
                    },
                    'backup-openai': {
                        'type': 'openai',
                        'base_url': 'https://api.openai.com/v1',
                        'model': 'text-embedding-3-small',
                        'enabled': True,
                        'batch_size': 16,
                        'timeout': 30
                    },
                    'custom-compatible': {
                        'type': 'openai-compatible',
                        'base_url': 'http://custom-server:8000/v1',
                        'model': 'custom-model',
                        'enabled': True
                    }
                },
                'default_server': 'primary-tei'
            },
            'production': {
                'servers': {
                    'production-cluster': {
                        'type': 'openai-compatible',
                        'base_url': 'https://embeddings.company.com/v1',
                        'model': 'company-embeddings-v1',
                        'enabled': True,
                        'batch_size': 64,
                        'timeout': 45,
                        'health_check_interval': 60
                    },
                    'openai-backup': {
                        'type': 'openai',
                        'base_url': 'https://api.openai.com/v1',
                        'model': 'text-embedding-3-large',
                        'enabled': True,
                        'batch_size': 32,
                        'timeout': 30
                    }
                },
                'default_server': 'production-cluster'
            }
        }
        
        template = templates[args.type]
        
        import yaml
        output = yaml.dump(template, default_flow_style=False, sort_keys=True)
        
        # Add comments
        comments = {
            'basic': "# Basic ChunkHound configuration with OpenAI\n# Set OPENAI_API_KEY environment variable\n\n",
            'local': "# Local embedding server configuration\n# Assumes TEI server running on localhost:8080\n\n",
            'advanced': "# Advanced multi-server configuration\n# Includes custom batch sizes and health check settings\n\n",
            'production': "# Production-ready configuration\n# Replace URLs and models with your actual servers\n\n"
        }
        
        output = comments[args.type] + output
        
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"✅ Template written to '{args.output}'")
        else:
            print(output)
        
    except Exception as e:
        logger.error(f"Template generation failed: {e}")
        sys.exit(1)


async def config_batch_test_command(args) -> None:
    """Handle config batch-test command."""
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        servers = [name for name in config_manager.registry.list_servers() 
                  if config_manager.registry.get_server(name).enabled]
        
        if not servers:
            print("No enabled servers to test")
            return
        
        print(f"Testing {len(servers)} server(s) in parallel...")
        print()
        
        async def test_server(server_name):
            try:
                provider = await config_manager.registry.get_provider(server_name)
                start_time = time.time()
                embeddings = await asyncio.wait_for(
                    provider.embed([args.text]), 
                    timeout=args.timeout
                )
                end_time = time.time()
                
                return {
                    'name': server_name,
                    'success': True,
                    'response_time': (end_time - start_time) * 1000,
                    'model': provider.model,
                    'dimensions': len(embeddings[0])
                }
            except asyncio.TimeoutError:
                return {
                    'name': server_name,
                    'success': False,
                    'error': f'Timeout after {args.timeout}s'
                }
            except Exception as e:
                return {
                    'name': server_name,
                    'success': False,
                    'error': str(e)
                }
        
        # Run tests in parallel
        results = await asyncio.gather(*[test_server(name) for name in servers])
        
        # Display results
        successful = 0
        for result in results:
            if result['success']:
                print(f"✅ {result['name']}: {result['response_time']:.1f}ms "
                      f"({result['model']}, {result['dimensions']} dims)")
                successful += 1
            else:
                print(f"❌ {result['name']}: {result['error']}")
        
        print()
        print(f"Results: {successful}/{len(servers)} servers passed")
        
        if successful < len(servers):
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Batch test failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(getattr(args, "verbose", False))
    validate_args(args)
    
    try:
        if args.command == "run":
            asyncio.run(run_command(args))
        elif args.command == "mcp":
            mcp_command(args)
        elif args.command == "config":
            if args.config_command == "list":
                asyncio.run(config_list_command(args))
            elif args.config_command == "add":
                asyncio.run(config_add_command(args))
            elif args.config_command == "remove":
                asyncio.run(config_remove_command(args))
            elif args.config_command == "health":
                asyncio.run(config_health_command(args))
            elif args.config_command == "test":
                asyncio.run(config_test_command(args))
            elif args.config_command == "enable":
                asyncio.run(config_enable_command(args))
            elif args.config_command == "disable":
                asyncio.run(config_disable_command(args))
            elif args.config_command == "set-default":
                asyncio.run(config_set_default_command(args))
            elif args.config_command == "validate":
                asyncio.run(config_validate_command(args))
            elif args.config_command == "benchmark":
                asyncio.run(config_benchmark_command(args))
            elif args.config_command == "switch":
                asyncio.run(config_switch_command(args))
            elif args.config_command == "discover":
                asyncio.run(config_discover_command(args))
            elif args.config_command == "export":
                asyncio.run(config_export_command(args))
            elif args.config_command == "import":
                asyncio.run(config_import_command(args))
            elif args.config_command == "template":
                asyncio.run(config_template_command(args))
            elif args.config_command == "batch-test":
                asyncio.run(config_batch_test_command(args))
            else:
                print("Error: config command required")
                parser.parse_args(["config", "--help"])
                sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()