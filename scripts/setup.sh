#!/bin/bash
# ChunkHound Development Setup Script
# Makes it dead simple to get started with development

set -e

echo "🔧 ChunkHound Development Setup"
echo "================================="

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
required_version="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Python 3.8+ required. Found: Python $python_version"
    echo "   Please install Python 3.8 or higher"
    exit 1
fi

echo "✅ Python $python_version detected"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install package in development mode
echo "📥 Installing ChunkHound in development mode..."
pip install -e ".[dev]"

# Verify installation
echo "🧪 Verifying installation..."
chunkhound --version

echo ""
echo "🎉 Setup Complete!"
echo "==================="
echo ""
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo ""
echo "Common commands:"
echo "  chunkhound run .           # Index current directory"
echo "  chunkhound server          # Start API server"
echo "  make test                  # Run tests"
echo "  make dev                   # Start development server"
echo "  make help                  # See all available commands"
echo ""
echo "Happy coding! 🚀"