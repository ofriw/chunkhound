"""ChunkHound MCP (Model Context Protocol) implementation.

This package provides both stdio and HTTP servers for integrating
ChunkHound with AI assistants like Claude.

The architecture uses a base class pattern to share common initialization
and lifecycle management between server types while respecting their
protocol-specific constraints.
"""

from .base import MCPServerBase
from .tools import TOOL_REGISTRY

# Transport servers are intentionally not imported at package import time to
# avoid optional dependency failures (e.g., FastMCP, mcp SDK). Import them
# directly from their modules when needed:
#   from chunkhound.mcp.http_server import HttpMCPServer
#   from chunkhound.mcp.stdio import StdioMCPServer

__all__ = ["MCPServerBase", "TOOL_REGISTRY"]
