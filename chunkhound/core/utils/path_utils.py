"""Path utility functions for ChunkHound."""

from pathlib import Path


def normalize_path_for_lookup(
    input_path: str | Path, base_dir: Path | None = None
) -> str:
    """Normalize path for database lookup operations.

    Converts absolute paths to relative paths using base directory,
    resolves symlinks for consistency, and ensures forward slash normalization
    for cross-platform compatibility.

    Args:
        input_path: Path to normalize (can be absolute or relative)
        base_dir: Base directory for relative path calculation (required for absolute paths)

    Returns:
        Normalized relative path with forward slashes

    Raises:
        ValueError: If absolute path is provided without base_dir, or if path is not under base_dir
    """
    path_obj = Path(input_path)

    # If path is already relative, just normalize slashes
    if not path_obj.is_absolute():
        return path_obj.as_posix()

    # For absolute paths, base_dir is REQUIRED
    if base_dir is None:
        raise ValueError(
            f"Cannot normalize absolute path without base_dir: {input_path}. "
            f"This indicates a bug - base directory should always be available from config."
        )

    try:
        # Resolve both paths to canonical form to handle symlinks (e.g., /var -> /private/var on macOS)
        resolved_path = path_obj.resolve()
        resolved_base_dir = base_dir.resolve()

        # Make path relative to base directory
        relative_path = resolved_path.relative_to(resolved_base_dir)
        return relative_path.as_posix()
    except ValueError:
        # Path is not under base_dir - this should not happen in normal operation
        raise ValueError(
            f"Path {input_path} is not under base directory {base_dir}. "
            f"This indicates a configuration or indexing issue."
        )
