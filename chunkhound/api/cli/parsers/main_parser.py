"""Main argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path

# Version imported dynamically to avoid early chunkhound module loading


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
  chunkhound run /path/to/project
  chunkhound run . --db ./chunks.duckdb
  chunkhound run /code --include "*.py" --exclude "*/tests/*"
  chunkhound config list
  chunkhound config add openai --type openai --base-url https://api.openai.com/v1
  chunkhound mcp --db ./chunks.duckdb
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="chunkhound 1.1.0",
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
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )


def add_database_argument(parser: argparse.ArgumentParser, required: bool = False) -> None:
    """Add database path argument to a parser.

    Args:
        parser: Parser to add argument to
        required: Whether the argument is required
    """
    parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".cache" / "chunkhound" / "chunks.duckdb",
        required=required,
        help="DuckDB database file path (default: ~/.cache/chunkhound/chunks.duckdb)",
    )


def add_embedding_arguments(parser: argparse.ArgumentParser) -> None:
    """Add embedding provider arguments to a parser.

    Args:
        parser: Parser to add arguments to
    """
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "openai-compatible", "tei", "bge-in-icl"],
        help="Embedding provider to use (default: openai)",
    )

    parser.add_argument(
        "--model",
        help="Embedding model to use (defaults to provider default)",
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


__all__ = [
    "create_main_parser",
    "setup_subparsers",
    "add_common_arguments",
    "add_database_argument",
    "add_embedding_arguments",
    "add_file_pattern_arguments",
]
