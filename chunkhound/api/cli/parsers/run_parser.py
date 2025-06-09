"""Run command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path

from .main_parser import (
    add_common_arguments,
    add_database_argument,
    add_embedding_arguments,
    add_file_pattern_arguments,
)


def add_run_subparser(subparsers) -> argparse.ArgumentParser:
    """Add run command subparser to the main parser.
    
    Args:
        subparsers: Subparsers object from the main argument parser
        
    Returns:
        The configured run subparser
    """
    run_parser = subparsers.add_parser(
        "run",
        help="Watch directory and index code for search",
        description="Index and watch a directory for code changes, generating embeddings for semantic search"
    )
    
    # Required positional argument
    run_parser.add_argument(
        "path",
        type=Path,
        help="Directory path to watch and index",
    )
    
    # Add common argument groups
    add_common_arguments(run_parser)
    add_database_argument(run_parser)
    add_embedding_arguments(run_parser)
    add_file_pattern_arguments(run_parser)
    
    # Run-specific arguments
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
    
    run_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for embedding generation (default: 50)",
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
    
    return run_parser


__all__ = ["add_run_subparser"]