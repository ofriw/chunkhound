"""Config command module - handles embedding server configuration operations."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from loguru import logger

from chunkhound.config import get_config_manager, reset_config_manager, ServerConfig
from ..utils.output import OutputFormatter, format_health_status, format_server_info, print_section
from ..utils.validation import validate_config_args, validate_server_name


async def config_command(args: argparse.Namespace) -> None:
    """Execute the config command with appropriate subcommand.
    
    Args:
        args: Parsed command-line arguments
    """
    # Route to appropriate subcommand
    subcommand_handlers = {
        "list": config_list_command,
        "add": config_add_command,
        "remove": config_remove_command,
        "test": config_test_command,
        "health": config_health_command,
        "enable": config_enable_command,
        "disable": config_disable_command,
        "set-default": config_set_default_command,
        "validate": config_validate_command,
        "benchmark": config_benchmark_command,
        "switch": config_switch_command,
        "discover": config_discover_command,
        "export": config_export_command,
        "import": config_import_command,
        "template": config_template_command,
        "batch-test": config_batch_test_command,
    }
    
    handler = subcommand_handlers.get(args.config_command)
    if handler:
        await handler(args)
    else:
        logger.error(f"Unknown config command: {args.config_command}")
        sys.exit(1)


async def config_list_command(args: argparse.Namespace) -> None:
    """Handle config list command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        servers = config_manager.registry.list_servers()
        
        if not servers:
            formatter.info("No servers configured.")
            return
        
        print(f"Configured servers ({len(servers)}):")
        print()
        
        for name in servers:
            server = config_manager.registry.get_server(name)
            default_marker = " (default)" if config_manager.registry._default_server == name else ""
            enabled_marker = "" if server.enabled else " (disabled)"
            
            print(f"  {name}{default_marker}{enabled_marker}")
            print(f"    Type: {server.type}")
            print(f"    URL:  {server.base_url}")
            print(f"    Model: {server.model or 'auto-detected'}")
            
            if getattr(args, 'show_health', False):
                try:
                    health = await config_manager.registry.check_server_health(name)
                    status = format_health_status({
                        'healthy': health.is_healthy,
                        'response_time_ms': health.response_time_ms,
                        'error': health.error_message
                    })
                    print(f"    Health: {status}")
                except Exception as e:
                    print(f"    Health: ❓ unknown ({e})")
            
            print()
            
    except Exception as e:
        formatter.error(f"Failed to list servers: {e}")
        sys.exit(1)


async def config_add_command(args: argparse.Namespace) -> None:
    """Handle config add command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Validate arguments
        if not validate_config_args(args.type, args.base_url, args.model, getattr(args, 'api_key', None)):
            sys.exit(1)
        
        # Check if server name already exists
        existing_servers = config_manager.registry.list_servers()
        if not validate_server_name(args.name, existing_servers):
            sys.exit(1)
        
        # Prepare metadata for BGE-IN-ICL specific options
        metadata = {}
        if args.type == 'bge-in-icl':
            if hasattr(args, 'batch_size') and args.batch_size:
                metadata['batch_size'] = args.batch_size
        
        # Create server configuration
        server_config = ServerConfig(
            name=args.name,
            type=args.type,
            base_url=args.base_url,
            model=args.model or ('bge-in-icl' if args.type == 'bge-in-icl' else None),
            api_key=getattr(args, 'api_key', None),
            enabled=True,
            metadata=metadata
        )
        
        # Add server to configuration
        config_manager.add_server(server_config)
        
        # Set as default if requested
        if getattr(args, 'default', False):
            config_manager.registry.set_default_server(args.name)
        
        # Save configuration
        config_manager.save_config()
        
        formatter.success(f"Added server '{args.name}' successfully")
        
        if getattr(args, 'default', False):
            formatter.info(f"Set '{args.name}' as default server")
            
    except Exception as e:
        formatter.error(f"Failed to add server: {e}")
        sys.exit(1)


async def config_remove_command(args: argparse.Namespace) -> None:
    """Handle config remove command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            formatter.error(f"Server '{args.name}' not found")
            sys.exit(1)
        
        config_manager.remove_server(args.name)
        config_manager.save_config()
        
        formatter.success(f"Removed server '{args.name}' successfully")
        
    except Exception as e:
        formatter.error(f"Failed to remove server: {e}")
        sys.exit(1)


async def config_test_command(args: argparse.Namespace) -> None:
    """Handle config test command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        server_name = getattr(args, 'name', None)
        if not server_name:
            server_name = config_manager.registry._default_server
            if not server_name:
                formatter.error("No default server configured and no server specified")
                sys.exit(1)
        
        if server_name not in config_manager.registry.list_servers():
            formatter.error(f"Server '{server_name}' not found")
            sys.exit(1)
        
        formatter.info(f"Testing server '{server_name}'...")
        
        # Perform health check
        health = await config_manager.registry.check_server_health(server_name)
        
        if health.is_healthy:
            formatter.success(f"Server '{server_name}' is healthy ({health.response_time_ms:.1f}ms)")
        else:
            formatter.error(f"Server '{server_name}' is unhealthy: {health.error_message}")
            sys.exit(1)
            
    except Exception as e:
        formatter.error(f"Failed to test server: {e}")
        sys.exit(1)


async def config_health_command(args: argparse.Namespace) -> None:
    """Handle config health command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if getattr(args, 'monitor', False):
            formatter.info("Starting health monitoring... (Press Ctrl+C to stop)")
            await config_manager.start_monitoring()
            try:
                while True:
                    await asyncio.sleep(10)
            except KeyboardInterrupt:
                formatter.info("Health monitoring stopped")
                await config_manager.stop_monitoring()
        else:
            # Single health check for all servers
            servers = config_manager.registry.list_servers()
            if not servers:
                formatter.info("No servers configured")
                return
            
            formatter.info("Checking server health...")
            
            for name in servers:
                try:
                    health = await config_manager.registry.check_server_health(name)
                    status = format_health_status({
                        'healthy': health.is_healthy,
                        'response_time_ms': health.response_time_ms,
                        'error': health.error_message
                    })
                    print(f"  {name}: {status}")
                except Exception as e:
                    print(f"  {name}: ❓ Error checking health: {e}")
                    
    except Exception as e:
        formatter.error(f"Failed to check health: {e}")
        sys.exit(1)


async def config_enable_command(args: argparse.Namespace) -> None:
    """Handle config enable command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            formatter.error(f"Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if server.enabled:
            formatter.info(f"Server '{args.name}' is already enabled")
            return
        
        config_manager.registry.enable_server(args.name)
        config_manager.save_config()
        
        formatter.success(f"Enabled server '{args.name}'")
        
    except Exception as e:
        formatter.error(f"Failed to enable server: {e}")
        sys.exit(1)


async def config_disable_command(args: argparse.Namespace) -> None:
    """Handle config disable command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            formatter.error(f"Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if not server.enabled:
            formatter.info(f"Server '{args.name}' is already disabled")
            return
        
        # Check if this is the default server
        if config_manager.registry._default_server == args.name:
            formatter.warning(f"Disabling default server '{args.name}' - you may want to set a new default")
        
        config_manager.registry.disable_server(args.name)
        config_manager.save_config()
        
        formatter.success(f"Disabled server '{args.name}'")
        
    except Exception as e:
        formatter.error(f"Failed to disable server: {e}")
        sys.exit(1)


async def config_set_default_command(args: argparse.Namespace) -> None:
    """Handle config set-default command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        if args.name not in config_manager.registry.list_servers():
            formatter.error(f"Server '{args.name}' not found")
            sys.exit(1)
        
        server = config_manager.registry.get_server(args.name)
        if not server.enabled:
            formatter.error(f"Cannot set disabled server '{args.name}' as default")
            sys.exit(1)
        
        config_manager.registry.set_default_server(args.name)
        config_manager.save_config()
        
        formatter.success(f"Set '{args.name}' as default server")
        
    except Exception as e:
        formatter.error(f"Failed to set default server: {e}")
        sys.exit(1)


async def config_validate_command(args: argparse.Namespace) -> None:
    """Handle config validate command."""
    formatter = OutputFormatter(verbose=getattr(args, 'verbose', False))
    
    try:
        config_manager = get_config_manager(str(args.config) if args.config else None)
        
        # Use enhanced validation
        validation_result = config_manager.validate_config_file(args.config)
        
        formatter.info(f"Validating configuration: {validation_result.get('config_path', 'default')}")
        print()
        
        if validation_result.get('valid', False):
            formatter.success("Configuration is valid")
            
            # Show summary
            servers = validation_result.get('servers', [])
            formatter.info(f"Found {len(servers)} server(s)")
            
            for server_info in servers:
                status = "✅" if server_info.get('valid', False) else "❌"
                print(f"  {status} {server_info.get('name', 'unknown')}")
                
                if not server_info.get('valid', False):
                    errors = server_info.get('errors', [])
                    for error in errors:
                        print(f"    Error: {error}")
        else:
            formatter.error("Configuration has errors:")
            errors = validation_result.get('errors', [])
            for error in errors:
                print(f"  • {error}")
            sys.exit(1)
            
    except Exception as e:
        formatter.error(f"Failed to validate configuration: {e}")
        sys.exit(1)


# Simplified implementations for remaining commands
async def config_benchmark_command(args: argparse.Namespace) -> None:
    """Handle config benchmark command."""
    formatter = OutputFormatter()
    formatter.info("Benchmark command not yet implemented in modular CLI")


async def config_switch_command(args: argparse.Namespace) -> None:
    """Handle config switch command."""
    formatter = OutputFormatter()
    formatter.info("Switch command not yet implemented in modular CLI")


async def config_discover_command(args: argparse.Namespace) -> None:
    """Handle config discover command."""
    formatter = OutputFormatter()
    formatter.info("Discover command not yet implemented in modular CLI")


async def config_export_command(args: argparse.Namespace) -> None:
    """Handle config export command."""
    formatter = OutputFormatter()
    formatter.info("Export command not yet implemented in modular CLI")


async def config_import_command(args: argparse.Namespace) -> None:
    """Handle config import command."""
    formatter = OutputFormatter()
    formatter.info("Import command not yet implemented in modular CLI")


async def config_template_command(args: argparse.Namespace) -> None:
    """Handle config template command."""
    formatter = OutputFormatter()
    formatter.info("Template command not yet implemented in modular CLI")


async def config_batch_test_command(args: argparse.Namespace) -> None:
    """Handle config batch-test command."""
    formatter = OutputFormatter()
    formatter.info("Batch-test command not yet implemented in modular CLI")


def add_config_subparser(subparsers) -> argparse.ArgumentParser:
    """Add config command subparser to the main parser.
    
    Args:
        subparsers: Subparsers object from the main argument parser
        
    Returns:
        The configured config subparser
    """
    config_parser = subparsers.add_parser(
        "config",
        help="Manage embedding server configurations",
        description="Configure and manage embedding server connections"
    )
    
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Configuration commands")
    
    # Config list command
    list_parser = config_subparsers.add_parser("list", help="List all configured servers")
    list_parser.add_argument("--config", type=Path, help="Configuration file path")
    list_parser.add_argument("--show-health", action="store_true", help="Show health status for each server")
    
    # Config add command
    add_parser = config_subparsers.add_parser("add", help="Add a new embedding server")
    add_parser.add_argument("name", help="Server name")
    add_parser.add_argument("--type", required=True, choices=["openai", "openai-compatible", "tei", "bge-in-icl"], help="Server type")
    add_parser.add_argument("--base-url", required=True, help="Server base URL")
    add_parser.add_argument("--model", help="Model name (auto-detected for TEI, defaults to 'bge-in-icl' for BGE-IN-ICL)")
    add_parser.add_argument("--api-key", help="API key for authentication")
    add_parser.add_argument("--default", action="store_true", help="Set as default server")
    add_parser.add_argument("--config", type=Path, help="Configuration file path")
    add_parser.add_argument("--batch-size", type=int, help="Batch size for embeddings")
    
    # Config remove command
    remove_parser = config_subparsers.add_parser("remove", help="Remove a server")
    remove_parser.add_argument("name", help="Server name to remove")
    remove_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config test command
    test_parser = config_subparsers.add_parser("test", help="Test server connectivity")
    test_parser.add_argument("name", nargs="?", help="Server name to test (uses default if not specified)")
    test_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config health command
    health_parser = config_subparsers.add_parser("health", help="Check server health")
    health_parser.add_argument("--monitor", action="store_true", help="Start continuous monitoring")
    health_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config enable command
    enable_parser = config_subparsers.add_parser("enable", help="Enable a server")
    enable_parser.add_argument("name", help="Server name to enable")
    enable_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config disable command
    disable_parser = config_subparsers.add_parser("disable", help="Disable a server")
    disable_parser.add_argument("name", help="Server name to disable")
    disable_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config set-default command
    default_parser = config_subparsers.add_parser("set-default", help="Set default server")
    default_parser.add_argument("name", help="Server name to set as default")
    default_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Config validate command
    validate_parser = config_subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument("--config", type=Path, help="Configuration file path")
    
    # Add simplified parsers for remaining commands
    config_subparsers.add_parser("benchmark", help="Benchmark server performance")
    config_subparsers.add_parser("switch", help="Switch between server configurations")
    config_subparsers.add_parser("discover", help="Discover configuration files")
    config_subparsers.add_parser("export", help="Export configuration")
    config_subparsers.add_parser("import", help="Import configuration")
    config_subparsers.add_parser("template", help="Generate configuration templates")
    config_subparsers.add_parser("batch-test", help="Test all enabled servers")
    
    return config_parser


__all__ = ["config_command", "add_config_subparser"]