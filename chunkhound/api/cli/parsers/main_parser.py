"""Main argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path

from chunkhound.version import __version__


def create_main_parser() -> argparse.ArgumentParser:
    """Create and configure the main argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="chunkhound",
        description="Local-first semantic code search with vector and regex capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chunkhound index
  chunkhound index /path/to/project
  chunkhound index . --db ./chunks.duckdb
  chunkhound index /code --include "*.py" --exclude "*/tests/*"
  chunkhound mcp --db ./chunks.duckdb
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"chunkhound {__version__}",
    )

    return parser


def setup_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    """Set up subparsers for the main parser.

    Args:
        parser: Main argument parser

    Returns:
        Subparsers action for adding command parsers
    """
    return parser.add_subparsers(dest="command", help="Available commands")


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common arguments used across multiple commands.

    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )


def add_database_argument(
    parser: argparse.ArgumentParser, required: bool = False
) -> None:
    """Add database path argument to a parser.

    Args:
        parser: Parser to add argument to
        required: Whether the argument is required
    """
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        required=required,
        help="Database file path (default: from config file or .chunkhound.db)",
    )
    
    parser.add_argument(
        "--database-path",
        type=Path,
        default=None,
        help="Database file path (alternative to --db)",
    )
    
    parser.add_argument(
        "--database-provider",
        choices=["duckdb", "lancedb"],
        help="Database provider to use",
    )
    
    parser.add_argument(
        "--database-lancedb-index-type",
        choices=["ivf-pq", "ivf", "flat"],
        help="LanceDB index type for vector search",
    )


def add_embedding_arguments(parser: argparse.ArgumentParser) -> None:
    """Add embedding provider arguments to a parser.

    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--provider",
        default=None,
        choices=["openai", "openai-compatible", "tei", "bge-in-icl"],
        help="Embedding provider to use (required - no default)",
    )

    parser.add_argument(
        "--model",
        help="Embedding model to use (defaults: openai=text-embedding-3-small, bge-in-icl=bge-in-icl, tei=auto-detect, openai-compatible=required)",
    )

    parser.add_argument(
        "--api-key",
        help="API key for embedding provider (uses env var if not specified)",
    )

    parser.add_argument(
        "--base-url",
        help="Base URL for embedding API (uses env var if not specified)",
    )

    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation (index code only)",
    )
    
    parser.add_argument(
        "--embedding-provider",
        choices=["openai", "openai-compatible", "tei", "bge-in-icl"],
        help="Embedding provider to use (alternative to --provider)",
    )
    
    parser.add_argument(
        "--embedding-model",
        help="Embedding model to use (alternative to --model)",
    )
    
    parser.add_argument(
        "--embedding-api-key",
        help="API key for embedding provider (alternative to --api-key)",
    )
    
    parser.add_argument(
        "--embedding-base-url",
        help="Base URL for embedding API (alternative to --base-url)",
    )
    
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        help="Number of texts to send per API request",
    )
    
    parser.add_argument(
        "--embedding-max-concurrent",
        type=int,
        help="Maximum concurrent embedding requests",
    )


def add_file_pattern_arguments(parser: argparse.ArgumentParser) -> None:
    """Add file pattern arguments to a parser.

    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="File patterns to include (can be specified multiple times)",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="File patterns to exclude (can be specified multiple times)",
    )


def add_mcp_arguments(parser: argparse.ArgumentParser) -> None:
    """Add MCP server arguments to a parser.
    
    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--mcp-transport",
        choices=["stdio", "http"],
        help="MCP transport type",
    )
    
    parser.add_argument(
        "--mcp-port",
        type=int,
        help="HTTP port for MCP server",
    )
    
    parser.add_argument(
        "--mcp-host",
        help="HTTP host for MCP server",
    )
    
    parser.add_argument(
        "--mcp-cors",
        action="store_true",
        help="Enable CORS for MCP HTTP server",
    )


def add_indexing_arguments(parser: argparse.ArgumentParser) -> None:
    """Add indexing configuration arguments to a parser.
    
    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--indexing-watch",
        action="store_true",
        help="Enable file watching for automatic reindexing",
    )
    
    parser.add_argument(
        "--indexing-debounce-ms",
        type=int,
        help="Debounce time in milliseconds for file watching",
    )
    
    parser.add_argument(
        "--indexing-batch-size",
        type=int,
        help="Number of files to process per batch",
    )
    
    parser.add_argument(
        "--indexing-db-batch-size",
        type=int,
        help="Number of records to insert per database transaction",
    )
    
    parser.add_argument(
        "--indexing-max-concurrent",
        type=int,
        help="Maximum concurrent file processing tasks",
    )
    
    parser.add_argument(
        "--indexing-force-reindex",
        action="store_true",
        help="Force reindexing of all files",
    )
    
    parser.add_argument(
        "--indexing-cleanup",
        action="store_true",
        help="Clean up orphaned chunks from deleted files",
    )
    
    parser.add_argument(
        "--indexing-ignore-gitignore",
        action="store_true",
        help="Ignore .gitignore files when scanning",
    )


__all__ = [
    "create_main_parser",
    "setup_subparsers",
    "add_common_arguments",
    "add_database_argument",
    "add_embedding_arguments",
    "add_file_pattern_arguments",
    "add_mcp_arguments",
    "add_indexing_arguments",
]
