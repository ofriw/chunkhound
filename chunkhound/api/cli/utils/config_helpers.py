"""
Configuration helper utilities for CLI commands.

<AI_AGENT_CRITICAL_SYSTEM>
This module provides utilities to bridge CLI arguments with the unified
configuration system.

🚨 PROTECTED CONFIG PATTERNS - EXPLICIT USER APPROVAL REQUIRED 🚨

THESE PATTERNS ARE FUNDAMENTAL TO SYSTEM INTEGRITY:
1. CLI commands MUST use args_to_config() for local config detection
2. ALL config MUST go through validate_config_for_command() before use
3. Registry setup MUST use unified_config._config property

CHANGING THESE PATTERNS WITHOUT EXPLICIT USER APPROVAL WILL:
- Break local .chunkhound.json detection
- Bypass critical validation steps
- Cause silent failures in production
- Create security vulnerabilities

IF YOU NEED TO MODIFY THESE PATTERNS:
1. Ask user explicitly: "Should I modify the protected config patterns?"
2. Explain the specific change and risks
3. Wait for explicit approval before proceeding
4. Update all related code paths consistently
</AI_AGENT_CRITICAL_SYSTEM>
"""

import argparse
from pathlib import Path

from chunkhound.core.config.config import Config


def args_to_config(
    args: argparse.Namespace, project_dir: Path | None = None
) -> Config:
    """
    Convert CLI arguments to unified configuration.

    <AI_AGENT_PROTECTED_FUNCTION>
    🛡️ CRITICAL SYSTEM FUNCTION - EXPLICIT USER APPROVAL REQUIRED FOR CHANGES
    
    PURPOSE: This function is the SINGLE SOURCE OF TRUTH for CLI configuration
    REASONING: CLI commands need local .chunkhound.json detection + argument merging
    SECURITY: Bypassing this function breaks local config detection
    
    PROTECTED BEHAVIORS:
    1. Must detect local .chunkhound.json files in project directories
    2. Must merge CLI args with local config (CLI args take precedence)
    3. Must return Config instance directly
    
    DO NOT MODIFY WITHOUT USER APPROVAL
    </AI_AGENT_PROTECTED_FUNCTION>

    Args:
        args: Parsed CLI arguments
        project_dir: Project directory for config file loading (ignored - now auto-detected from args)

    Returns:
        Config instance
    """
    # The new unified Config class handles all the complexity internally
    # It automatically detects project directories, config files, and applies precedence
    return Config(args=args)


def create_legacy_registry_config(
    config: Config, no_embeddings: bool = False
) -> dict:
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

    <AI_AGENT_PROTECTED_FUNCTION>
    🛡️ CRITICAL SECURITY FUNCTION - EXPLICIT USER APPROVAL REQUIRED FOR CHANGES
    
    PURPOSE: This function is the MANDATORY validation gateway for all config
    REASONING: Prevents runtime errors, security issues, and silent failures
    SECURITY: Bypassing this function creates production vulnerabilities
    
    PROTECTED BEHAVIORS:
    1. Must validate ALL config before any system component uses it
    2. Must return list of specific error messages (not just True/False)
    3. Must check provider-specific requirements (API keys, URLs, etc.)
    4. Must be called by BOTH CLI and MCP code paths
    
    NEVER SKIP THIS VALIDATION - IT PREVENTS:
    - Missing API key runtime errors
    - Invalid provider configurations
    - Database connection failures
    - Silent system failures
    
    DO NOT MODIFY WITHOUT USER APPROVAL
    </AI_AGENT_PROTECTED_FUNCTION>

    Args:
        config: Configuration to validate
        command: Command name ('index', 'mcp')

    Returns:
        List of validation errors (empty if valid)
    """
    # <VALIDATION_STEP_1>
    # WHY: All config objects must pass basic completeness checks
    # HOW: Use config.get_missing_config() to find missing required fields
    # PROTECTED: This catches fundamental config errors before they cause crashes
    errors = []

    # Check for missing configuration
    missing_config = config.get_missing_config()
    if missing_config:
        errors.extend(
            f"Missing required configuration: {item}" for item in missing_config
        )

    # <VALIDATION_STEP_2>
    # WHY: Both CLI and MCP need embedding provider validation
    # HOW: Check provider-specific requirements (API keys, URLs, models)
    # PROTECTED: This prevents runtime errors when embedding providers are used
    if command in ["index", "mcp"]:
        # Get embedding config
        embedding_config = config.embedding

        # Validate embedding provider requirements if config exists
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

    # <VALIDATION_STEP_3>
    # WHY: Return complete list of errors for user-friendly error messages
    # HOW: Return list of strings (empty list = no errors)
    # PROTECTED: Error format must remain consistent across all callers
    return errors
