"""Shared utilities for MCP servers."""

import argparse


def add_common_mcp_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common MCP server arguments to a parser.

    This function adds all the configuration arguments that both
    stdio and HTTP MCP servers support.

    Args:
        parser: ArgumentParser to add arguments to
    """
    # Config file argument
    parser.add_argument("--config", type=str, help="Path to configuration file")

    # Database arguments
    parser.add_argument("--db", type=str, help="Database path")
    parser.add_argument(
        "--database-provider", choices=["duckdb", "lancedb"], help="Database provider"
    )

    # Embedding arguments
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama", "tei", "bge-icl", "openai-compatible"],
        help="Embedding provider",
    )
    parser.add_argument("--model", type=str, help="Embedding model")
    parser.add_argument("--api-key", type=str, help="API key for embedding provider")
    parser.add_argument("--base-url", type=str, help="Base URL for embedding provider")

    # Debug flag
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
