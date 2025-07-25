"""New modular CLI entry point for ChunkHound."""

import argparse
import asyncio
import multiprocessing
import os
import sys
from pathlib import Path

# Required for PyInstaller multiprocessing support
multiprocessing.freeze_support()

from loguru import logger

# Imports deferred for optimal module loading
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

        # Get correct database path from unified config
        from chunkhound.core.config.config import Config

        # Load config using unified pattern
        unified_config = Config(args=args)
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
        # Get correct database path from unified config
        from chunkhound.core.config.config import Config

        # Load config using unified pattern
        unified_config = Config(args=args)
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
        elif args.command == "mcp":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.mcp import mcp_command

            await mcp_command(args)
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
