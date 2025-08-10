"""New modular CLI entry point for ChunkHound."""

import argparse
import asyncio
import multiprocessing
import sys

from loguru import logger

from .utils.config_factory import create_validated_config

# Required for PyInstaller multiprocessing support
multiprocessing.freeze_support()


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
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format=(
                "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
                "<level>{message}</level>"
            ),
        )


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

    # Validate args and create config
    config, validation_errors = create_validated_config(args, args.command)

    if validation_errors:
        for error in validation_errors:
            logger.error(f"Error: {error}")
        sys.exit(1)

    try:
        if args.command == "index":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.run import run_command

            await run_command(args, config)
        elif args.command == "mcp":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.mcp import mcp_command

            await mcp_command(args, config)
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
        if (
            "validation error for EmbeddingConfig" in error_str
            and "provider" in error_str
        ):
            logger.error(
                "Embedding provider must be specified. "
                "Choose from: openai, openai-compatible, tei\n"
                "Set via --provider, CHUNKHOUND_EMBEDDING__PROVIDER environment "
                "variable, or in config file."
            )
        else:
            logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
