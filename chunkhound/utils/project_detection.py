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
        start_path: Starting directory (defaults to CHUNKHOUND_PROJECT_ROOT env var or cwd)

    Returns:
        Path to project root directory
    """
    if start_path is None:
        # Check environment variable first, then fall back to cwd
        project_root_env = os.environ.get("CHUNKHOUND_PROJECT_ROOT")
        if project_root_env:
            start_path = Path(project_root_env)
        else:
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

    # If no markers found, use project root env var or original cwd
    project_root_env = os.environ.get("CHUNKHOUND_PROJECT_ROOT")
    if project_root_env:
        return Path(project_root_env)
    return Path.cwd()


def get_project_database_path() -> Path:
    """
    Get the database path for the current project.
    
    NOTE: This function is deprecated. The Config class now handles
    database path resolution internally. Use Config().database.path instead.

    Returns:
        Path to database file in project root
    """
    # Check environment variable first
    db_path_env = os.environ.get("CHUNKHOUND_DATABASE__PATH") or os.environ.get("CHUNKHOUND_DB_PATH")
    if db_path_env:
        return Path(db_path_env)

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
