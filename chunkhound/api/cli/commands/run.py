"""Run command module - handles directory indexing operations."""

import argparse
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.config.config import Config
from chunkhound.core.config.embedding_config import EmbeddingConfig
from chunkhound.core.config.embedding_factory import EmbeddingProviderFactory
from chunkhound.embeddings import EmbeddingManager
from chunkhound.registry import configure_registry, create_indexing_coordinator
from chunkhound.services.directory_indexing_service import DirectoryIndexingService
from chunkhound.version import __version__

from ..parsers.run_parser import process_batch_arguments
from ..utils.output import OutputFormatter, format_stats
from ..utils.validation import (
    ensure_database_directory,
    validate_file_patterns,
    validate_path,
    validate_provider_args,
)


async def run_command(args: argparse.Namespace, config: Config) -> None:
    """Execute the run command using the service layer.

    Args:
        args: Parsed command-line arguments
        config: Pre-validated configuration instance
    """
    # Initialize output formatter
    formatter = OutputFormatter(verbose=args.verbose)

    # Check if local config was found (for logging purposes)
    project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
    local_config_path = project_dir / ".chunkhound.json"
    if local_config_path.exists():
        formatter.info(f"Found local config: {local_config_path}")

    # Use database path from config
    db_path = Path(config.database.path)

    # Display startup information
    formatter.info(f"Starting ChunkHound v{__version__}")
    formatter.info(f"Processing directory: {args.path}")
    formatter.info(f"Database: {db_path}")

    # Process and validate batch arguments (includes deprecation warnings)
    process_batch_arguments(args)

    # Validate arguments - update args.db to use config value for validation
    args.db = db_path
    if not _validate_run_arguments(args, formatter, config):
        sys.exit(1)

    try:
        # Configure registry with the Config object
        configure_registry(config)
        indexing_coordinator = create_indexing_coordinator()

        formatter.success(f"Service layer initialized: {args.db}")

        # Get initial stats
        initial_stats = await indexing_coordinator.get_stats()
        formatter.info(f"Initial stats: {format_stats(initial_stats)}")

        # Create directory indexing service
        def progress_callback(message: str):
            if args.verbose:
                formatter.info(message)

        indexing_service = DirectoryIndexingService(
            indexing_coordinator=indexing_coordinator,
            config=config,
            progress_callback=progress_callback
        )

        # Process directory using shared service
        stats = await indexing_service.process_directory(
            Path(args.path), no_embeddings=args.no_embeddings
        )

        # Display results
        _print_completion_summary(stats, formatter)

        formatter.success("Run command completed successfully")

    except KeyboardInterrupt:
        formatter.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        formatter.error(f"Run command failed: {e}")
        logger.exception("Run command error details")
        sys.exit(1)
    finally:
        pass


def _print_completion_summary(stats, formatter: OutputFormatter) -> None:
    """Print completion summary from IndexingStats."""
    formatter.success("Processing complete:")
    formatter.info(f"   • Processed: {stats.files_processed} files")
    formatter.info(f"   • Skipped: {stats.files_skipped} files") 
    formatter.info(f"   • Errors: {stats.files_errors} files")
    formatter.info(f"   • Total chunks: {stats.chunks_created}")
    
    if stats.embeddings_generated > 0:
        formatter.success(f"Generated {stats.embeddings_generated} embeddings")
    
    if stats.cleanup_deleted_files > 0 or stats.cleanup_deleted_chunks > 0:
        formatter.info("🧹 Cleanup summary:")
        formatter.info(f"   • Deleted files: {stats.cleanup_deleted_files}")
        formatter.info(f"   • Removed chunks: {stats.cleanup_deleted_chunks}")
    
    formatter.info(f"Processing time: {stats.processing_time:.2f}s")


def _validate_run_arguments(
    args: argparse.Namespace, formatter: OutputFormatter, config: Any = None
) -> bool:
    """Validate run command arguments.

    Args:
        args: Parsed arguments
        formatter: Output formatter
        config: Configuration (optional)

    Returns:
        True if valid, False otherwise
    """
    # Validate path
    if not validate_path(args.path, must_exist=True, must_be_dir=True):
        return False

    # Ensure database directory exists
    if not ensure_database_directory(args.db):
        return False

    # Validate provider arguments
    if not args.no_embeddings:
        # Use unified config values if available, fall back to CLI args
        if config and config.embedding:
            provider = config.embedding.provider
            api_key = (
                config.embedding.api_key.get_secret_value()
                if config.embedding.api_key
                else None
            )
            base_url = config.embedding.base_url
            model = config.embedding.model
        else:
            # Check if CLI args have provider info
            provider = getattr(args, 'provider', None)
            api_key = getattr(args, 'api_key', None)
            base_url = getattr(args, 'base_url', None)
            model = getattr(args, 'model', None)
        if not validate_provider_args(provider, api_key, base_url, model):
            return False

    # Validate file patterns
    if not validate_file_patterns(args.include, args.exclude):
        return False

    return True


__all__ = ["run_command"]
