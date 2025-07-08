"""Validation utilities for ChunkHound CLI arguments."""

import sys
from pathlib import Path

from loguru import logger


def validate_path(
    path: Path, must_exist: bool = True, must_be_dir: bool = True
) -> bool:
    """Validate a file system path.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist
        must_be_dir: Whether the path must be a directory

    Returns:
        True if valid, False otherwise
    """
    if must_exist and not path.exists():
        logger.error(f"Path does not exist: {path}")
        return False

    if must_exist and must_be_dir and not path.is_dir():
        logger.error(f"Path is not a directory: {path}")
        return False

    return True


def validate_provider_args(
    provider: str | None, api_key: str | None, base_url: str | None, model: str | None
) -> bool:
    """Validate embedding provider arguments.

    Args:
        provider: Provider name (required)
        api_key: Optional API key (should come from unified config)
        base_url: Optional base URL
        model: Optional model name

    Returns:
        True if valid, False otherwise
    """
    if not provider:
        logger.error(
            "Embedding provider must be specified. Choose from: openai, openai-compatible, tei, bge-in-icl. "
            "Set via --provider, CHUNKHOUND_EMBEDDING__PROVIDER, or in config file."
        )
        return False
    if provider == "openai":
        if not api_key:
            logger.error(
                "OpenAI API key required. Set CHUNKHOUND_EMBEDDING_API_KEY or use --api-key"
            )
            return False

    elif provider == "openai-compatible":
        if not base_url:
            logger.error("Base URL required for OpenAI-compatible provider")
            return False
        if not model:
            logger.error("Model name required for OpenAI-compatible provider")
            return False

    elif provider == "tei":
        if not base_url:
            logger.error("Base URL required for TEI provider")
            return False

    elif provider == "bge-in-icl":
        if not base_url:
            logger.error("Base URL required for BGE-IN-ICL provider")
            return False

    else:
        logger.error(f"Unknown provider: {provider}")
        return False

    return True


def validate_config_args(
    server_type: str, base_url: str | None, model: str | None, api_key: str | None
) -> bool:
    """Validate configuration server arguments.

    Args:
        server_type: Type of server being configured
        base_url: Server base URL
        model: Model name
        api_key: API key

    Returns:
        True if valid, False otherwise
    """
    if server_type in ["openai", "openai-compatible"] and not model:
        logger.error(f"Model is required for {server_type} servers")
        return False

    if not base_url:
        logger.error("Base URL is required")
        return False

    # Validate URL format
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        logger.error("Base URL must start with http:// or https://")
        return False

    return True


def validate_file_patterns(
    include_patterns: list[str], exclude_patterns: list[str]
) -> bool:
    """Validate file inclusion and exclusion patterns.

    Args:
        include_patterns: List of inclusion patterns
        exclude_patterns: List of exclusion patterns

    Returns:
        True if valid, False otherwise
    """
    # Basic validation - patterns should not be empty strings
    if any(not pattern.strip() for pattern in include_patterns):
        logger.error("Include patterns cannot be empty")
        return False

    if any(not pattern.strip() for pattern in exclude_patterns):
        logger.error("Exclude patterns cannot be empty")
        return False

    return True


def validate_numeric_args(
    debounce_ms: int | None = None, batch_size: int | None = None
) -> bool:
    """Validate numeric arguments.

    Args:
        debounce_ms: Optional debounce time in milliseconds
        batch_size: Optional batch size

    Returns:
        True if valid, False otherwise
    """
    if debounce_ms is not None:
        if debounce_ms < 0:
            logger.error("Debounce time cannot be negative")
            return False
        if debounce_ms > 10000:  # 10 seconds max
            logger.error("Debounce time cannot exceed 10 seconds")
            return False

    if batch_size is not None:
        if batch_size < 1:
            logger.error("Batch size must be at least 1")
            return False
        if batch_size > 1000:
            logger.error("Batch size cannot exceed 1000")
            return False

    return True


def validate_server_name(name: str, existing_servers: list[str]) -> bool:
    """Validate server name for uniqueness and format.

    Args:
        name: Server name to validate
        existing_servers: List of existing server names

    Returns:
        True if valid, False otherwise
    """
    if not name or not name.strip():
        logger.error("Server name cannot be empty")
        return False

    # Check for valid characters
    if not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
        logger.error(
            "Server name can only contain letters, numbers, hyphens, underscores, and dots"
        )
        return False

    if name in existing_servers:
        logger.error(f"Server '{name}' already exists")
        return False

    return True


def ensure_database_directory(db_path: Path) -> bool:
    """Ensure the database directory exists.

    Args:
        db_path: Path to database file

    Returns:
        True if directory exists or was created successfully
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create database directory: {e}")
        return False


def validate_config_file_path(config_path: Path | None) -> bool:
    """Validate configuration file path.

    Args:
        config_path: Optional path to configuration file

    Returns:
        True if valid or None, False if invalid
    """
    if config_path is None:
        return True

    # Check if parent directory exists or can be created
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Cannot access configuration directory: {e}")
        return False


def exit_on_validation_error(message: str) -> None:
    """Print error message and exit with error code.

    Args:
        message: Error message to display
    """
    logger.error(message)
    sys.exit(1)


def validate_embedding_dimension(dimension: int | None) -> bool:
    """Validate embedding dimension parameter.

    Args:
        dimension: Embedding dimension to validate

    Returns:
        True if valid, False otherwise
    """
    if dimension is None:
        return True

    if dimension < 1:
        logger.error("Embedding dimension must be positive")
        return False

    if dimension > 10000:  # Reasonable upper limit
        logger.error("Embedding dimension is too large (max 10,000)")
        return False

    return True


def validate_timeout_args(timeout: float | None) -> bool:
    """Validate timeout arguments.

    Args:
        timeout: Timeout value in seconds

    Returns:
        True if valid, False otherwise
    """
    if timeout is None:
        return True

    if timeout <= 0:
        logger.error("Timeout must be positive")
        return False

    if timeout > 300:  # 5 minutes max
        logger.error("Timeout cannot exceed 300 seconds")
        return False

    return True
