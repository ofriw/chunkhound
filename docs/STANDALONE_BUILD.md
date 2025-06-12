# ChunkHound Standalone Executable Distribution

This document describes how to build and distribute ChunkHound as a standalone executable using the unified build system with PyInstaller onedir deployment for optimal performance.

## Overview

ChunkHound can be packaged as a self-contained directory distribution that includes all dependencies, making it easy to distribute without requiring Python installation on target systems. The onedir deployment provides dramatically faster startup times compared to single-file executables.

## Performance

- **Startup Time**: ~0.6 seconds (16x faster than deprecated single-file deployment)
- **Distribution Size**: ~97MB directory (macOS), ~95MB (Ubuntu)
- **Runtime Performance**: Same as native Python
- **Dependencies**: Zero (fully self-contained)
- **Python CLI Performance**: ~0.3 seconds (90% improvement from original 2.7s)

## Quick Build

```bash
# Build using unified script (recommended)
./scripts/build.sh all

# Build specific platform
./scripts/build.sh mac      # macOS native build
./scripts/build.sh ubuntu   # Ubuntu Docker build

# Build with validation
./scripts/build.sh all --validate

# Or use Makefile shortcuts
make build-all-platforms
make build-macos-only
make build-linux-only
```

## Build Requirements

- Python 3.10+
- UV package manager (recommended)
- Docker (for Ubuntu builds)
- macOS (for macOS builds) or Linux (for Ubuntu Docker builds)

### Installing Build Dependencies

```bash
# Ensure all dependencies are synced
uv sync

# PyInstaller is automatically managed by the build system
```

## Unified Build System

The standalone build process uses a unified build script (`scripts/build.sh`) that:

1. **Detects platform automatically** (macOS native, Ubuntu via Docker)
2. **Packages all Python modules** from the service-layer architecture
3. **Includes native binaries** for tree-sitter language parsers and DuckDB
4. **Creates onedir distributions** with optimal startup performance
5. **Generates checksums** and compressed archives automatically
6. **Validates binaries** with startup time testing

### Build Artifacts

After a successful build, you'll find:

**macOS Build:**
- `chunkhound-macos-universal.tar.gz` - Compressed distribution
- `chunkhound-macos-universal/` - Directory containing executable
- SHA256SUMS - Checksum verification file

**Ubuntu Build:**
- `chunkhound-ubuntu.tar.gz` - Compressed distribution  
- `chunkhound-ubuntu/` - Directory containing executable
- SHA256SUMS - Checksum verification file

## Testing the Executable

The unified build script automatically validates executables, but you can test manually:

```bash
# Extract and test macOS build
tar -xzf chunkhound-macos-universal.tar.gz
cd chunkhound-macos-universal
./chunkhound --version
./chunkhound --help

# Extract and test Ubuntu build  
tar -xzf chunkhound-ubuntu.tar.gz
cd chunkhound-ubuntu
./chunkhound --version
./chunkhound --help

# Test indexing (no-embeddings mode for quick test)
./chunkhound run /path/to/code --no-embeddings --db test.db

# Test MCP server
./chunkhound mcp --db test.db
```

## Distribution

The standalone distribution provides optimal packaging for end users:

- **Size**: ~97MB (macOS), ~95MB (Ubuntu) - includes Python runtime and all dependencies
- **Dependencies**: None (fully self-contained)  
- **Platforms**: macOS Universal, Ubuntu (Linux x64), Windows (planned)
- **Performance**: ~0.6 second startup (16x faster than deprecated single-file)

### Distribution Artifacts

The build system automatically creates:

```bash
# Compressed archives ready for distribution
chunkhound-macos-universal.tar.gz
chunkhound-ubuntu.tar.gz

# Checksum verification
SHA256SUMS

# Directory distributions (extracted)
chunkhound-macos-universal/
chunkhound-ubuntu/
```

### User Installation

```bash
# Download and extract (macOS example)
curl -L https://github.com/your-org/chunkhound/releases/latest/chunkhound-macos-universal.tar.gz | tar -xz
cd chunkhound-macos-universal
./chunkhound --help

# Download and extract (Ubuntu example)  
wget https://github.com/your-org/chunkhound/releases/latest/chunkhound-ubuntu.tar.gz
tar -xzf chunkhound-ubuntu.tar.gz
cd chunkhound-ubuntu
./chunkhound --help
```

### Cross-Platform Builds

The unified build system supports multiple platforms from a single command:

```bash
# Build all supported platforms
./scripts/build.sh all

# Build specific platforms
./scripts/build.sh mac      # macOS native build (requires macOS)
./scripts/build.sh ubuntu   # Ubuntu build via Docker (requires Docker)

# Build with comprehensive validation
./scripts/build.sh all --clean --validate

# Makefile shortcuts
make build-all-platforms    # Builds both macOS and Ubuntu
make validate-binaries      # Full build + validation pipeline
```

**Platform Requirements:**
- **macOS builds**: Must run on macOS (native PyInstaller)  
- **Ubuntu builds**: Can run on any Docker-capable system
- **All platforms**: Can be built from macOS with Docker installed

## Build Configuration

The unified build system uses `scripts/build.sh` with platform-specific configurations:

### Included Dependencies

- **Service-layer architecture**: All modules (chunkhound, core, interfaces, providers, services, registry)
- **Tree-sitter binaries**: Language parsers for Python, Java, C#, TypeScript, JavaScript, Markdown
- **DuckDB binaries**: Native database library with vector search extensions
- **Python dependencies**: OpenAI, aiohttp, pydantic, loguru, MCP, tree-sitter, etc.

### Build Process Details

The unified script handles:

```bash
# Automatic dependency detection
# Platform-specific PyInstaller configuration  
# Native binary inclusion for all supported languages
# Service registry and provider pattern modules
# Hidden import resolution for modular architecture
# Onedir optimization for fast startup
# Automatic validation and checksum generation
```

## Troubleshooting

### Common Issues

1. **Build Failures**: Run `./scripts/build.sh --help` for comprehensive options
2. **Docker Issues**: Ensure Docker is running for Ubuntu builds  
3. **Permission Issues**: Verify executable permissions after extraction
4. **Missing Dependencies**: The unified script handles all dependencies automatically

### Build Failures

If the build fails:

```bash
# Clean build with verbose output
./scripts/build.sh all --clean --verbose

# Check Docker status (for Ubuntu builds)
docker --version
docker info

# Verify UV environment
uv sync --verbose
```

### Runtime Issues

If the executable doesn't work:

1. **Verify extraction**: Ensure the entire directory was extracted
2. **Check permissions**: `chmod +x chunkhound` if needed
3. **Test locally**: Build and test on the same platform first
4. **Validate checksums**: Use SHA256SUMS to verify download integrity

### Platform-Specific Issues

**macOS:**
- May require "Allow applications downloaded from anywhere" in Security settings
- Universal binary works on both Intel and Apple Silicon

**Ubuntu/Linux:**
- Requires glibc 2.17+ (Ubuntu 16.04+, CentOS 7+)  
- Built on Ubuntu 20.04 for maximum compatibility

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

# Rebuild all platforms with validation
./scripts/build.sh all --clean --validate

# Test specific platform
./scripts/build.sh mac --verbose

# Quick development cycle (no cleanup)
./scripts/build.sh mac && cd chunkhound-macos-universal && ./chunkhound --version
```

## CI/CD Integration

ChunkHound includes comprehensive CI/CD with GitHub Actions:

```yaml
# Integrated cross-platform build pipeline
- name: Build Cross-Platform Binaries
  run: |
    uv sync
    ./scripts/build.sh all --validate
    
- name: Upload macOS Binary
  uses: actions/upload-artifact@v3
  with:
    name: chunkhound-macos-universal
    path: chunkhound-macos-universal.tar.gz
    
- name: Upload Ubuntu Binary  
  uses: actions/upload-artifact@v3
  with:
    name: chunkhound-ubuntu
    path: chunkhound-ubuntu.tar.gz
```

See `.github/workflows/cross-platform-build.yml` for the complete pipeline.

## Performance Considerations

- **Startup Time**: ~0.6 seconds standalone vs ~0.3 seconds Python CLI (excellent performance)
- **Runtime Performance**: Identical to native Python after startup
- **Memory Usage**: Similar to Python (no unpacking overhead in onedir mode)
- **Disk Space**: ~97MB vs ~5MB for Python wheel (zero-dependency trade-off)

### Performance Evolution

- **Original Python CLI**: 2.7 seconds (problematic baseline)
- **Optimized Python CLI**: 0.3 seconds (90% improvement, current performance)
- **Single-file binary (deprecated)**: 15+ seconds startup due to extraction overhead  
- **Onedir binary (current)**: 0.6 seconds startup with no extraction needed

The unified build system with onedir deployment provides **production-ready performance** for both Python and standalone distributions.

## Security Notes

- The executable contains the full Python bytecode
- Source code structure is preserved in the executable
- Consider code obfuscation for sensitive applications
- Executable is not digitally signed by default

## Alternative Distribution Methods

Consider these alternatives based on your needs:

1. **Python Package** (`pip install chunkhound`) - Smallest (~5MB), requires Python 3.10+, 0.3s startup
2. **Onedir Distribution** - Zero dependencies, ~97MB, 0.6s startup, best for end users  
3. **Docker Image** - Best for server deployments and CI/CD
4. **System Packages** (DEB/RPM) - Best for Linux distributions (planned)

### Recommendation Matrix

| Use Case | Method | Pros | Cons |
|----------|--------|------|------|
| **Development** | Python package | Fast (0.3s), small size, easy updates | Requires Python 3.10+ |
| **End Users** | Onedir binary | Zero dependencies, easy distribution | Larger size (~97MB) |
| **Servers** | Docker image | Consistent environment, easy deployment | Container overhead |
| **CI/CD** | Docker or Python | Fast builds, cacheable layers | Platform dependencies |

For most **end-user distributions**, the **onedir deployment** provides optimal balance of simplicity and performance.

## Support

For build issues or questions:

1. Check this documentation
2. Review the `chunkhound.spec` file
3. Test with the provided build script
4. Open an issue on GitHub with build logs