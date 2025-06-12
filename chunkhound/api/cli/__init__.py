"""ChunkHound CLI API package - modular command-line interface."""

# Removed eager imports to eliminate 958-module import cascade
# Commands are now imported lazily in main.py when needed

__all__ = [
    "run_command",
    "mcp_command", 
    "config_command",
]