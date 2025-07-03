"""Output formatting utilities for ChunkHound CLI commands."""

import json
import os
import sys
from datetime import datetime
from typing import Any


class OutputFormatter:
    """Handles consistent output formatting across CLI commands."""

    def __init__(self, verbose: bool = False):
        """Initialize output formatter.

        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose

    def info(self, message: str) -> None:
        """Print an info message.

        Args:
            message: Message to print
        """
        print(f"ℹ️  {message}")

    def success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: Message to print
        """
        print(f"✅ {message}")

    def warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Message to print
        """
        print(f"⚠️  {message}")

    def error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: Message to print
        """
        # Skip stderr output in MCP mode to avoid JSON-RPC interference
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            print(f"❌ {message}", file=sys.stderr)

    def verbose_info(self, message: str) -> None:
        """Print a verbose info message if verbose mode is enabled.

        Args:
            message: Message to print
        """
        if self.verbose:
            print(f"🔍 {message}")

    def json_output(self, data: dict[str, Any]) -> None:
        """Print data as formatted JSON.

        Args:
            data: Data to output as JSON
        """
        print(json.dumps(data, indent=2, default=str))

    def table_header(self, headers: list[str], widths: list[int] | None = None) -> None:
        """Print a table header.

        Args:
            headers: Column headers
            widths: Optional column widths
        """
        if widths:
            row = " | ".join(
                header.ljust(width) for header, width in zip(headers, widths)
            )
        else:
            row = " | ".join(headers)

        print(row)
        print("-" * len(row))

    def table_row(self, values: list[str], widths: list[int] | None = None) -> None:
        """Print a table row.

        Args:
            values: Column values
            widths: Optional column widths
        """
        if widths:
            row = " | ".join(
                str(value).ljust(width) for value, width in zip(values, widths)
            )
        else:
            row = " | ".join(str(value) for value in values)

        print(row)


def format_stats(stats: dict[str, Any]) -> str:
    """Format database statistics for display.

    Args:
        stats: Statistics dictionary from database

    Returns:
        Formatted statistics string
    """
    files = stats.get("files", 0)
    chunks = stats.get("chunks", 0)
    embeddings = stats.get("embeddings", 0)

    return f"{files} files, {chunks} chunks, {embeddings} embeddings"


def format_health_status(status: dict[str, Any]) -> str:
    """Format health status for display.

    Args:
        status: Health status dictionary

    Returns:
        Formatted status string with emoji
    """
    if status.get("healthy", False):
        response_time = status.get("response_time_ms", 0)
        return f"🟢 Healthy ({response_time}ms)"
    else:
        error = status.get("error", "Unknown error")
        return f"🔴 Unhealthy: {error}"


def format_file_size(size_bytes: float) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_timestamp(timestamp: datetime | None = None) -> str:
    """Format timestamp for display.

    Args:
        timestamp: Timestamp to format, defaults to current time

    Returns:
        Formatted timestamp string
    """
    if timestamp is None:
        timestamp = datetime.now()

    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def format_progress(current: int, total: int, prefix: str = "") -> str:
    """Format progress indicator.

    Args:
        current: Current progress value
        total: Total value
        prefix: Optional prefix text

    Returns:
        Formatted progress string
    """
    percentage = (current / total * 100) if total > 0 else 0
    prefix_text = f"{prefix} " if prefix else ""
    return f"{prefix_text}({current}/{total}, {percentage:.1f}%)"


def format_server_info(server_config: dict[str, Any]) -> list[str]:
    """Format server configuration for table display.

    Args:
        server_config: Server configuration dictionary

    Returns:
        List of formatted values for table row
    """
    name = server_config.get("name", "Unknown")
    server_type = server_config.get("type", "Unknown")
    base_url = server_config.get("base_url", "N/A")
    model = server_config.get("model", "Auto")
    enabled = "Yes" if server_config.get("enabled", False) else "No"
    is_default = "Yes" if server_config.get("default", False) else "No"

    # Truncate long URLs for display
    if len(base_url) > 40:
        base_url = base_url[:37] + "..."

    return [name, server_type, base_url, model, enabled, is_default]


def print_banner(title: str, subtitle: str | None = None) -> None:
    """Print a banner with title and optional subtitle.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    print("=" * 60)
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print("=" * 60)
    print()


def print_section(title: str) -> None:
    """Print a section header.

    Args:
        title: Section title
    """
    print(f"\n{title}")
    print("-" * len(title))
