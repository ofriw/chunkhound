#!/bin/bash
set -e

# ChunkHound Unified Build Script
# The ONE script that replaces the complex multi-script build system
# Builds for macOS (native) and Ubuntu (Docker) using PyInstaller onedir format

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

# Build configuration
BUILD_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
HOST_PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
HOST_ARCH=$(uname -m)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Default options
CLEAN_BUILD=false
VALIDATE_BINARIES=false
VERBOSE=false
PLATFORM=""

# Version info
VERSION=$(grep '^version = ' "$PROJECT_ROOT/pyproject.toml" | sed 's/version = "\(.*\)"/\1/')

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${BOLD}🚀 $1${NC}"
}

# Usage information
show_usage() {
    cat << EOF
ChunkHound Unified Build Script v$VERSION

USAGE:
  ./scripts/build.sh [PLATFORM] [OPTIONS]

PLATFORMS:
  mac         Build macOS binary (native, requires macOS host)
  ubuntu      Build Ubuntu binary (Docker, works on any host)
  all         Build both platforms (requires macOS host)

OPTIONS:
  --clean     Clean previous artifacts before building
  --validate  Test binaries after build (startup time, basic functionality)
  --verbose   Show detailed build output
  --help      Show this help message

EXAMPLES:
  ./scripts/build.sh all                    # Build both platforms
  ./scripts/build.sh ubuntu --clean         # Clean build Ubuntu only
  ./scripts/build.sh mac --validate         # Build and test macOS binary
  ./scripts/build.sh all --clean --validate # Full clean build with testing

ARTIFACTS:
  dist/
  ├── chunkhound-macos-universal/          # macOS onedir
  ├── chunkhound-ubuntu-amd64/             # Ubuntu onedir
  ├── chunkhound-macos-universal.tar.gz    # Compressed macOS
  ├── chunkhound-ubuntu-amd64.tar.gz       # Compressed Ubuntu
  └── SHA256SUMS                           # Checksums

REQUIREMENTS:
  - Python 3.10+ with uv package manager
  - Docker (for Ubuntu builds)
  - macOS host (for macOS builds)

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            mac|ubuntu|all)
                if [[ -n "$PLATFORM" ]]; then
                    log_error "Multiple platforms specified. Use 'all' to build both."
                    exit 1
                fi
                PLATFORM="$1"
                shift
                ;;
            --clean)
                CLEAN_BUILD=true
                shift
                ;;
            --validate)
                VALIDATE_BINARIES=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Default to current platform if none specified
    if [[ -z "$PLATFORM" ]]; then
        if [[ "$HOST_PLATFORM" == "darwin" ]]; then
            PLATFORM="mac"
        else
            PLATFORM="ubuntu"
        fi
        log_info "No platform specified, defaulting to: $PLATFORM"
    fi
}

# Setup build environment
setup_build_env() {
    log_step "Setting up build environment"

    cd "$PROJECT_ROOT"

    # Verify uv is available
    if ! command -v uv &> /dev/null; then
        log_error "uv package manager not found. Install from: https://docs.astral.sh/uv/"
        exit 1
    fi

    # Clean artifacts if requested
    if [[ "$CLEAN_BUILD" == true ]]; then
        log_info "Cleaning previous artifacts..."
        rm -rf "$DIST_DIR"
    fi

    # Create dist directory
    mkdir -p "$DIST_DIR"

    # Sync dependencies
    log_info "Syncing dependencies with uv..."
    if [[ "$VERBOSE" == true ]]; then
        uv sync --dev
    else
        uv sync --dev > /dev/null 2>&1
    fi

    log_success "Build environment ready"
}

# Build macOS binary (native)
build_macos() {
    log_step "Building macOS binary (native)"

    if [[ "$HOST_PLATFORM" != "darwin" ]]; then
        log_error "macOS builds require macOS host. Current host: $HOST_PLATFORM"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    local output_dir="$DIST_DIR/chunkhound-macos-universal"
    local spec_file="chunkhound-optimized.spec"

    # Verify spec file exists
    if [[ ! -f "$spec_file" ]]; then
        log_error "PyInstaller spec file not found: $spec_file"
        exit 1
    fi

    log_info "Building with PyInstaller (onedir format)..."

    # Build with PyInstaller
    local build_cmd="uv run pyinstaller $spec_file --clean --noconfirm --distpath $DIST_DIR"

    if [[ "$VERBOSE" == true ]]; then
        $build_cmd
    else
        $build_cmd > /dev/null 2>&1
    fi

    # Verify output directory exists and rename if needed
    if [[ -d "$DIST_DIR/chunkhound-optimized" ]]; then
        # Clean target directory if it exists
        if [[ -d "$output_dir" ]]; then
            rm -rf "$output_dir"
        fi
        # Rename the PyInstaller output directory
        mv "$DIST_DIR/chunkhound-optimized" "$output_dir"
    elif [[ ! -d "$output_dir" ]]; then
        log_error "Build failed - output directory not found"
        exit 1
    fi

    # Verify binary exists and is executable
    local binary="$output_dir/chunkhound-optimized"
    if [[ ! -f "$binary" ]]; then
        log_error "Binary not found: $binary"
        exit 1
    fi

    chmod +x "$binary"

    # Create compressed archive
    log_info "Creating compressed archive..."
    cd "$DIST_DIR"
    tar -czf "chunkhound-macos-universal.tar.gz" "chunkhound-macos-universal/"

    log_success "macOS binary built successfully"
    log_info "Binary: $output_dir/chunkhound-optimized"
    log_info "Archive: $DIST_DIR/chunkhound-macos-universal.tar.gz"
}

# Build Ubuntu binary (Docker)
build_ubuntu() {
    log_step "Building Ubuntu binary (Docker)"

    # Verify Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Verify Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker daemon is not running. Start Docker and try again."
        exit 1
    fi

    cd "$PROJECT_ROOT"

    local output_dir="$DIST_DIR/chunkhound-ubuntu-amd64"
    local docker_tag="chunkhound:build-$BUILD_TIMESTAMP"

    log_info "Building with Docker (linux/amd64)..."

    # Build Docker image
    local build_cmd="docker build --platform linux/amd64 --target ubuntu-builder --tag $docker_tag"

    if [[ "$VERBOSE" == true ]]; then
        $build_cmd .
    else
        $build_cmd . > /dev/null 2>&1
    fi

    # Extract binary from container
    log_info "Extracting binary from Docker container..."

    local container_name="temp-ubuntu-$BUILD_TIMESTAMP"
    docker create --name "$container_name" "$docker_tag" > /dev/null

    # Create output directory
    mkdir -p "$output_dir"

    # Copy binary from container
    docker cp "$container_name":/app/dist/chunkhound-optimized/. "$output_dir/"

    # Clean up container
    docker rm "$container_name" > /dev/null

    # Clean up image
    docker rmi "$docker_tag" > /dev/null 2>&1 || true

    # Verify binary exists
    local binary="$output_dir/chunkhound-optimized"
    if [[ ! -f "$binary" ]]; then
        log_error "Binary not found after Docker extraction: $binary"
        exit 1
    fi

    chmod +x "$binary"

    # Create compressed archive
    log_info "Creating compressed archive..."
    cd "$DIST_DIR"
    tar -czf "chunkhound-ubuntu-amd64.tar.gz" "chunkhound-ubuntu-amd64/"

    log_success "Ubuntu binary built successfully"
    log_info "Binary: $output_dir/chunkhound-optimized"
    log_info "Archive: $DIST_DIR/chunkhound-ubuntu-amd64.tar.gz"
}

# Validate built binaries
validate_binaries() {
    log_step "Validating built binaries"

    local validation_failed=false

    # Test macOS binary
    if [[ -f "$DIST_DIR/chunkhound-macos-universal/chunkhound-optimized" ]]; then
        log_info "Testing macOS binary..."

        local binary="$DIST_DIR/chunkhound-macos-universal/chunkhound-optimized"

        # Test version command
        if ! "$binary" --version > /dev/null 2>&1; then
            log_error "macOS binary version check failed"
            validation_failed=true
        else
            local version_output=$("$binary" --version 2>&1)
            log_info "macOS binary version: $version_output"
        fi

        # Test help command (quick startup test)
        log_info "Testing macOS binary startup time..."
        local start_time=$(date +%s.%N)
        if ! "$binary" --help > /dev/null 2>&1; then
            log_error "macOS binary help command failed"
            validation_failed=true
        else
            local end_time=$(date +%s.%N)
            local startup_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "< 1.0")
            log_info "macOS binary startup time: ${startup_time}s"
        fi

        # Check binary size
        local size=$(ls -lh "$binary" | awk '{print $5}')
        log_info "macOS binary size: $size"
    fi

    # Test Ubuntu binary (only if we can run Linux binaries)
    if [[ -f "$DIST_DIR/chunkhound-ubuntu-amd64/chunkhound-optimized" ]]; then
        log_info "Testing Ubuntu binary..."

        local binary="$DIST_DIR/chunkhound-ubuntu-amd64/chunkhound-optimized"

        # Check if we can run Linux binaries (e.g., on Linux or via Docker)
        if [[ "$HOST_PLATFORM" == "linux" ]]; then
            # Test version command
            if ! "$binary" --version > /dev/null 2>&1; then
                log_error "Ubuntu binary version check failed"
                validation_failed=true
            else
                local version_output=$("$binary" --version 2>&1)
                log_info "Ubuntu binary version: $version_output"
            fi

            # Test startup time
            log_info "Testing Ubuntu binary startup time..."
            local start_time=$(date +%s.%N)
            if ! "$binary" --help > /dev/null 2>&1; then
                log_error "Ubuntu binary help command failed"
                validation_failed=true
            else
                local end_time=$(date +%s.%N)
                local startup_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "< 1.0")
                log_info "Ubuntu binary startup time: ${startup_time}s"
            fi
        else
            log_info "Skipping Ubuntu binary runtime test (wrong host platform)"
            log_info "Verifying binary file properties instead..."

            if file "$binary" | grep -q "ELF.*executable"; then
                log_info "Ubuntu binary is valid ELF executable"
            else
                log_error "Ubuntu binary is not a valid ELF executable"
                validation_failed=true
            fi
        fi

        # Check binary size
        local size=$(ls -lh "$binary" | awk '{print $5}')
        log_info "Ubuntu binary size: $size"
    fi

    if [[ "$validation_failed" == true ]]; then
        log_error "Binary validation failed"
        exit 1
    else
        log_success "All binaries validated successfully"
    fi
}

# Generate checksums
generate_checksums() {
    log_step "Generating checksums"

    cd "$DIST_DIR"

    # Remove old checksums
    rm -f SHA256SUMS

    # Generate checksums for all tar.gz files
    for file in *.tar.gz; do
        if [[ -f "$file" ]]; then
            sha256sum "$file" >> SHA256SUMS
        fi
    done

    if [[ -f "SHA256SUMS" ]]; then
        log_success "Checksums generated: $DIST_DIR/SHA256SUMS"
        if [[ "$VERBOSE" == true ]]; then
            cat SHA256SUMS
        fi
    fi
}

# Build summary
build_summary() {
    log_step "Build Summary"

    echo
    log_info "Build completed successfully!"
    log_info "Timestamp: $(date)"
    log_info "Platform(s): $PLATFORM"
    log_info "Output directory: $DIST_DIR"
    echo

    if [[ -d "$DIST_DIR" ]]; then
        log_info "Generated artifacts:"
        ls -la "$DIST_DIR" | grep -E '\.(tar\.gz|SHA256SUMS)$' || true
        echo

        # Show directory sizes
        for dir in "$DIST_DIR"/chunkhound-*; do
            if [[ -d "$dir" ]]; then
                local size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                local name=$(basename "$dir")
                log_info "$name: $size"
            fi
        done
    fi

    echo
    log_success "Ready for deployment! 🚀"
}

# Main execution
main() {
    # Show header
    echo -e "${BOLD}ChunkHound Unified Build Script v$VERSION${NC}"
    echo -e "${BLUE}Building high-performance code search binaries${NC}"
    echo

    # Parse arguments
    parse_args "$@"

    # Setup build environment
    setup_build_env

    # Build based on platform selection
    case "$PLATFORM" in
        mac)
            build_macos
            ;;
        ubuntu)
            build_ubuntu
            ;;
        all)
            build_macos
            build_ubuntu
            ;;
        *)
            log_error "Invalid platform: $PLATFORM"
            show_usage
            exit 1
            ;;
    esac

    # Generate checksums
    generate_checksums

    # Validate binaries if requested
    if [[ "$VALIDATE_BINARIES" == true ]]; then
        validate_binaries
    fi

    # Show build summary
    build_summary
}

# Execute main function with all arguments
main "$@"
