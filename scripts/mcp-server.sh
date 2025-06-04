#!/usr/bin/env bash
# ChunkHound MCP Server - Easy startup script for IDEs like Zed
# Usage: ./scripts/mcp-server.sh [--db path/to/db] [--verbose]

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Default database path
DB_PATH="${CHUNKHOUND_DB_PATH:-$HOME/.cache/chunkhound/chunks.duckdb}"

# Parse arguments
ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            DB_PATH="$2"
            shift 2
            ;;
        --verbose|-v)
            ARGS+=("--verbose")
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--db path/to/db] [--verbose]"
            echo ""
            echo "Environment variables:"
            echo "  CHUNKHOUND_DB_PATH  - Default database path"
            echo "  OPENAI_API_KEY      - Required for semantic search"
            echo ""
            echo "Examples:"
            echo "  $0                              # Use default database"
            echo "  $0 --db ./my-project.duckdb    # Use specific database"
            echo "  $0 --verbose                   # Enable verbose logging"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure database directory exists
mkdir -p "$(dirname "$DB_PATH")"

# Check if database exists, suggest indexing if not
if [[ ! -f "$DB_PATH" ]]; then
    echo "Warning: Database not found at $DB_PATH"
    echo "Run 'uv run chunkhound run .' to index the current directory first"
    echo ""
fi

# Export environment variables for the MCP server
export CHUNKHOUND_DB_PATH="$DB_PATH"

# Start MCP server using uv
echo "Starting ChunkHound MCP server..."
echo "Database: $DB_PATH"
echo "Use Ctrl+C to stop"
echo ""

exec uv run chunkhound mcp --db "$DB_PATH" "${ARGS[@]}"