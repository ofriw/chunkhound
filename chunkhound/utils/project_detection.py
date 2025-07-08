"""Project directory detection utilities for MCP server."""

import os
from pathlib import Path


def find_project_root(start_path: Path | None = None) -> Path:
    """
    Find the project root directory by looking for markers.

    Searches upward from start_path for:
    1. .chunkhound.db or chunkhound.db (existing database)
    2. .git directory (git repository root)
    3. pyproject.toml, package.json, etc. (project files)

    Args:
        start_path: Starting directory (defaults to cwd)

    Returns:
        Path to project root directory
    """
    if start_path is None:
        start_path = Path.cwd()

    current = Path(start_path).resolve()

    # Project markers in order of preference
    markers = [
        ".chunkhound.db",
        ".git",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        ".chunkhound.json",
    ]

    # Search upward for project markers
    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    # If no markers found, use original cwd
    return Path.cwd()


def get_project_database_path() -> Path:
    """
    Get the database path for the current project.

    Returns:
        Path to database file in project root
    """
    # Use the config system which handles env vars
    from chunkhound.core.config.config import get_config
    config = get_config()
    
    if config.database.path:
        return Path(config.database.path)

    # Find project root and use default database name
    project_root = find_project_root()
    return project_root / ".chunkhound" / "db"


def get_project_watch_paths() -> list[Path]:
    """
    Get watch paths for the current project.

    Returns:
        List of paths to watch (defaults to project root)
    """
    # Check environment variable first
    if env_paths := os.environ.get("CHUNKHOUND_WATCH_PATHS"):
        return [Path(p.strip()) for p in env_paths.split(",") if p.strip()]

    # Default to project root
    return [find_project_root()]
