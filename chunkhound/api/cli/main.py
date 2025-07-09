"""New modular CLI entry point for ChunkHound."""

import argparse
import asyncio
import multiprocessing
import os
import sys
from pathlib import Path

# Required for PyInstaller multiprocessing support
multiprocessing.freeze_support()


# Check for MCP command early to avoid any imports that trigger logging
def is_mcp_command() -> bool:
    """Check if this is an MCP command before any imports."""
    return len(sys.argv) >= 2 and sys.argv[1] == "mcp"


# Handle MCP command immediately before any imports
if is_mcp_command():
    # Set MCP mode environment early
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    # CRITICAL: Import numpy modules early for DuckDB threading safety in MCP mode
    # Must happen before any DuckDB operations in async/threading context
    # See: https://duckdb.org/docs/stable/clients/python/known_issues.html
    try:
        import numpy
        import numpy.core.multiarray
    except ImportError:
        pass

    # Import only what's needed for MCP
    from pathlib import Path

    # Parse MCP arguments minimally for database path only
    # The centralized config will handle all other settings
    if "--db" in sys.argv:
        db_index = sys.argv.index("--db")
        if db_index + 1 < len(sys.argv):
            db_path = Path(sys.argv[db_index + 1])
            # Only set if explicitly provided
            os.environ["CHUNKHOUND_DB_PATH"] = str(db_path)

    # Launch MCP server directly via import (fixes PyInstaller sys.executable recursion bug)
    try:
        from chunkhound.mcp_entry import main_sync

        main_sync()
    except ImportError as e:
        print(f"Error: Could not import chunkhound.mcp_entry: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        sys.exit(1)

    # This should not be reached, but added for safety
    sys.exit(0)

from loguru import logger

# All imports deferred to avoid early module loading during MCP detection
from .utils.validation import (
    ensure_database_directory,
    exit_on_validation_error,
    validate_path,
    validate_provider_args,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI.

    Args:
        verbose: Whether to enable verbose logging
    """
    logger.remove()

    if verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments.

    Args:
        args: Parsed arguments to validate
    """
    if args.command == "index":
        if not validate_path(args.path, must_exist=True, must_be_dir=True):
            exit_on_validation_error(f"Invalid path: {args.path}")

        # Get correct database path from unified config if not explicitly provided
        from .utils.config_helpers import args_to_config

        project_dir = Path(args.path) if hasattr(args, "path") else Path.cwd()
        
        # Load config (will automatically detect .chunkhound.json in project_dir)
        unified_config = args_to_config(args, project_dir)
        db_path = (
            Path(unified_config.database.path)
            if unified_config.database.path
            else Path(".chunkhound.db")
        )

        if not ensure_database_directory(db_path):
            exit_on_validation_error("Cannot access database directory")

        # Validate provider-specific arguments for index command using unified config
        if not args.no_embeddings:
            # Check if embedding config exists
            if not unified_config.embedding:
                logger.error("No embedding configuration found")
                exit_on_validation_error("Embedding configuration required")
            
            # Use unified config values instead of CLI args
            provider = unified_config.embedding.provider if hasattr(unified_config.embedding, 'provider') else None
            api_key = unified_config.embedding.api_key.get_secret_value() if unified_config.embedding.api_key else None
            base_url = unified_config.embedding.base_url
            model = unified_config.embedding.model
            
            
            # Use the standard validation function with config values
            if not validate_provider_args(provider, api_key, base_url, model):
                exit_on_validation_error("Provider validation failed")

    elif args.command == "mcp":
        # Get correct database path from unified config if not explicitly provided
        from .utils.config_helpers import args_to_config

        project_dir = Path.cwd()  # MCP doesn't have a path argument
        unified_config = args_to_config(args, project_dir)
        db_path = (
            Path(unified_config.database.path)
            if unified_config.database.path
            else Path(".chunkhound.db")
        )

        # Ensure database directory exists for MCP server
        if not ensure_database_directory(db_path):
            exit_on_validation_error("Cannot access database directory")


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the complete argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    # Import parsers dynamically to avoid early loading
    from .parsers import create_main_parser, setup_subparsers
    from .parsers.mcp_parser import add_mcp_subparser
    from .parsers.run_parser import add_run_subparser

    parser = create_main_parser()
    subparsers = setup_subparsers(parser)

    # Add command subparsers
    add_run_subparser(subparsers)
    add_mcp_subparser(subparsers)

    return parser


async def async_main() -> None:
    """Async main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Setup logging for non-MCP commands (MCP already handled above)
    setup_logging(getattr(args, "verbose", False))

    validate_args(args)

    try:
        if args.command == "index":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.run import run_command

            await run_command(args)
        else:
            logger.error(f"Unknown command: {args.command}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        logger.exception("Full error details:")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        sys.exit(0)
    except ImportError as e:
        # More specific handling for import errors
        logger.error(f"Import error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        # Check if this is a Pydantic validation error for missing provider
        error_str = str(e)
        if "validation error for EmbeddingConfig" in error_str and "provider" in error_str:
            logger.error(
                "Embedding provider must be specified. Choose from: openai, openai-compatible, tei, bge-in-icl\n"
                "Set via --provider, CHUNKHOUND_EMBEDDING__PROVIDER environment variable, or in config file."
            )
        else:
            logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
