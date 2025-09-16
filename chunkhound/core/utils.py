"""Core utility functions for ChunkHound."""

from pathlib import Path


def normalize_path_for_lookup(input_path: str | Path, base_dir: Path | None = None) -> str:
    """Normalize path for database lookup operations.

    Converts absolute paths to relative paths using base directory,
    and ensures forward slash normalization for cross-platform compatibility.

    Args:
        input_path: Path to normalize (can be absolute or relative)
        base_dir: Base directory for relative path calculation (defaults to file's parent)

    Returns:
        Normalized relative path with forward slashes
    """
    path_obj = Path(input_path)

    # If path is absolute, convert to relative
    if path_obj.is_absolute():
        if base_dir is None:
            # Use file's parent directory as base if no base_dir provided
            base_dir = path_obj.parent

        try:
            # Make path relative to base directory
            relative_path = path_obj.relative_to(base_dir)
        except ValueError:
            # Path is not relative to base directory, use parent directory
            relative_path = path_obj.relative_to(path_obj.parent)
        return relative_path.as_posix()
    else:
        # Path is already relative, just normalize slashes
        return path_obj.as_posix()