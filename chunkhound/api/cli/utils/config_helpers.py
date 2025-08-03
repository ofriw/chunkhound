"""Configuration helper utilities for CLI commands."""

import argparse
from pathlib import Path

from chunkhound.core.config.config import Config


def args_to_config(args: argparse.Namespace, project_dir: Path | None = None) -> Config:
    """
    Convert CLI arguments to unified configuration.

    Args:
        args: Parsed CLI arguments
        project_dir: Project directory for config file loading (ignored - now auto-detected from args)

    Returns:
        Config instance
    """
    # The new unified Config class handles all the complexity internally
    # It automatically detects project directories, config files, and applies precedence
    return Config(args=args)


def create_legacy_registry_config(config: Config, no_embeddings: bool = False) -> dict:
    """
    Create legacy registry configuration format from unified config.

    Args:
        config: Configuration
        no_embeddings: Whether to skip embedding configuration

    Returns:
        Legacy registry configuration dictionary
    """
    registry_config = {
        "database": {
            "path": config.database.path,
            "provider": config.database.provider,
            "batch_size": config.indexing.db_batch_size,
            "lancedb_index_type": config.database.lancedb_index_type,
        },
        "embedding": {
            "batch_size": config.embedding.batch_size,
            "max_concurrent_batches": config.embedding.max_concurrent_batches,
        },
    }

    if not no_embeddings:
        embedding_dict = {
            "provider": config.embedding.provider,
            "model": config.get_embedding_model(),
        }

        if config.embedding.api_key:
            embedding_dict["api_key"] = (
                config.embedding.api_key.get_secret_value()
                if hasattr(config.embedding.api_key, "get_secret_value")
                else config.embedding.api_key
            )

        if config.embedding.base_url:
            embedding_dict["base_url"] = config.embedding.base_url

        registry_config["embedding"].update(embedding_dict)

    return registry_config


def validate_config_for_command(config: Config, command: str) -> list[str]:
    """
    Validate configuration for a specific command.

    Args:
        config: Configuration to validate
        command: Command name ('index', 'mcp')

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check for missing configuration
    missing_config = config.get_missing_config()
    if missing_config:
        errors.extend(
            f"Missing required configuration: {item}" for item in missing_config
        )

    # Validate embedding provider requirements for index and MCP commands
    if command in ["index", "mcp"]:
        embedding_config = config.embedding

        if embedding_config:
            if (
                embedding_config.provider in ["tei", "bge-in-icl"]
                and not embedding_config.base_url
            ):
                errors.append(
                    f"--base-url required for {embedding_config.provider} provider"
                )

            if embedding_config.provider == "openai-compatible":
                if not embedding_config.model:
                    errors.append(
                        f"--model required for {embedding_config.provider} provider"
                    )
                if not embedding_config.base_url:
                    errors.append(
                        f"--base-url required for {embedding_config.provider} provider"
                    )

    return errors
