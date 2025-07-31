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
        # Set up file patterns using unified config (already loaded)
        include_patterns, exclude_patterns = _setup_file_patterns_from_config(
            config, args
        )
        formatter.info(f"Include patterns: {include_patterns}")
        formatter.info(f"Exclude patterns: {exclude_patterns}")

        # Configuration already validated in main.py

        # Configure registry with the Config object
        configure_registry(config)
        indexing_coordinator = create_indexing_coordinator()

        formatter.success(f"Service layer initialized: {args.db}")

        # Get initial stats
        initial_stats = await indexing_coordinator.get_stats()
        formatter.info(f"Initial stats: {format_stats(initial_stats)}")

        # Perform directory processing
        await _process_directory(
            indexing_coordinator, args, formatter, include_patterns, exclude_patterns
        )

        # Generate missing embeddings if enabled
        if not args.no_embeddings:
            await _generate_missing_embeddings(
                indexing_coordinator, formatter, exclude_patterns
            )

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
        if config:
            provider = config.embedding.provider
            api_key = (
                config.embedding.api_key.get_secret_value()
                if config.embedding.api_key
                else None
            )
            base_url = config.embedding.base_url
            model = config.embedding.model
        else:
            provider = args.provider
            api_key = args.api_key
            base_url = args.base_url
            model = args.model

        if not validate_provider_args(provider, api_key, base_url, model):
            return False

    # Validate file patterns
    if not validate_file_patterns(args.include, args.exclude):
        return False

    return True


def _setup_file_patterns_from_config(
    config: Any, args: argparse.Namespace
) -> tuple[list[str], list[str]]:
    """Set up file inclusion and exclusion patterns from unified config.

    Args:
        config: Unified configuration object
        args: Parsed arguments (for fallback)

    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    # Trust config layer to provide complete patterns, allow CLI override
    if hasattr(args, "include") and args.include:
        include_patterns = args.include  # CLI override
    else:
        include_patterns = config.indexing.include  # Config layer (now complete)

    # Use exclude patterns from config
    exclude_patterns = list(config.indexing.exclude)
    if hasattr(args, "exclude") and args.exclude:
        exclude_patterns.extend(args.exclude)

    return include_patterns, exclude_patterns


async def _setup_embedding_manager(
    args: argparse.Namespace, formatter: OutputFormatter
) -> EmbeddingManager | None:
    """Set up embedding manager using factory-based provider configuration.

    Args:
        args: Parsed arguments
        formatter: Output formatter

    Returns:
        Configured EmbeddingManager or None if embeddings disabled
    """
    if args.no_embeddings:
        formatter.info("Embeddings disabled")
        return None

    try:
        embedding_manager = EmbeddingManager()

        # Build configuration from CLI arguments
        config_dict = {
            "provider": args.provider,
        }

        # Add optional parameters if provided
        if args.model:
            config_dict["model"] = args.model
        if args.api_key:
            config_dict["api_key"] = args.api_key
        if args.base_url:
            config_dict["base_url"] = args.base_url

        # Create EmbeddingConfig and validate
        config = EmbeddingConfig(**config_dict)

        # Use factory to create provider
        provider = EmbeddingProviderFactory.create_provider(config)
        embedding_manager.register_provider(provider, set_default=True)

        # Display success message with appropriate details
        if args.provider == "openai":
            model = config.get_model()
            formatter.success(f"Embedding provider: {args.provider}/{model}")
        elif args.provider in ["openai-compatible", "tei", "bge-in-icl"]:
            model = config.get_model()
            formatter.success(
                f"Embedding provider: {args.provider}/{model} at {args.base_url}"
            )
        else:
            formatter.success(f"Embedding provider: {args.provider}")

        return embedding_manager

    except Exception as e:
        formatter.warning(f"Failed to initialize embedding provider: {e}")
        formatter.info("Continuing without embeddings...")
        return None


async def _process_directory(
    indexing_coordinator,
    args: argparse.Namespace,
    formatter: OutputFormatter,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> None:
    """Process directory for indexing.

    Args:
        indexing_coordinator: Indexing coordinator service
        args: Parsed arguments
        formatter: Output formatter
        include_patterns: File inclusion patterns
        exclude_patterns: File exclusion patterns
    """
    formatter.info("Starting file processing...")

    # Convert patterns to service layer format
    processed_patterns = [f"**/{pattern}" for pattern in include_patterns]

    # Process directory using indexing coordinator
    result = await indexing_coordinator.process_directory(
        args.path, patterns=processed_patterns, exclude_patterns=exclude_patterns
    )

    if result["status"] in ["complete", "success"]:
        formatter.success("Processing complete:")
        processed_count = result.get('files_processed', result.get('processed', 0))
        formatter.info(f"   • Processed: {processed_count} files")
        formatter.info(f"   • Skipped: {result.get('skipped', 0)} files")
        formatter.info(f"   • Errors: {result.get('errors', 0)} files")
        formatter.info(f"   • Total chunks: {result.get('total_chunks', 0)}")

        # Report cleanup statistics
        cleanup = result.get("cleanup", {})
        if cleanup.get("deleted_files", 0) > 0 or cleanup.get("deleted_chunks", 0) > 0:
            formatter.info("🧹 Cleanup summary:")
            formatter.info(f"   • Deleted files: {cleanup.get('deleted_files', 0)}")
            formatter.info(f"   • Removed chunks: {cleanup.get('deleted_chunks', 0)}")

        # Show updated stats
        final_stats = await indexing_coordinator.get_stats()
        formatter.info(f"Final stats: {format_stats(final_stats)}")

    else:
        formatter.error(f"Processing failed: {result}")
        raise RuntimeError(f"Directory processing failed: {result}")


async def _generate_missing_embeddings(
    indexing_coordinator, formatter: OutputFormatter, exclude_patterns: list[str]
) -> None:
    """Generate missing embeddings for chunks.

    Args:
        indexing_coordinator: Indexing coordinator service
        formatter: Output formatter
        exclude_patterns: File patterns to exclude from embedding generation
    """
    formatter.info("Checking for missing embeddings...")

    embed_result = await indexing_coordinator.generate_missing_embeddings(
        exclude_patterns=exclude_patterns
    )

    if embed_result["status"] == "success":
        formatter.success(f"Generated {embed_result['generated']} missing embeddings")
    elif embed_result["status"] in ["up_to_date", "complete"]:
        if embed_result.get("message"):
            formatter.success(embed_result["message"])
        else:
            formatter.info("All embeddings up to date")
    else:
        formatter.warning(f"Embedding generation failed: {embed_result}")


__all__ = ["run_command"]
