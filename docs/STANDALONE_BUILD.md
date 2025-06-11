# ChunkHound Standalone Executable Distribution

This document describes how to build and distribute ChunkHound as a standalone executable using PyInstaller.

## Overview

ChunkHound can be packaged as a self-contained executable that includes all dependencies, making it easy to distribute without requiring Python installation on target systems.

## Quick Build

```bash
# Build using Makefile (recommended)
make build-standalone

# Or build using the script directly
./scripts/build_standalone.sh

# Or build using PyInstaller directly
pyinstaller chunkhound.spec --clean
```

## Build Requirements

- Python 3.10+
- PyInstaller 6.14.1+
- All ChunkHound dependencies installed
- UV package manager (recommended)

### Installing Build Dependencies

```bash
# Install PyInstaller if not already installed
uv add --dev pyinstaller

# Ensure all dependencies are synced
uv sync
```

## Build Process

The standalone build process uses PyInstaller with a comprehensive spec file (`chunkhound.spec`) that:

1. **Packages all Python modules** from the main ChunkHound packages
2. **Includes native binaries** for tree-sitter language parsers and DuckDB
3. **Handles hidden imports** that PyInstaller might miss
4. **Creates a single executable** with all dependencies embedded

### Build Artifacts

After a successful build, you'll find:

- `dist/chunkhound` - The standalone executable
- `build/` - Temporary build files (can be deleted)
- `chunkhound-cli` - Copy of the executable in project root

## Testing the Executable

The build script automatically tests the executable, but you can test manually:

```bash
# Basic functionality
./chunkhound-cli --version
./chunkhound-cli --help

# Test indexing (no-embeddings mode for quick test)
./chunkhound-cli run /path/to/code --no-embeddings --db test.db

# Test MCP server
./chunkhound-cli mcp --db test.db
```

## Distribution

The standalone executable (`chunkhound-cli`) can be distributed as-is:

- **Size**: ~27MB (includes Python runtime and all dependencies)
- **Dependencies**: None (fully self-contained)
- **Platforms**: Built for the host platform (macOS, Linux, Windows)
- **Performance**: Slightly slower startup than native Python due to unpacking

### Cross-Platform Builds

To build for different platforms, you need to run the build on each target platform:

```bash
# On macOS - creates macOS executable
make build-standalone

# On Linux - creates Linux executable  
make build-standalone

# On Windows - creates Windows executable
make build-standalone
```

## Build Configuration

The build is configured in `chunkhound.spec` with the following key features:

### Included Dependencies

- **Core ChunkHound modules**: All packages (chunkhound, core, interfaces, providers, services, registry)
- **Tree-sitter binaries**: Language parsers for Python, Markdown, etc.
- **DuckDB binaries**: Native database library
- **Python dependencies**: OpenAI, aiohttp, pydantic, loguru, MCP, etc.

### Hidden Imports

The spec file explicitly includes modules that PyInstaller might miss:

```python
hiddenimports = [
    'chunkhound.api.cli.main',
    'chunkhound.mcp_entry',
    'core.models',
    'providers.embedding.openai_provider',
    'services.embedding_service',
    # ... and many more
]
```

### Excluded Modules

Large unused modules are excluded to reduce size:

```python
excludes = [
    'matplotlib', 'numpy.distutils', 'tkinter',
    'jupyter', 'pytest', 'sphinx'
]
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Add missing modules to `hiddenimports` in `chunkhound.spec`
2. **Missing Binaries**: Ensure native libraries are in the `datas` section
3. **Large Size**: Add unused modules to the `excludes` list
4. **Slow Startup**: Normal for PyInstaller executables due to unpacking

### Build Failures

If the build fails:

1. Clean previous builds: `rm -rf build/ dist/`
2. Check dependencies: `uv sync`
3. Verify spec file syntax
4. Check PyInstaller version compatibility

### Runtime Issues

If the executable doesn't work:

1. Test on the build machine first
2. Check for missing system libraries on target machine
3. Verify file permissions (`chmod +x chunkhound-cli`)
4. Check for antivirus interference

## Development Workflow

For development and testing:

```bash
# Make changes to code
# ...

# Rebuild executable
make build-standalone

# Test new executable
./chunkhound-cli --version
```

## CI/CD Integration

To integrate into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Build Standalone Executable
  run: |
    uv sync
    make build-standalone
    
- name: Upload Executable
  uses: actions/upload-artifact@v3
  with:
    name: chunkhound-${{ runner.os }}
    path: chunkhound-cli
```

## Performance Considerations

- **Startup Time**: ~2-3 seconds (vs <1 second for Python)
- **Runtime Performance**: Same as native Python after startup
- **Memory Usage**: Similar to Python + small overhead for unpacking
- **Disk Space**: 27MB vs ~5MB for Python wheel

## Security Notes

- The executable contains the full Python bytecode
- Source code structure is preserved in the executable
- Consider code obfuscation for sensitive applications
- Executable is not digitally signed by default

## Alternative Distribution Methods

Consider these alternatives based on your needs:

1. **Python Package** (`pip install chunkhound`) - Smallest, requires Python
2. **Docker Image** - Best for server deployments
3. **Standalone Executable** - Best for end-user distribution
4. **System Packages** (DEB/RPM) - Best for Linux distributions

## Support

For build issues or questions:

1. Check this documentation
2. Review the `chunkhound.spec` file
3. Test with the provided build script
4. Open an issue on GitHub with build logs