"""ChunkHound MCP (Model Context Protocol) implementation.

This package provides both stdio and HTTP servers for integrating
ChunkHound with AI assistants like Claude.

The architecture uses a base class pattern to share common initialization
and lifecycle management between server types while respecting their
protocol-specific constraints.
"""

from .base import MCPServerBase
from .http_server import HttpMCPServer
from .stdio import StdioMCPServer
from .tools import TOOL_REGISTRY

__all__ = ["MCPServerBase", "StdioMCPServer", "HttpMCPServer", "TOOL_REGISTRY"]
