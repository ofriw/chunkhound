#!/usr/bin/env python3
"""
ChunkHound MCP Entry Point - Dedicated script for Model Context Protocol server
Suppresses all logging before any chunkhound module imports to ensure clean JSON-RPC
"""

import os
import sys
import logging

# CRITICAL: Suppress ALL logging BEFORE any other imports
# This must happen before importing loguru or any chunkhound modules
logging.disable(logging.CRITICAL)
for logger_name in ['', 'mcp', 'server', 'fastmcp', 'registry', 'chunkhound']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

# Redirect stderr to /dev/null to suppress all output during MCP mode
if os.name != 'nt':  # Unix-like systems
    devnull = open(os.devnull, 'w')
    sys.stderr = devnull
else:  # Windows
    devnull = open('nul', 'w')
    sys.stderr = devnull

# Set environment variable to signal MCP mode
os.environ["CHUNKHOUND_MCP_MODE"] = "1"

# Suppress loguru logger
try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
except ImportError:
    pass

async def main():
    """Main entry point for MCP server with proper logging suppression."""
    # Database path should be set via environment variable
    db_path = os.environ.get("CHUNKHOUND_DB_PATH")
    if not db_path:
        from pathlib import Path
        db_path = str(Path.home() / ".cache" / "chunkhound" / "chunks.duckdb")
        os.environ["CHUNKHOUND_DB_PATH"] = db_path
    
    # Now import and run the MCP server
    from chunkhound.mcp_server import main as run_mcp_server
    await run_mcp_server()


def main_sync():
    """Synchronous entry point for CLI integration."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()