#!/usr/bin/env python3
"""
ChunkHound MCP Entry Point - Dedicated script for Model Context Protocol server
Suppresses all logging before any chunkhound module imports to ensure clean JSON-RPC
"""

import logging
import os

# CRITICAL: Suppress ALL logging BEFORE any other imports
# This must happen before importing loguru or any chunkhound modules
logging.disable(logging.CRITICAL)
for logger_name in ['', 'mcp', 'server', 'fastmcp', 'registry', 'chunkhound']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

# Note: Do NOT redirect stderr to /dev/null as it breaks MCP SDK's internal error handling
# The MCP SDK requires stderr for proper TaskGroup error handling
# Instead, rely on logging.disable() and loguru suppression for clean JSON-RPC output

# Set environment variable to signal MCP mode
os.environ["CHUNKHOUND_MCP_MODE"] = "1"

# CRITICAL: Import numpy modules early for DuckDB threading safety
# Must happen before any DuckDB operations in async/threading context
# See: https://duckdb.org/docs/stable/clients/python/known_issues.html
try:
    import numpy
    import numpy.core.multiarray
except ImportError:
    pass

# Suppress loguru logger
try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
except ImportError:
    pass

async def main() -> None:
    """Main entry point for MCP server with proper logging suppression."""
    # Database path should be set via environment variable
    db_path = os.environ.get("CHUNKHOUND_DB_PATH")
    if not db_path:
        from pathlib import Path
        db_path = str(Path.home() / ".cache" / "chunkhound" / "chunks.duckdb")
        os.environ["CHUNKHOUND_DB_PATH"] = db_path

    # Ensure embedding API keys are available for semantic search
    # This handles cases where keys might be set in parent process but not inherited

    # Handle new unified API key
    chunkhound_api_key = os.environ.get("CHUNKHOUND_EMBEDDING_API_KEY")
    if chunkhound_api_key:
        os.environ["CHUNKHOUND_EMBEDDING_API_KEY"] = chunkhound_api_key

    # Handle legacy OpenAI API key for backward compatibility
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    # Now import and run the MCP server
    from chunkhound.mcp_server import main as run_mcp_server
    await run_mcp_server()


def main_sync() -> None:
    """Synchronous entry point for CLI integration."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
