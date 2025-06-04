#!/bin/bash
# ChunkHound Development Setup Script
# Makes it dead simple to get started with development

set -e

echo "🔧 ChunkHound Development Setup"
echo "================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is required but not installed"
    echo "   Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv detected"

# Sync dependencies with uv
echo "📦 Installing dependencies with uv..."
uv sync

# Verify installation
echo "🧪 Verifying installation..."
uv run chunkhound --version

echo ""
echo "🎉 Setup Complete!"
echo "==================="
echo ""
echo "To use ChunkHound:"
echo "  uv run chunkhound run .    # Index current directory"
echo "  uv run chunkhound mcp      # Start MCP server"
echo ""
echo "Development commands:"
echo "  make test                  # Run tests"
echo "  make dev                   # Index current directory"
echo "  make help                  # See all available commands"
echo ""
echo "Happy coding! 🚀"