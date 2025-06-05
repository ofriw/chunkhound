"""ChunkHound CLI - Command-line interface for directory watching and indexing."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from . import __version__
from .database import Database
from .embeddings import EmbeddingManager, create_openai_provider


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


def run_command(args: argparse.Namespace) -> None:
    """Execute the run command."""
    logger.info(f"Starting ChunkHound v{__version__}")
    logger.info(f"Processing directory: {args.path}")
    logger.info(f"Database: {args.db}")
    
    # Default file patterns for Python and Java files if none specified
    if not args.include:
        args.include = ["*.py", "*.java"]
    
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
        
        # Process directory - include Python, Java, and Markdown files
        logger.info("Starting file processing...")
        result = db.process_directory(args.path, patterns=["**/*.py", "**/*.java", "**/*.md", "**/*.markdown"], exclude_patterns=args.exclude)
        
        if result["status"] == "complete":
            logger.info(f"✅ Processing complete:")
            logger.info(f"   • Processed: {result['processed']} files")
            logger.info(f"   • Skipped: {result['skipped']} files")
            logger.info(f"   • Errors: {result['errors']} files")
            logger.info(f"   • Total chunks: {result['total_chunks']}")
            
            # Show updated stats
            final_stats = db.get_stats()
            logger.info(f"Final database stats: {final_stats['files']} files, {final_stats['chunks']} chunks, {final_stats['embeddings']} embeddings")
            
            # Generate missing embeddings if embedding manager is available
            if embedding_manager:
                logger.info("Checking for missing embeddings...")
                embed_result = db.generate_missing_embeddings()
                if embed_result["status"] == "success":
                    logger.info(f"✅ Generated {embed_result['generated']} missing embeddings")
                elif embed_result["status"] == "up_to_date":
                    logger.info("All embeddings up to date")
                else:
                    logger.warning(f"Embedding generation failed: {embed_result}")
        else:
            logger.error(f"Processing failed: {result}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Database error: {e}")
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
            run_command(args)
        elif args.command == "mcp":
            mcp_command(args)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()