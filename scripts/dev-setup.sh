#!/usr/bin/env bash
# ChunkHound Development Setup - Index project and start MCP server
# Usage: ./scripts/dev-setup.sh [--index-only] [--server-only]

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Default options
RUN_INDEX=true
RUN_SERVER=true
DB_PATH="./.chunkhound.duckdb"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --index-only)
            RUN_SERVER=false
            shift
            ;;
        --server-only)
            RUN_INDEX=false
            shift
            ;;
        --db)
            DB_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--index-only] [--server-only] [--db path]"
            echo ""
            echo "Options:"
            echo "  --index-only   Only run indexing, don't start server"
            echo "  --server-only  Only start server, skip indexing"
            echo "  --db PATH      Use specific database path (default: ./.chunkhound.duckdb)"
            echo ""
            echo "Environment variables:"
            echo "  OPENAI_API_KEY  - Required for semantic search features"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 ChunkHound Development Setup${NC}"
echo "Project: $(pwd)"
echo "Database: $DB_PATH"
echo ""

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ uv is not installed. Please install it first:${NC}"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Index the project
if [[ "$RUN_INDEX" == "true" ]]; then
    echo -e "${YELLOW}📚 Indexing project...${NC}"
    
    # Check if database already exists
    if [[ -f "$DB_PATH" ]]; then
        echo "Existing database found, re-indexing..."
    fi
    
    # Run indexing with verbose output
    if uv run chunkhound run . --db "$DB_PATH" --verbose; then
        echo -e "${GREEN}✅ Indexing completed successfully${NC}"
        
        # Show stats
        echo -e "${BLUE}📊 Database Statistics:${NC}"
        uv run chunkhound run . --db "$DB_PATH" --stats || echo "Stats not available"
    else
        echo -e "${RED}❌ Indexing failed${NC}"
        exit 1
    fi
    echo ""
fi

# Start MCP server
if [[ "$RUN_SERVER" == "true" ]]; then
    echo -e "${YELLOW}🚀 Starting MCP server...${NC}"
    echo "Database: $DB_PATH"
    
    # Check if OpenAI API key is set
    if [[ -z "$OPENAI_API_KEY" ]]; then
        echo -e "${YELLOW}⚠️  OPENAI_API_KEY not set - semantic search will be unavailable${NC}"
    else
        echo -e "${GREEN}✅ OpenAI API key configured${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}🔧 MCP server tools available:${NC}"
    echo "  • search_regex - Search code with regex patterns"
    echo "  • search_semantic - AI-powered semantic search"
    echo "  • get_stats - Database statistics"
    echo "  • health_check - Server health status"
    echo ""
    echo -e "${BLUE}Use Ctrl+C to stop the server${NC}"
    echo ""
    
    export CHUNKHOUND_DB_PATH="$DB_PATH"
    exec uv run chunkhound mcp --db "$DB_PATH" --verbose
fi

echo -e "${GREEN}✅ Setup complete!${NC}"