"""Run command module - handles directory indexing operations."""

import argparse
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.config.config import Config
from chunkhound.registry import configure_registry, create_indexing_coordinator
from chunkhound.services.directory_indexing_service import DirectoryIndexingService
from chunkhound.version import __version__

from ..parsers.run_parser import process_batch_arguments
from ..utils.rich_output import RichOutputFormatter
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
    # Initialize Rich output formatter
    formatter = RichOutputFormatter(verbose=args.verbose)

    # Check if local config was found (for logging purposes)
    project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
    local_config_path = project_dir / ".chunkhound.json"
    if local_config_path.exists():
        formatter.info(f"Found local config: {local_config_path}")

    # Use database path from config
    db_path = Path(config.database.path)

    # Display modern startup information
    formatter.startup_info(
        version=__version__,
        directory=str(args.path),
        database=str(db_path),
        config=config.__dict__ if hasattr(config, "__dict__") else {},
    )

    # Process and validate batch arguments (includes deprecation warnings)
    process_batch_arguments(args)

    # Validate arguments - update args.db to use config value for validation
    args.db = db_path
    if not _validate_run_arguments(args, formatter, config):
        sys.exit(1)

    try:
        # Configure registry with the Config object
        configure_registry(config)

        formatter.success(f"Service layer initialized: {args.db}")

        # Create progress manager for modern UI
        with formatter.create_progress_display() as progress_manager:
            # Get the underlying Progress instance for service layers
            progress_instance = progress_manager.get_progress_instance()

            # Create indexing coordinator with Progress instance
            indexing_coordinator = create_indexing_coordinator()
            # Pass progress to the coordinator after creation
            if hasattr(indexing_coordinator, "progress"):
                indexing_coordinator.progress = progress_instance

            # Get initial stats
            initial_stats = await indexing_coordinator.get_stats()
            formatter.initial_stats_panel(initial_stats)

            # Simple progress callback for verbose output
            def progress_callback(message: str):
                if args.verbose:
                    formatter.verbose_info(message)

            # Create indexing service with Progress instance
            indexing_service = DirectoryIndexingService(
                indexing_coordinator=indexing_coordinator,
                config=config,
                progress_callback=progress_callback,
                progress=progress_instance,
            )

            # Process directory - service layers will add subtasks to progress_instance
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


def _print_completion_summary(stats, formatter: RichOutputFormatter) -> None:
    """Print completion summary from IndexingStats using Rich formatting."""
    # Convert stats object to dictionary for Rich display
    if hasattr(stats, "__dict__"):
        stats_dict = stats.__dict__
    else:
        stats_dict = stats if isinstance(stats, dict) else {}
    formatter.completion_summary(stats_dict, stats.processing_time)


def _validate_run_arguments(
    args: argparse.Namespace, formatter: RichOutputFormatter, config: Any = None
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
            provider = getattr(args, "provider", None)
            api_key = getattr(args, "api_key", None)
            base_url = getattr(args, "base_url", None)
            model = getattr(args, "model", None)

            # If no provider info found, provide helpful error
            if not provider:
                formatter.error("No embedding provider configured.")
                formatter.info("To fix this, you can:")
                formatter.info(
                    "  1. Create .chunkhound.json config file with embeddings"
                )
                formatter.info("  2. Use --no-embeddings to skip embeddings")
                return False
        if not validate_provider_args(provider, api_key, base_url, model):
            return False

    # Validate file patterns
    if not validate_file_patterns(args.include, args.exclude):
        return False

    return True


__all__ = ["run_command"]
