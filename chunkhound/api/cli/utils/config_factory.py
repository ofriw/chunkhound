"""Configuration factory for consolidated config loading and validation.

This module provides centralized functions to create and validate configuration
instances, eliminating duplication across CLI commands and MCP servers.
"""

import argparse

from chunkhound.core.config.config import Config


def create_validated_config(
    args: argparse.Namespace, command: str
) -> tuple[Config, list[str]]:
    """Create and validate config for a specific command.

    This centralizes the config loading pattern that was duplicated across
    main.py, run.py, and mcp_server.py.

    Args:
        args: Parsed command-line arguments
        command: Command name for validation ('index', 'mcp')

    Returns:
        tuple: (config_instance, validation_errors)
    """
    config = Config(args=args)
    validation_errors = config.validate_for_command(command)
    return config, validation_errors


def create_config(args: argparse.Namespace) -> Config:
    """Create config without validation.

    Use this when validation isn't needed or will be done separately.

    Args:
        args: Parsed command-line arguments

    Returns:
        Config instance
    """
    return Config(args=args)


def create_default_config() -> Config:
    """Create config with defaults (no CLI args).

    Use this for fallback scenarios where args aren't available.

    Returns:
        Config instance with defaults
    """
    return Config()
