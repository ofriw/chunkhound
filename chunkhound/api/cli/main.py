"""New modular CLI entry point for ChunkHound."""

import argparse
import asyncio
import sys
import os

# Check for MCP command early to avoid any imports that trigger logging
def is_mcp_command():
    """Check if this is an MCP command before any imports."""
    return len(sys.argv) >= 2 and sys.argv[1] == "mcp"

# Handle MCP command immediately before any imports
if is_mcp_command():
    # Set MCP mode environment early
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    
    # Import only what's needed for MCP
    from pathlib import Path
    import subprocess
    
    # Parse MCP arguments minimally
    db_path = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"
    if "--db" in sys.argv:
        db_index = sys.argv.index("--db")
        if db_index + 1 < len(sys.argv):
            db_path = Path(sys.argv[db_index + 1])
    
    # Launch MCP server directly
    mcp_launcher_path = Path(__file__).parent.parent.parent.parent / "mcp_launcher.py"
    cmd = [sys.executable, str(mcp_launcher_path), "--db", str(db_path)]
    
    process = subprocess.run(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    sys.exit(process.returncode)

from loguru import logger
# All imports deferred to avoid early module loading during MCP detection
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
    # Import parsers dynamically to avoid early loading
    from .parsers import create_main_parser, setup_subparsers
    from .parsers.run_parser import add_run_subparser
    from .parsers.mcp_parser import add_mcp_subparser
    from .parsers.config_parser import add_config_subparser

    parser = create_main_parser()
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
    
    # Setup logging for non-MCP commands (MCP already handled above)
    setup_logging(getattr(args, "verbose", False))
    def validate_args(args):
        """Validate arguments."""
        # Add any validation logic here if needed
        pass
    
    validate_args(args)
    
    try:
        if args.command == "run":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.run import run_command
            await run_command(args)
        elif args.command == "config":
            # Dynamic import to avoid early chunkhound module loading
            from .commands.config import config_command
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