#!/bin/bash
set -e

# Build script for ChunkHound standalone executable
# This script creates a self-contained executable using PyInstaller

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"

echo "🚀 Building ChunkHound standalone executable..."
echo "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

# Ensure PyInstaller is available
echo "🔍 Checking PyInstaller availability..."
if ! uv run python -c "import PyInstaller" 2>/dev/null; then
    echo "❌ PyInstaller not found. Installing..."
    uv add --dev pyinstaller
fi

# Build the executable
echo "🔨 Building standalone executable..."
uv run pyinstaller chunkhound.spec --clean --noconfirm

# Check if build was successful
if [ ! -f "$DIST_DIR/chunkhound" ]; then
    echo "❌ Build failed: executable not found in $DIST_DIR"
    exit 1
fi

# Test the executable
echo "🧪 Testing the executable..."
if ! "$DIST_DIR/chunkhound" --version >/dev/null 2>&1; then
    echo "❌ Build failed: executable doesn't work"
    exit 1
fi

# Replace the project-level binary
echo "🔄 Replacing project binary..."
if [ -f "$PROJECT_ROOT/chunkhound-cli" ]; then
    mv "$PROJECT_ROOT/chunkhound-cli" "$PROJECT_ROOT/chunkhound-cli.backup.$(date +%s)"
fi
cp "$DIST_DIR/chunkhound" "$PROJECT_ROOT/chunkhound-cli"
chmod +x "$PROJECT_ROOT/chunkhound-cli"

# Get executable size
EXEC_SIZE=$(du -h "$PROJECT_ROOT/chunkhound-cli" | cut -f1)

echo "✅ Standalone executable build complete!"
echo "📍 Location: $PROJECT_ROOT/chunkhound-cli"
echo "📦 Size: $EXEC_SIZE"
echo ""
echo "🧪 Final test:"
"$PROJECT_ROOT/chunkhound-cli" --version
echo ""
echo "🎉 Build successful! The standalone executable is ready to use."
echo ""
echo "Usage examples:"
echo "  ./chunkhound-cli --help"
echo "  ./chunkhound-cli run /path/to/code"
echo "  ./chunkhound-cli mcp --db ./chunks.db"