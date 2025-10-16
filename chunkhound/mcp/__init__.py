"""Lightweight MCP package initializer with lazy imports.

We avoid importing heavy transport dependencies (e.g., FastMCP) at import time
to prevent environment-specific import issues during test collection. Server
classes are resolved lazily either via getters or module-level __getattr__.
"""

from typing import TYPE_CHECKING

from .base import MCPServerBase
from .tools import TOOL_REGISTRY

if TYPE_CHECKING:  # type checkers only; avoids runtime imports
    from .http_server import HttpMCPServer as _HttpMCPServer
    from .stdio import StdioMCPServer as _StdioMCPServer


def get_http_server_class():
    """Return the HTTP MCP server class with a lazy import."""
    from .http_server import HttpMCPServer

    return HttpMCPServer


def get_stdio_server_class():
    """Return the stdio MCP server class with a lazy import."""
    from .stdio import StdioMCPServer

    return StdioMCPServer


def __getattr__(name: str):  # PEP 562: lazy attribute access on module
    if name == "HttpMCPServer":
        return get_http_server_class()
    if name == "StdioMCPServer":
        return get_stdio_server_class()
    raise AttributeError(name)


__all__ = [
    "MCPServerBase",
    "TOOL_REGISTRY",
    # Legacy names resolved lazily for compatibility
    "HttpMCPServer",
    "StdioMCPServer",
    # Explicit getters
    "get_http_server_class",
    "get_stdio_server_class",
]
