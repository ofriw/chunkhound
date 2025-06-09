"""Config command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path

from .main_parser import add_common_arguments


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
    
    add_common_arguments(config_parser)
    
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", 
        help="Configuration commands",
        required=True
    )
    
    # Config list command
    list_parser = config_subparsers.add_parser(
        "list", 
        help="List all configured servers"
    )
    list_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    list_parser.add_argument(
        "--show-health", 
        action="store_true", 
        help="Show health status for each server"
    )
    
    # Config add command
    add_parser = config_subparsers.add_parser(
        "add", 
        help="Add a new embedding server"
    )
    add_parser.add_argument(
        "name", 
        help="Server name"
    )
    add_parser.add_argument(
        "--type", 
        required=True,
        choices=["openai", "openai-compatible", "tei", "bge-in-icl"],
        help="Server type"
    )
    add_parser.add_argument(
        "--base-url", 
        required=True,
        help="Server base URL"
    )
    add_parser.add_argument(
        "--model", 
        help="Model name (auto-detected for TEI, defaults to 'bge-in-icl' for BGE-IN-ICL)"
    )
    add_parser.add_argument(
        "--api-key", 
        help="API key for authentication"
    )
    add_parser.add_argument(
        "--default", 
        action="store_true",
        help="Set as default server"
    )
    add_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    add_parser.add_argument(
        "--batch-size", 
        type=int,
        help="Batch size for embeddings"
    )
    add_parser.add_argument(
        "--timeout", 
        type=float,
        help="Request timeout in seconds"
    )
    add_parser.add_argument(
        "--max-retries", 
        type=int,
        help="Maximum number of retries"
    )
    
    # Config remove command
    remove_parser = config_subparsers.add_parser(
        "remove", 
        help="Remove a server"
    )
    remove_parser.add_argument(
        "name", 
        help="Server name to remove"
    )
    remove_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    remove_parser.add_argument(
        "--force", 
        action="store_true",
        help="Force removal without confirmation"
    )
    
    # Config test command
    test_parser = config_subparsers.add_parser(
        "test", 
        help="Test server connectivity"
    )
    test_parser.add_argument(
        "name", 
        nargs="?", 
        help="Server name to test (uses default if not specified)"
    )
    test_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    test_parser.add_argument(
        "--timeout", 
        type=float,
        default=30.0,
        help="Test timeout in seconds (default: 30)"
    )
    
    # Config health command
    health_parser = config_subparsers.add_parser(
        "health", 
        help="Check server health"
    )
    health_parser.add_argument(
        "--monitor", 
        action="store_true",
        help="Start continuous monitoring"
    )
    health_parser.add_argument(
        "--interval", 
        type=int,
        default=10,
        help="Monitoring interval in seconds (default: 10)"
    )
    health_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    
    # Config enable command
    enable_parser = config_subparsers.add_parser(
        "enable", 
        help="Enable a server"
    )
    enable_parser.add_argument(
        "name", 
        help="Server name to enable"
    )
    enable_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    
    # Config disable command
    disable_parser = config_subparsers.add_parser(
        "disable", 
        help="Disable a server"
    )
    disable_parser.add_argument(
        "name", 
        help="Server name to disable"
    )
    disable_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    
    # Config set-default command
    default_parser = config_subparsers.add_parser(
        "set-default", 
        help="Set default server"
    )
    default_parser.add_argument(
        "name", 
        help="Server name to set as default"
    )
    default_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    
    # Config validate command
    validate_parser = config_subparsers.add_parser(
        "validate", 
        help="Validate configuration"
    )
    validate_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    validate_parser.add_argument(
        "--strict", 
        action="store_true",
        help="Enable strict validation"
    )
    
    # Config benchmark command
    benchmark_parser = config_subparsers.add_parser(
        "benchmark", 
        help="Benchmark server performance"
    )
    benchmark_parser.add_argument(
        "name", 
        nargs="?", 
        help="Server name to benchmark (tests all enabled if not specified)"
    )
    benchmark_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    benchmark_parser.add_argument(
        "--iterations", 
        type=int,
        default=10,
        help="Number of benchmark iterations (default: 10)"
    )
    benchmark_parser.add_argument(
        "--concurrent", 
        type=int,
        default=1,
        help="Number of concurrent requests (default: 1)"
    )
    
    # Config switch command
    switch_parser = config_subparsers.add_parser(
        "switch", 
        help="Switch between server configurations"
    )
    switch_parser.add_argument(
        "name", 
        help="Server name to switch to"
    )
    switch_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    
    # Config discover command
    discover_parser = config_subparsers.add_parser(
        "discover", 
        help="Discover configuration files"
    )
    discover_parser.add_argument(
        "path", 
        nargs="?", 
        type=Path,
        help="Directory to search (default: current directory)"
    )
    discover_parser.add_argument(
        "--show-all", 
        action="store_true",
        help="Show invalid configurations too"
    )
    discover_parser.add_argument(
        "--recursive", 
        action="store_true",
        default=True,
        help="Search recursively (default: true)"
    )
    
    # Config export command
    export_parser = config_subparsers.add_parser(
        "export", 
        help="Export configuration"
    )
    export_parser.add_argument(
        "output", 
        type=Path,
        help="Output file path"
    )
    export_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    export_parser.add_argument(
        "--format", 
        choices=["yaml", "json"],
        default="yaml",
        help="Export format (default: yaml)"
    )
    export_parser.add_argument(
        "--servers", 
        nargs="*",
        help="Specific servers to export (exports all if not specified)"
    )
    
    # Config import command
    import_parser = config_subparsers.add_parser(
        "import", 
        help="Import configuration"
    )
    import_parser.add_argument(
        "input", 
        type=Path,
        help="Input file path"
    )
    import_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    import_parser.add_argument(
        "--merge", 
        action="store_true",
        help="Merge with existing configuration"
    )
    import_parser.add_argument(
        "--overwrite", 
        action="store_true",
        help="Overwrite existing servers"
    )
    
    # Config template command
    template_parser = config_subparsers.add_parser(
        "template", 
        help="Generate configuration templates"
    )
    template_parser.add_argument(
        "type", 
        choices=["basic", "openai", "tei", "bge-in-icl", "multi"],
        help="Template type to generate"
    )
    template_parser.add_argument(
        "--output", 
        type=Path,
        help="Output file path (prints to stdout if not specified)"
    )
    template_parser.add_argument(
        "--format", 
        choices=["yaml", "json"],
        default="yaml",
        help="Template format (default: yaml)"
    )
    
    # Config batch-test command
    batch_test_parser = config_subparsers.add_parser(
        "batch-test", 
        help="Test all enabled servers"
    )
    batch_test_parser.add_argument(
        "--config", 
        type=Path, 
        help="Configuration file path"
    )
    batch_test_parser.add_argument(
        "--timeout", 
        type=float,
        default=30.0,
        help="Test timeout per server in seconds (default: 30)"
    )
    batch_test_parser.add_argument(
        "--parallel", 
        action="store_true",
        help="Run tests in parallel"
    )
    
    return config_parser


__all__ = ["add_config_subparser"]