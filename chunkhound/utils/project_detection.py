"""Project directory detection utilities for MCP server."""

import os
from pathlib import Path


def find_project_root(start_path: Path | None = None) -> Path:
    """
    Find project root directory using strict requirements.

    Project root is determined ONLY by:
    1. A positional CLI argument (passed as start_path)
    2. The presence of .chunkhound.json in the current directory
    3. Everything else is considered an error and terminates the process

    Args:
        start_path: Starting directory from CLI positional argument (optional)

    Returns:
        Path to project root directory

    Raises:
        SystemExit: If no valid project root can be determined
    """
    import sys

    if start_path is not None:
        # CLI positional argument provided - use it directly
        project_root = Path(start_path).resolve()
        if not project_root.exists():
            print(
                f"Error: Specified project directory does not exist: {project_root}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not project_root.is_dir():
            print(
                f"Error: Specified project path is not a directory: {project_root}",
                file=sys.stderr,
            )
            sys.exit(1)
        return project_root

    # No CLI argument - check for .chunkhound.json in current directory
    current_dir = Path.cwd()
    chunkhound_json = current_dir / ".chunkhound.json"

    if chunkhound_json.exists():
        return current_dir

    # No valid project root found - terminate with clear error
    print("Error: No ChunkHound project found.", file=sys.stderr)
    print(
        f"Expected .chunkhound.json in current directory: {current_dir}",
        file=sys.stderr,
    )
    print("Or provide a project directory as a positional argument.", file=sys.stderr)
    sys.exit(1)


def get_project_database_path() -> Path:
    """
    Get the database path for the current project.

    NOTE: This function is deprecated. The Config class now handles
    database path resolution internally. Use Config().database.path instead.

    Returns:
        Path to database file in project root
    """
    # Check environment variable first
    db_path_env = os.environ.get("CHUNKHOUND_DATABASE__PATH") or os.environ.get(
        "CHUNKHOUND_DB_PATH"
    )
    if db_path_env:
        return Path(db_path_env)

    # Find project root and use default database name
    project_root = find_project_root()
    return project_root / ".chunkhound" / "db"
