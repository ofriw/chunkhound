"""
Configuration helper utilities for CLI commands.

This module provides utilities to bridge CLI arguments with the unified
configuration system.
"""

import argparse
import os
from pathlib import Path

from loguru import logger

from chunkhound.core.config.unified_config import ChunkHoundConfig


def args_to_config(args: argparse.Namespace, project_dir: Path | None = None) -> ChunkHoundConfig:
    """
    Convert CLI arguments to unified configuration.
    
    Args:
        args: Parsed CLI arguments
        project_dir: Project directory for config file loading
        
    Returns:
        ChunkHoundConfig instance
    """
    config_overrides = {}
    
    # Database configuration - only override if explicitly provided
    if hasattr(args, 'db') and args.db is not None:
        config_overrides['database'] = {'path': str(args.db)}
    
    # Embedding configuration
    embedding_config = {}
    if hasattr(args, 'provider') and args.provider:
        embedding_config['provider'] = args.provider
    if hasattr(args, 'model') and args.model:
        embedding_config['model'] = args.model
    if hasattr(args, 'api_key') and args.api_key:
        embedding_config['api_key'] = args.api_key
    if hasattr(args, 'base_url') and args.base_url:
        embedding_config['base_url'] = args.base_url
    if hasattr(args, 'embedding_batch_size') and args.embedding_batch_size:
        embedding_config['batch_size'] = args.embedding_batch_size
    if hasattr(args, 'max_concurrent') and args.max_concurrent:
        embedding_config['max_concurrent_batches'] = args.max_concurrent
    
    if embedding_config:
        config_overrides['embedding'] = embedding_config
    
    # MCP configuration
    mcp_config = {}
    if hasattr(args, 'http') and args.http:
        mcp_config['transport'] = 'http'
    elif hasattr(args, 'stdio') and args.stdio:
        mcp_config['transport'] = 'stdio'
    if hasattr(args, 'port') and args.port:
        mcp_config['port'] = args.port
    if hasattr(args, 'host') and args.host:
        mcp_config['host'] = args.host
    if hasattr(args, 'cors') and args.cors:
        mcp_config['cors'] = args.cors
    
    if mcp_config:
        config_overrides['mcp'] = mcp_config
    
    # Indexing configuration
    indexing_config = {}
    if hasattr(args, 'include') and args.include:
        indexing_config['include_patterns'] = args.include
    if hasattr(args, 'exclude') and args.exclude:
        indexing_config['exclude_patterns'] = args.exclude
    if hasattr(args, 'watch') and args.watch:
        indexing_config['watch'] = args.watch
    if hasattr(args, 'debounce_ms') and args.debounce_ms:
        indexing_config['debounce_ms'] = args.debounce_ms
    if hasattr(args, 'db_batch_size') and args.db_batch_size:
        indexing_config['db_batch_size'] = args.db_batch_size
    if hasattr(args, 'force_reindex') and args.force_reindex:
        indexing_config['force_reindex'] = args.force_reindex
    if hasattr(args, 'cleanup') and args.cleanup:
        indexing_config['cleanup'] = args.cleanup
    
    if indexing_config:
        config_overrides['indexing'] = indexing_config
    
    # Global configuration
    if hasattr(args, 'verbose') and args.verbose:
        config_overrides['debug'] = args.verbose
    
    # Load configuration with hierarchical resolution
    return ChunkHoundConfig.load_hierarchical(
        project_dir=project_dir,
        **config_overrides
    )


def create_legacy_registry_config(config: ChunkHoundConfig, no_embeddings: bool = False) -> dict:
    """
    Create legacy registry configuration format from unified config.
    
    Args:
        config: Unified configuration
        no_embeddings: Whether to skip embedding configuration
        
    Returns:
        Legacy registry configuration dictionary
    """
    registry_config = {
        'database': {
            'path': config.database.path,
            'type': config.database.provider,
            'batch_size': config.indexing.db_batch_size,
            'lancedb_index_type': config.database.lancedb_index_type,
        },
        'embedding': {
            'batch_size': config.embedding.batch_size,
            'max_concurrent_batches': config.embedding.max_concurrent_batches,
        }
    }
    
    if not no_embeddings:
        embedding_dict = {
            'provider': config.embedding.provider,
            'model': config.get_embedding_model(),
        }
        
        if config.embedding.api_key:
            embedding_dict['api_key'] = config.embedding.api_key.get_secret_value()
            
        if config.embedding.base_url:
            embedding_dict['base_url'] = config.embedding.base_url
            
        registry_config['embedding'].update(embedding_dict)
    
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
    # Handle legacy OPENAI_API_KEY
    if not config.embedding.api_key and os.getenv('OPENAI_API_KEY'):
        config.embedding.api_key = os.getenv('OPENAI_API_KEY')
    
    # Handle legacy OPENAI_BASE_URL  
    if not config.embedding.base_url and os.getenv('OPENAI_BASE_URL'):
        config.embedding.base_url = os.getenv('OPENAI_BASE_URL')
    
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
        errors.extend(f"Missing required configuration: {item}" for item in missing_config)
    
    # Command-specific validation
    if command == 'index':
        # Validate embedding provider requirements for indexing
        if config.embedding.provider in ['tei', 'bge-in-icl'] and not config.embedding.base_url:
            errors.append(f"--base-url required for {config.embedding.provider} provider")
        
        if config.embedding.provider == 'openai-compatible':
            if not config.embedding.model:
                errors.append(f"--model required for {config.embedding.provider} provider")
            if not config.embedding.base_url:
                errors.append(f"--base-url required for {config.embedding.provider} provider")
    
    elif command == 'mcp':
        # MCP-specific validation
        if config.mcp.transport == 'http':
            if not (1 <= config.mcp.port <= 65535):
                errors.append(f"Invalid port {config.mcp.port}, must be between 1 and 65535")
    
    return errors