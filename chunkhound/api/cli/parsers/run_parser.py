"""Run command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path
from typing import Any, cast

from .main_parser import (
    add_common_arguments,
    add_database_argument,
    add_embedding_arguments,
    add_file_pattern_arguments,
    add_indexing_arguments,
    add_mcp_arguments,
)


def validate_batch_sizes(
    embedding_batch_size: int | None, db_batch_size: int | None, provider: str
) -> tuple[bool, str]:
    """Validate batch size arguments against provider limits and system constraints.

    Args:
        embedding_batch_size: Number of texts per embedding API request (None uses default)
        db_batch_size: Number of records per database transaction (None uses default)
        provider: Embedding provider name

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Use defaults if None
    if embedding_batch_size is None:
        embedding_batch_size = 50  # Default from EmbeddingConfig
    if db_batch_size is None:
        db_batch_size = 100  # Default from IndexingConfig
    # Provider-specific embedding batch limits
    embedding_limits: dict[str, tuple[int, int]] = {
        "openai": (1, 2048),
        "openai-compatible": (1, 1000),
        "tei": (1, 512),
        "bge-in-icl": (1, 256),
    }

    # Database batch limits (DuckDB optimized for large batches)
    db_limits = (1, 10000)

    # Validate embedding batch size
    if provider in embedding_limits:
        min_emb, max_emb = embedding_limits[provider]
        if not (min_emb <= embedding_batch_size <= max_emb):
            return (
                False,
                f"Embedding batch size {embedding_batch_size} invalid for provider '{provider}'. Must be between {min_emb} and {max_emb}.",
            )
    else:
        # Default limits for unknown providers
        if not (1 <= embedding_batch_size <= 1000):
            return (
                False,
                f"Embedding batch size {embedding_batch_size} invalid. Must be between 1 and 1000.",
            )

    # Validate database batch size
    min_db, max_db = db_limits
    if not (min_db <= db_batch_size <= max_db):
        return (
            False,
            f"Database batch size {db_batch_size} invalid. Must be between {min_db} and {max_db}.",
        )

    return True, ""


def process_batch_arguments(args: argparse.Namespace) -> None:
    """Process and validate batch arguments, handle deprecation warnings.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If batch size validation fails
    """
    import sys

    # Handle backward compatibility - --batch-size maps to --embedding-batch-size
    if args.batch_size is not None:
        print(
            f"WARNING: --batch-size is deprecated. Use --embedding-batch-size instead.\n"
            f"         Using --embedding-batch-size {args.batch_size} based on your --batch-size {args.batch_size}\n"
            f"         Consider also setting --db-batch-size for optimal performance",
            file=sys.stderr,
        )
        # Only override if embedding_batch_size is still default
        if args.embedding_batch_size == 100:  # Default value
            args.embedding_batch_size = args.batch_size

    # Validate batch sizes
    is_valid, error_msg = validate_batch_sizes(
        args.embedding_batch_size,
        args.db_batch_size,
        getattr(args, "provider", "openai"),
    )

    if not is_valid:
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


def add_run_subparser(subparsers: Any) -> argparse.ArgumentParser:
    """Add run command subparser to the main parser.

    Args:
        subparsers: Subparsers object from the main argument parser

    Returns:
        The configured run subparser
    """
    run_parser = subparsers.add_parser(
        "index",
        help="Index directory and optionally watch for changes",
        description="Scan and index a directory for code search, generating embeddings for semantic search. Optionally watch for file changes and update the index automatically.",
    )

    # Optional positional argument with default to current directory
    run_parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Directory path to index (default: current directory)",
    )

    # Add common argument groups
    add_common_arguments(run_parser)
    add_database_argument(run_parser)
    add_embedding_arguments(run_parser)
    add_file_pattern_arguments(run_parser)
    add_indexing_arguments(run_parser)
    add_mcp_arguments(run_parser)

    # Run-specific arguments (only those not covered by the new functions)
    # Keep legacy arguments for backwards compatibility but map to new names
    run_parser.add_argument(
        "--debounce-ms",
        type=int,
        default=500,
        help="File change debounce time in milliseconds (default: 500)",
    )

    run_parser.add_argument(
        "--watch",
        action="store_true",
        help="Enable continuous file watching mode",
    )

    run_parser.add_argument(
        "--initial-scan-only",
        action="store_true",
        help="Perform initial scan only, do not watch for changes",
    )

    run_parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Force reindexing of all files, even if they haven't changed",
    )

    # Database batch size (not covered by other functions)
    run_parser.add_argument(
        "--db-batch-size",
        type=int,
        default=500,
        help="Number of records per database transaction (default: 500, range: 1-10000)",
    )

    # Legacy arguments - deprecated but maintained for backward compatibility
    run_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="[DEPRECATED] Use --embedding-batch-size instead. Batch size for embedding generation",
    )

    run_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent embedding batches (default: 3)",
    )

    run_parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up orphaned chunks from deleted files",
    )

    return cast(argparse.ArgumentParser, run_parser)


__all__: list[str] = ["add_run_subparser"]
