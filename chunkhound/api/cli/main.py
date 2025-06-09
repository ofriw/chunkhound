"""New modular CLI entry point for ChunkHound."""

import argparse
import asyncio
import sys
from loguru import logger
from .commands import run_command, mcp_command, config_command
from .parsers import create_main_parser, setup_subparsers
from .parsers.run_parser import add_run_subparser
from .parsers.mcp_parser import add_mcp_subparser
from .parsers.config_parser import add_config_subparser
from .utils.validation import validate_path, ensure_database_directory, exit_on_validation_error


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
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments.
    
    Args:
        args: Parsed arguments to validate
    """
    if args.command == "run":
        if not validate_path(args.path, must_exist=True, must_be_dir=True):
            exit_on_validation_error(f"Invalid path: {args.path}")
        
        if not ensure_database_directory(args.db):
            exit_on_validation_error("Cannot access database directory")
            
        # Validate provider-specific arguments for run command
        if not args.no_embeddings:
            if args.provider in ['tei', 'bge-in-icl'] and not args.base_url:
                exit_on_validation_error(f"--base-url required for {args.provider} provider")
            
            if args.provider not in ['tei', 'bge-in-icl'] and not args.model:
                exit_on_validation_error(f"--model required for {args.provider} provider")
    
    elif args.command == "mcp":
        # Ensure database directory exists for MCP server
        if not ensure_database_directory(args.db):
            exit_on_validation_error("Cannot access database directory")


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the complete argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    # Create main parser
    parser = create_main_parser()
    
    # Set up subparsers
    subparsers = setup_subparsers(parser)
    
    # Add command subparsers
    add_run_subparser(subparsers)
    add_mcp_subparser(subparsers)
    add_config_subparser(subparsers)
    
    return parser


async def async_main() -> None:
    """Async main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(getattr(args, "verbose", False))
    validate_args(args)
    
    try:
        if args.command == "run":
            await run_command(args)
        elif args.command == "mcp":
            # MCP command is synchronous but we call it from async context
            mcp_command(args)
        elif args.command == "config":
            await config_command(args)
        else:
            logger.error(f"Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        logger.debug("Full error details:", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()