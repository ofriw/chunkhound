"""MCP (Model Context Protocol) server configuration for ChunkHound.

This module provides configuration for the MCP server including
transport type, network settings, and server behavior.
"""

import argparse
import os
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class MCPConfig(BaseModel):
    """Configuration for MCP server operation.

    Controls how the MCP server operates including transport type,
    network configuration, and server behavior.
    """

    # Transport configuration
    transport: Literal["stdio", "http"] = Field(
        default="stdio", description="Transport type for MCP server"
    )

    # HTTP transport settings
    host: str = Field(default="localhost", description="Host to bind HTTP server to")

    port: int = Field(
        default=3000, description="Port for HTTP server (0 for OS-assigned port)"
    )

    @field_validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate port number - allow 0 for OS-assigned port."""
        if v == 0:
            return v  # Special case: 0 means OS-assigned port
        if v < 1024 or v > 65535:
            raise ValueError("Port must be 0 (OS-assigned) or between 1024-65535")
        return v

    cors: bool = Field(default=False, description="Enable CORS for HTTP transport")

    # Server behavior
    max_response_tokens: int = Field(
        default=20000,
        ge=1000,
        le=50000,
        description="Maximum tokens in a single response",
    )

    request_timeout: int = Field(
        default=60, ge=1, le=300, description="Request timeout in seconds"
    )

    # Performance settings
    max_concurrent_requests: int = Field(
        default=10, ge=1, le=100, description="Maximum concurrent requests to handle"
    )

    response_cache_size: int = Field(
        default=100, ge=0, le=1000, description="Size of response cache (0 to disable)"
    )

    # Security settings
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed origins for CORS (only used when cors=True)",
    )

    @field_validator("host")
    def validate_host(cls, v: str) -> str:
        """Validate host address."""
        if not v:
            raise ValueError("Host cannot be empty")

        # Basic validation - actual implementation might be more thorough
        if (
            v not in ["localhost", "127.0.0.1", "0.0.0.0"]
            and not v.replace(".", "").isdigit()
        ):
            # Simple check - in production you'd want proper IP/hostname validation
            if not all(c.isalnum() or c in ".-" for c in v):
                raise ValueError(f"Invalid host: {v}")

        return v

    @field_validator("allowed_origins")
    def validate_origins(cls, v: list[str], info) -> list[str]:
        """Validate CORS origins when CORS is enabled."""
        cors = info.data.get("cors", False) if info.data else False

        if cors and not v:
            # Ensure at least one origin when CORS is enabled
            return ["*"]

        # Remove duplicates
        return list(set(v))

    def get_server_url(self) -> str:
        """Get the full server URL for HTTP transport."""
        if self.transport != "http":
            raise ValueError("Server URL only available for HTTP transport")

        return f"http://{self.host}:{self.port}"

    def is_http_transport(self) -> bool:
        """Check if using HTTP transport."""
        return self.transport == "http"

    def is_stdio_transport(self) -> bool:
        """Check if using stdio transport."""
        return self.transport == "stdio"

    def get_transport_config(self) -> dict:
        """Get transport-specific configuration."""
        if self.transport == "http":
            return {
                "host": self.host,
                "port": self.port,
                "cors": self.cors,
                "allowed_origins": self.allowed_origins if self.cors else [],
                "max_concurrent_requests": self.max_concurrent_requests,
            }
        else:  # stdio
            return {
                "max_concurrent_requests": 1,  # stdio is inherently sequential
            }

    @classmethod
    def add_cli_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add MCP-related CLI arguments."""
        parser.add_argument(
            "--stdio",
            action="store_true",
            help="Use stdio transport (default)",
        )

        parser.add_argument(
            "--http",
            action="store_true",
            help="Use HTTP transport instead of stdio",
        )

        parser.add_argument(
            "--port",
            type=int,
            help="Port for HTTP transport",
        )

        parser.add_argument(
            "--host",
            help="Host for HTTP transport",
        )

        parser.add_argument(
            "--cors",
            action="store_true",
            help="Enable CORS for HTTP transport",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load MCP config from environment variables."""
        config = {}

        if transport := os.getenv("CHUNKHOUND_MCP__TRANSPORT"):
            config["transport"] = transport
        if port := os.getenv("CHUNKHOUND_MCP__PORT"):
            config["port"] = int(port)
        if host := os.getenv("CHUNKHOUND_MCP__HOST"):
            config["host"] = host
        if cors := os.getenv("CHUNKHOUND_MCP__CORS"):
            config["cors"] = cors.lower() in ("true", "1", "yes")

        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract MCP config from CLI arguments."""
        overrides = {}

        # Handle transport boolean flags mapping to transport string
        if hasattr(args, "http") and args.http:
            overrides["transport"] = "http"
        elif hasattr(args, "stdio") and args.stdio:
            overrides["transport"] = "stdio"

        if hasattr(args, "port") and args.port is not None:
            overrides["port"] = args.port
        if hasattr(args, "host") and args.host is not None:
            overrides["host"] = args.host
        if hasattr(args, "cors") and args.cors:
            overrides["cors"] = args.cors

        return overrides

    def __repr__(self) -> str:
        """String representation of MCP configuration."""
        if self.transport == "http":
            return (
                f"MCPConfig("
                f"transport={self.transport}, "
                f"url={self.get_server_url()}, "
                f"cors={self.cors})"
            )
        else:
            return f"MCPConfig(transport={self.transport})"
