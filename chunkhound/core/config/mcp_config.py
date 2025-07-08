"""MCP (Model Context Protocol) server configuration for ChunkHound.

This module provides configuration for the MCP server including
transport type, network settings, and server behavior.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MCPConfig(BaseModel):
    """Configuration for MCP server operation.
    
    Controls how the MCP server operates including transport type,
    network configuration, and server behavior.
    """
    
    # Transport configuration
    transport: Literal["stdio", "http"] = Field(
        default="stdio",
        description="Transport type for MCP server"
    )
    
    # HTTP transport settings
    host: str = Field(
        default="localhost",
        description="Host to bind HTTP server to"
    )
    
    port: int = Field(
        default=3000,
        ge=1024,
        le=65535,
        description="Port for HTTP server"
    )
    
    cors: bool = Field(
        default=False,
        description="Enable CORS for HTTP transport"
    )
    
    # Server behavior
    max_response_tokens: int = Field(
        default=20000,
        ge=1000,
        le=50000,
        description="Maximum tokens in a single response"
    )
    
    request_timeout: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )
    
    # Performance settings
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent requests to handle"
    )
    
    response_cache_size: int = Field(
        default=100,
        ge=0,
        le=1000,
        description="Size of response cache (0 to disable)"
    )
    
    # Security settings
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed origins for CORS (only used when cors=True)"
    )
    
    @field_validator("host")
    def validate_host(cls, v: str) -> str:
        """Validate host address."""
        if not v:
            raise ValueError("Host cannot be empty")
        
        # Basic validation - actual implementation might be more thorough
        if v not in ["localhost", "127.0.0.1", "0.0.0.0"] and not v.replace(".", "").isdigit():
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