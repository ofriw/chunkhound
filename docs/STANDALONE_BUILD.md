# ChunkHound Standalone Executable Distribution

This document describes how to build and distribute ChunkHound as a standalone executable using PyInstaller with onedir deployment for optimal performance.

## Overview

ChunkHound can be packaged as a self-contained directory distribution that includes all dependencies, making it easy to distribute without requiring Python installation on target systems. The onedir deployment provides dramatically faster startup times compared to single-file executables.

## Performance

- **Startup Time**: ~0.6 seconds (16x faster than single-file deployment)
- **Distribution Size**: ~106MB directory
- **Runtime Performance**: Same as native Python
- **Dependencies**: Zero (fully self-contained)

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
4. **Creates a directory distribution** with fast startup (onedir mode)
5. **Eliminates extraction overhead** that causes slow startup in single-file mode

### Build Artifacts

After a successful build, you'll find:

- `dist/chunkhound/` - The onedir distribution directory containing:
  - `chunkhound` - The main executable
  - `_internal/` - Dependencies and libraries
- `build/` - Temporary build files (can be deleted)
- `chunkhound-cli-fast` - Wrapper script for easy execution
- `chunkhound-cli` - Symlink to the wrapper script

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

The standalone distribution can be packaged and distributed:

- **Size**: ~106MB directory (includes Python runtime and all dependencies)
- **Dependencies**: None (fully self-contained)
- **Platforms**: Built for the host platform (macOS, Linux, Windows)
- **Performance**: ~0.6 second startup (practically as fast as native Python)

### Distribution Packaging

```bash
# Create a tarball for distribution
tar -czf chunkhound-linux.tar.gz -C dist chunkhound

# Or create a zip file
cd dist && zip -r ../chunkhound-linux.zip chunkhound/
```

### User Installation

```bash
# Extract and use
tar -xzf chunkhound-linux.tar.gz
cd chunkhound
./chunkhound --help

# Or use the wrapper script (if provided)
./chunkhound-cli --help
```

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

### Onedir Configuration

The spec file uses onedir mode for optimal performance:

```python
# Onedir mode configuration
exe = EXE(
    pyz,
    a.scripts,
    [],                    # No binaries embedded
    exclude_binaries=True, # Onedir mode
    name='chunkhound',
    upx=False,            # Disabled for speed
    # ...
)

# Directory collection
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles, 
    a.datas,
    name='chunkhound',
)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Add missing modules to `hiddenimports` in `chunkhound.spec`
2. **Missing Binaries**: Ensure native libraries are in the `datas` section
3. **Large Size**: Add unused modules to the `excludes` list
4. **Directory Structure**: Ensure you're distributing the entire `dist/chunkhound/` directory

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

- **Startup Time**: ~0.6 seconds (practically as fast as native Python)
- **Runtime Performance**: Same as native Python after startup
- **Memory Usage**: Similar to Python (no unpacking overhead)
- **Disk Space**: 106MB vs ~5MB for Python wheel (acceptable trade-off for zero dependencies)

### Performance History

- **Single-file mode (deprecated)**: 15+ seconds startup due to extraction overhead
- **Onedir mode (current)**: 0.6 seconds startup with no extraction needed
- **Python package**: 0.4 seconds startup (baseline performance)

The switch to onedir deployment achieved a **16x performance improvement** over single-file mode.

## Security Notes

- The executable contains the full Python bytecode
- Source code structure is preserved in the executable
- Consider code obfuscation for sensitive applications
- Executable is not digitally signed by default

## Alternative Distribution Methods

Consider these alternatives based on your needs:

1. **Python Package** (`pip install chunkhound`) - Smallest (~5MB), requires Python, 0.4s startup
2. **Onedir Distribution** - Zero dependencies, ~106MB, 0.6s startup, best for end users
3. **Docker Image** - Best for server deployments
4. **System Packages** (DEB/RPM) - Best for Linux distributions

### Recommendation

For most end-user distributions, the **onedir deployment** provides the best balance of:
- Zero dependencies (no Python installation required)
- Fast startup performance (0.6s)
- Easy distribution (single directory)
- Cross-platform compatibility

## Support

For build issues or questions:

1. Check this documentation
2. Review the `chunkhound.spec` file
3. Test with the provided build script
4. Open an issue on GitHub with build logs