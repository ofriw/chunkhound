"""Run command module - handles directory indexing and file watching operations."""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound import __version__
from chunkhound.embeddings import (
    EmbeddingManager,
    create_openai_compatible_provider,
    create_openai_provider,
    create_tei_provider,
)
from chunkhound.signal_coordinator import CLICoordinator
from chunkhound.database_factory import create_database_with_dependencies
from registry import configure_registry, create_indexing_coordinator

from ..parsers.run_parser import process_batch_arguments
from ..utils.config_helpers import (
    args_to_config,
    create_legacy_registry_config,
    validate_config_for_command,
)
from ..utils.output import OutputFormatter, format_stats
from ..utils.validation import (
    ensure_database_directory,
    validate_file_patterns,
    validate_numeric_args,
    validate_path,
    validate_provider_args,
)


async def run_command(args: argparse.Namespace) -> None:
    """Execute the run command using the service layer.

    Args:
        args: Parsed command-line arguments
    """
    # Initialize output formatter
    formatter = OutputFormatter(verbose=args.verbose)

    # Load unified configuration first
    project_dir = Path(args.path) if hasattr(args, 'path') else Path.cwd()
    unified_config = args_to_config(args, project_dir)
    
    # Use consistent database path resolution between MCP and CLI
    # Prefer environment variable, then explicit CLI arg, then project-aware default
    if env_db_path := os.environ.get("CHUNKHOUND_DB_PATH"):
        db_path = Path(env_db_path)
    elif hasattr(args, 'db') and args.db is not None:
        db_path = Path(args.db)
    else:
        # Use project-aware database path like MCP server
        from chunkhound.utils.project_detection import get_project_database_path
        db_path = get_project_database_path()

    # Display startup information
    formatter.info(f"Starting ChunkHound v{__version__}")
    formatter.info(f"Processing directory: {args.path}")
    formatter.info(f"Database: {db_path}")

    # Process and validate batch arguments (includes deprecation warnings)
    process_batch_arguments(args)

    # Validate arguments - update args.db to use config value for validation
    args.db = db_path
    if not _validate_run_arguments(args, formatter):
        sys.exit(1)

    # Initialize CLI coordinator for database access coordination
    cli_coordinator = CLICoordinator(db_path)

    try:
        # Check for running MCP server and coordinate if needed
        await _handle_mcp_coordination(cli_coordinator, formatter)

        # Set up file patterns using unified config (already loaded)
        include_patterns, exclude_patterns = _setup_file_patterns_from_config(unified_config, args)
        formatter.info(f"Include patterns: {include_patterns}")
        formatter.info(f"Exclude patterns: {exclude_patterns}")

        # Create database using unified factory to ensure consistent initialization
        config = _build_registry_config(args, unified_config)
        # Note: Not creating Database here - the indexing_coordinator is sufficient for CLI operations
        configure_registry(config)
        indexing_coordinator = create_indexing_coordinator()

        formatter.success(f"Service layer initialized: {args.db}")

        # Get initial stats
        initial_stats = await indexing_coordinator.get_stats()
        formatter.info(f"Initial stats: {format_stats(initial_stats)}")

        # Perform directory processing
        await _process_directory(
            indexing_coordinator, args, formatter,
            include_patterns, exclude_patterns
        )

        # Generate missing embeddings if enabled
        if not args.no_embeddings:
            await _generate_missing_embeddings(indexing_coordinator, formatter, exclude_patterns)

        # Start watch mode if enabled
        if args.watch:
            formatter.info("Initial indexing complete. Starting watch mode...")
            await _start_watch_mode(args, indexing_coordinator, formatter, exclude_patterns)
        formatter.success("Run command completed successfully")

    except KeyboardInterrupt:
        formatter.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        formatter.error(f"Run command failed: {e}")
        logger.exception("Run command error details")
        sys.exit(1)
    finally:
        # Restore database access to MCP server if coordination was active
        cli_coordinator.release_database_access()


def _validate_run_arguments(args: argparse.Namespace, formatter: OutputFormatter) -> bool:
    """Validate run command arguments.

    Args:
        args: Parsed arguments
        formatter: Output formatter

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
        if not validate_provider_args(args.provider, args.api_key, args.base_url, args.model):
            return False

    # Validate file patterns
    if not validate_file_patterns(args.include, args.exclude):
        return False

    # Validate numeric arguments (batch validation now handled in process_batch_arguments)
    if not validate_numeric_args(args.debounce_ms, getattr(args, 'embedding_batch_size', 100)):
        return False

    return True


async def _handle_mcp_coordination(cli_coordinator: CLICoordinator, formatter: OutputFormatter) -> None:
    """Handle MCP server coordination for database access.

    Args:
        cli_coordinator: CLI coordinator instance
        formatter: Output formatter
    """
    if cli_coordinator.signal_coordinator.is_mcp_server_running():
        mcp_pid = cli_coordinator.signal_coordinator.process_detector.get_server_pid()
        formatter.info(f"🔍 Detected running MCP server (PID {mcp_pid})")

        if not cli_coordinator.request_database_access():
            formatter.error("❌ Failed to coordinate database access. Please stop the MCP server or use a different database file.")
            sys.exit(1)


def _build_registry_config(args: argparse.Namespace, unified_config: Any = None) -> dict[str, Any]:
    """Build configuration for the provider registry.

    Args:
        args: Parsed arguments
        unified_config: Pre-loaded unified configuration (optional)

    Returns:
        Configuration dictionary
    """
    # Use provided unified configuration or load it
    if unified_config is None:
        project_dir = Path(args.path) if hasattr(args, 'path') else Path.cwd()
        unified_config = args_to_config(args, project_dir)
    
    # Validate configuration for the index command
    validation_errors = validate_config_for_command(unified_config, 'index')
    if validation_errors:
        for error in validation_errors:
            logger.error(f"Configuration error: {error}")
        raise ValueError("Invalid configuration")
    
    # Convert to legacy registry format
    return create_legacy_registry_config(
        unified_config, 
        no_embeddings=getattr(args, 'no_embeddings', False)
    )


def _setup_file_patterns_from_config(config: Any, args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Set up file inclusion and exclusion patterns from unified config.

    Args:
        config: Unified configuration object
        args: Parsed arguments (for fallback)

    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    # Trust config layer to provide complete patterns, allow CLI override
    if hasattr(args, 'include') and args.include:
        include_patterns = args.include  # CLI override
    else:
        include_patterns = config.indexing.include_patterns  # Config layer (now complete)

    # Use effective exclude patterns that include .gitignore patterns
    project_dir = Path(args.path) if hasattr(args, 'path') else Path.cwd()
    exclude_patterns = config.indexing.get_effective_exclude_patterns(project_dir)
    if hasattr(args, 'exclude') and args.exclude:
        exclude_patterns.extend(args.exclude)

    return include_patterns, exclude_patterns


async def _setup_embedding_manager(args: argparse.Namespace, formatter: OutputFormatter) -> EmbeddingManager | None:
    """Set up embedding manager based on provider configuration.

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

        if args.provider == "openai":
            model = args.model or "text-embedding-3-small"
            provider = create_openai_provider(
                api_key=args.api_key,
                base_url=args.base_url,
                model=model,
            )
            embedding_manager.register_provider(provider, set_default=True)
            formatter.success(f"Embedding provider: {args.provider}/{model}")

        elif args.provider == "openai-compatible":
            model = args.model or "auto-detected"
            provider = create_openai_compatible_provider(
                base_url=args.base_url,
                model=model,
                api_key=args.api_key,
            )
            embedding_manager.register_provider(provider, set_default=True)
            formatter.success(f"Embedding provider: {args.provider}/{model} at {args.base_url}")

        elif args.provider == "tei":
            provider = create_tei_provider(
                base_url=args.base_url,
                model=args.model,
            )
            embedding_manager.register_provider(provider, set_default=True)
            formatter.success(f"Embedding provider: {args.provider} at {args.base_url}")

        elif args.provider == "bge-in-icl":
            # BGE-IN-ICL provider setup would go here
            formatter.warning("BGE-IN-ICL provider not yet implemented in service layer")
            return None

        else:
            formatter.warning(f"Unknown embedding provider: {args.provider}")
            return None

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
    exclude_patterns: list[str]
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
        args.path,
        patterns=processed_patterns,
        exclude_patterns=exclude_patterns
    )

    if result["status"] in ["complete", "success"]:
        formatter.success("Processing complete:")
        formatter.info(f"   • Processed: {result.get('files_processed', result.get('processed', 0))} files")
        formatter.info(f"   • Skipped: {result.get('skipped', 0)} files")
        formatter.info(f"   • Errors: {result.get('errors', 0)} files")
        formatter.info(f"   • Total chunks: {result.get('total_chunks', 0)}")

        # Report cleanup statistics
        cleanup = result.get('cleanup', {})
        if cleanup.get('deleted_files', 0) > 0 or cleanup.get('deleted_chunks', 0) > 0:
            formatter.info("🧹 Cleanup summary:")
            formatter.info(f"   • Deleted files: {cleanup.get('deleted_files', 0)}")
            formatter.info(f"   • Removed chunks: {cleanup.get('deleted_chunks', 0)}")

        # Show updated stats
        final_stats = await indexing_coordinator.get_stats()
        formatter.info(f"Final stats: {format_stats(final_stats)}")

    else:
        formatter.error(f"Processing failed: {result}")
        raise RuntimeError(f"Directory processing failed: {result}")


async def _generate_missing_embeddings(indexing_coordinator, formatter: OutputFormatter, exclude_patterns: list[str]) -> None:
    """Generate missing embeddings for chunks.

    Args:
        indexing_coordinator: Indexing coordinator service
        formatter: Output formatter
        exclude_patterns: File patterns to exclude from embedding generation
    """
    formatter.info("Checking for missing embeddings...")

    embed_result = await indexing_coordinator.generate_missing_embeddings(exclude_patterns=exclude_patterns)

    if embed_result["status"] == "success":
        formatter.success(f"Generated {embed_result['generated']} missing embeddings")
    elif embed_result["status"] in ["up_to_date", "complete"]:
        if embed_result.get("message"):
            formatter.success(embed_result["message"])
        else:
            formatter.info("All embeddings up to date")
    else:
        formatter.warning(f"Embedding generation failed: {embed_result}")


async def _start_watch_mode(args: argparse.Namespace, indexing_coordinator, formatter: OutputFormatter, exclude_patterns: list[str]) -> None:
    """Start file watching mode.

    Args:
        args: Parsed arguments
        indexing_coordinator: Indexing coordinator service
        formatter: Output formatter
        exclude_patterns: File patterns to exclude from processing
    """
    formatter.info("🔍 Starting file watching mode...")

    try:
        # Import file watcher components
        from chunkhound.file_watcher import WATCHDOG_AVAILABLE, FileWatcherManager

        if not WATCHDOG_AVAILABLE:
            formatter.error("❌ File watching requires the 'watchdog' package. Install with: pip install watchdog")
            return

        # Initialize file watcher
        file_watcher_manager = FileWatcherManager()

        # Create callback for file changes
        async def process_cli_file_change(file_path: Path, event_type: str):
            """Process file changes in CLI mode."""
            try:
                if event_type == 'deleted':
                    removed_chunks = await indexing_coordinator.remove_file(str(file_path))
                    if removed_chunks > 0:
                        formatter.info(f"🗑️  Removed {removed_chunks} chunks from deleted file: {file_path}")
                else:
                    # Process file (created, modified, moved)
                    if file_path.exists() and file_path.is_file():
                        # Check if file should be excluded before processing
                        from fnmatch import fnmatch
                        should_exclude = False
                        
                        # Get relative path from watch directory for pattern matching
                        watch_dir = Path(args.path) if hasattr(args, 'path') else Path.cwd()
                        try:
                            rel_path = file_path.relative_to(watch_dir)
                        except ValueError:
                            # File is not under watch directory, use absolute path
                            rel_path = file_path
                        
                        for exclude_pattern in exclude_patterns:
                            # Check both relative and absolute paths
                            if (fnmatch(str(rel_path), exclude_pattern) or 
                                fnmatch(str(file_path), exclude_pattern)):
                                should_exclude = True
                                break
                        
                        if should_exclude:
                            formatter.verbose_info(f"🚫 Skipped excluded file: {file_path}")
                            return
                        
                        result = await indexing_coordinator.process_file(file_path)
                        if result["status"] == "success":
                            formatter.info(f"📝 Processed {event_type} file: {file_path} ({result['chunks']} chunks)")
                        elif result["status"] not in ["skipped", "no_content", "no_chunks"]:
                            formatter.warning(f"⚠️  Failed to process {event_type} file: {file_path} - {result.get('error', 'unknown error')}")
            except Exception as e:
                formatter.error(f"❌ Error processing {event_type} for {file_path}: {e}")

        # Initialize file watcher with callback
        watch_paths = [args.path] if args.path.is_dir() else [args.path.parent]
        watcher_success = await file_watcher_manager.initialize(
            process_cli_file_change,
            watch_paths=watch_paths
        )

        if not watcher_success:
            formatter.error("❌ Failed to initialize file watcher")
            return

        formatter.success("✅ File watching started. Press Ctrl+C to stop.")

        # Keep watching until interrupted
        try:
            while True:
                await asyncio.sleep(1.0)
        except KeyboardInterrupt:
            formatter.info("🛑 File watching stopped by user")
        finally:
            await file_watcher_manager.cleanup()

    except ImportError as e:
        formatter.error(f"❌ Failed to import file watching components: {e}")
    except Exception as e:
        formatter.error(f"❌ File watching failed: {e}")


__all__ = ["run_command"]
