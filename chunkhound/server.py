"""Standalone API server script for ChunkHound.

This module provides a standalone server that can be run independently
of the CLI for API-only deployments.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from loguru import logger

from .api import app


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the server."""
    logger.remove()
    
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )


def run_server(
    host: str = "127.0.0.1",
    port: int = 7474,
    db_path: Optional[str] = None,
    verbose: bool = False,
    reload: bool = False
) -> None:
    """Run the ChunkHound API server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        db_path: Path to database file
        verbose: Enable verbose logging
        reload: Enable auto-reload for development
    """
    setup_logging(verbose)
    
    # Set database path environment variable
    if db_path:
        os.environ["CHUNKHOUND_DB_PATH"] = db_path
    elif "CHUNKHOUND_DB_PATH" not in os.environ:
        default_db = Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"
        os.environ["CHUNKHOUND_DB_PATH"] = str(default_db)
    
    logger.info(f"Starting ChunkHound API server on {host}:{port}")
    logger.info(f"Database: {os.environ['CHUNKHOUND_DB_PATH']}")
    
    uvicorn.run(
        "chunkhound.api:app",
        host=host,
        port=port,
        log_level="info" if verbose else "warning",
        reload=reload,
        access_log=verbose
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ChunkHound API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=7474, help="Port to listen on")
    parser.add_argument("--db", help="Database file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    run_server(
        host=args.host,
        port=args.port,
        db_path=args.db,
        verbose=args.verbose,
        reload=args.reload
    )