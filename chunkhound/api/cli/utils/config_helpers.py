"""
Configuration helper utilities for CLI commands.

This module provides utilities to bridge CLI arguments with the unified
configuration system.
"""

import argparse
import os
from pathlib import Path

from chunkhound.core.config.config import Config
from chunkhound.core.config.unified_config import ChunkHoundConfig


def args_to_config(
    args: argparse.Namespace, project_dir: Path | None = None
) -> ChunkHoundConfig:
    """
    Convert CLI arguments to unified configuration.

    Args:
        args: Parsed CLI arguments
        project_dir: Project directory for config file loading

    Returns:
        ChunkHoundConfig instance
    """
    # Get config file path from args
    config_file = getattr(args, "config", None)
    if config_file:
        config_file = Path(config_file)
    
    # Determine target directory (for .chunkhound.json detection)
    target_dir = None
    if hasattr(args, "path"):
        target_dir = Path(args.path)
    elif project_dir:
        target_dir = Path(project_dir)
    
    # Use the new Config class
    config = Config.from_cli_args(args, config_file=config_file, target_dir=target_dir)
    
    # Create ChunkHoundConfig wrapper instance
    chunk_config = ChunkHoundConfig()
    chunk_config._config = config
    
    return chunk_config


def create_legacy_registry_config(
    config: ChunkHoundConfig, no_embeddings: bool = False
) -> dict:
    """
    Create legacy registry configuration format from unified config.

    Args:
        config: Unified configuration
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


def apply_legacy_env_vars(config: ChunkHoundConfig) -> ChunkHoundConfig:
    """
    Apply legacy environment variables to configuration.

    This provides backward compatibility for existing environment variables
    while the system transitions to the unified configuration.

    Args:
        config: Configuration to update

    Returns:
        Updated configuration
    """
    # Legacy environment variables are now handled by the Config class
    # in its _load_env_vars method, so this is now a no-op
    return config


def validate_config_for_command(config: ChunkHoundConfig, command: str) -> list[str]:
    """
    Validate configuration for a specific command.

    Args:
        config: Configuration to validate
        command: Command name ('index', 'mcp')

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Common validation
    missing_config = config.get_missing_config()
    if missing_config:
        errors.extend(
            f"Missing required configuration: {item}" for item in missing_config
        )

    # Both index and mcp commands need embedding provider validation
    if command in ["index", "mcp"]:
        # Validate embedding provider requirements
        if (
            config.embedding.provider in ["tei", "bge-in-icl"]
            and not config.embedding.base_url
        ):
            errors.append(
                f"--base-url required for {config.embedding.provider} provider"
            )

        if config.embedding.provider == "openai-compatible":
            if not config.embedding.model:
                errors.append(
                    f"--model required for {config.embedding.provider} provider"
                )
            if not config.embedding.base_url:
                errors.append(
                    f"--base-url required for {config.embedding.provider} provider"
                )

    return errors
