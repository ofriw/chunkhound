"""ChunkHound CLI - Command-line interface for directory watching and indexing."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from . import __version__


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
        "--host",
        default="127.0.0.1",
        help="API server host (default: 127.0.0.1)",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=7474,
        help="API server port (default: 7474)",
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


def run_command(args: argparse.Namespace) -> None:
    """Execute the run command."""
    logger.info(f"Starting ChunkHound v{__version__}")
    logger.info(f"Watching directory: {args.path}")
    logger.info(f"Database: {args.db}")
    logger.info(f"API server: http://{args.host}:{args.port}")
    
    # Default file patterns for Python files if none specified
    if not args.include:
        args.include = ["*.py"]
    
    # Default exclusion patterns
    default_excludes = [
        "*/.git/*",
        "*/__pycache__/*", 
        "*/venv/*",
        "*/env/*",
        "*/.venv/*",
        "*/node_modules/*",
        "*/dist/*",
        "*/build/*",
    ]
    args.exclude.extend(default_excludes)
    
    logger.info(f"Include patterns: {args.include}")
    logger.info(f"Exclude patterns: {args.exclude}")
    
    # TODO: Phase 1 - For now, just log the configuration
    logger.info("Phase 1: Configuration validated. Ready for database and parsing implementation.")


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
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()