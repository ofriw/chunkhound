#!/bin/bash
set -e

# ChunkHound Unified Dual Build Pipeline Orchestrator
# Builds binaries for all supported platforms with single command execution
# Platform-aware: macOS builds all platforms, Linux builds Linux only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
ARTIFACTS_DIR="$DIST_DIR/artifacts"
LOGS_DIR="$DIST_DIR/build-reports"

# Build configuration
BUILD_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
HOST_PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
HOST_ARCH=$(uname -m)
BUILD_ID="build-$BUILD_TIMESTAMP"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default configuration
CLEAN_BUILD=false
RUN_TESTS=false
PARALLEL_BUILD=true
ENABLE_SIGNING=false
ENABLE_NOTARIZATION=false
SKIP_DOCKER=false
SKIP_MACOS=false
VERBOSE=false
DRY_RUN=false

# Performance tracking
BUILD_START_TIME=$(date +%s)

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

log_section() {
    echo -e "\n${BOLD}${CYAN}🚀 $1${NC}"
    echo -e "${CYAN}$(printf '=%.0s' {1..50})${NC}"
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}🔍 $1${NC}"
    fi
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Build pipeline failed! Exit code: $exit_code"
        log_info "Check logs in: $LOGS_DIR"
    fi
}
trap cleanup EXIT

# Help function
show_help() {
    cat << EOF
ChunkHound Unified Dual Build Pipeline Orchestrator

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}DESCRIPTION:${NC}
    Builds ChunkHound binaries for all supported platforms with unified orchestration.
    Platform-aware: macOS builds all platforms, Linux builds Linux only.

${BOLD}OPTIONS:${NC}
    -h, --help                Show this help message
    -c, --clean               Clean all build directories before building
    -t, --test                Run validation tests after building
    -p, --parallel            Enable parallel builds (default: true)
    -s, --sign                Enable code signing (macOS only, requires setup)
    -n, --notarize            Enable notarization (macOS only, requires Apple ID)
    -v, --verbose             Enable verbose logging
    --dry-run                 Show what would be built without building
    --skip-docker             Skip Docker Linux builds
    --skip-macos              Skip native macOS builds (macOS only)
    --output-dir DIR          Custom output directory (default: dist/artifacts)
    --build-id ID             Custom build identifier (default: build-TIMESTAMP)

${BOLD}PLATFORM MATRIX:${NC}
    Linux Host:     Docker Linux (amd64)
    macOS Host:     Docker Linux (amd64) + Native macOS (Intel + Apple Silicon + Universal)

${BOLD}EXAMPLES:${NC}
    $0                        # Build all available platforms
    $0 --clean --test         # Clean build with validation
    $0 --skip-docker          # macOS native builds only
    $0 --parallel --verbose   # Parallel builds with detailed logging
    $0 --sign --notarize      # Production build with signing (macOS)
    $0 --dry-run              # Preview build plan

${BOLD}OUTPUT STRUCTURE:${NC}
    dist/artifacts/
    ├── linux/                Linux binaries (via Docker)
    ├── macos/                macOS binaries (native, macOS host only)
    │   ├── intel/            Intel (x86_64) binary
    │   ├── apple-silicon/    Apple Silicon (arm64) binary
    │   └── universal/        Universal binary (Intel + Apple Silicon)
    ├── checksums/            SHA256 checksums for all binaries
    └── build-reports/        Build logs and performance reports

${BOLD}PREREQUISITES:${NC}
    All Platforms:    Python 3.11+, uv, Git
    Docker Builds:    Docker with BuildKit support
    macOS Builds:     Xcode Command Line Tools, macOS 10.15+
    Code Signing:     Apple Developer account and certificates
EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--clean)
                CLEAN_BUILD=true
                shift
                ;;
            -t|--test)
                RUN_TESTS=true
                shift
                ;;
            -p|--parallel)
                PARALLEL_BUILD=true
                shift
                ;;
            --no-parallel)
                PARALLEL_BUILD=false
                shift
                ;;
            -s|--sign)
                ENABLE_SIGNING=true
                shift
                ;;
            -n|--notarize)
                ENABLE_NOTARIZATION=true
                ENABLE_SIGNING=true  # Notarization requires signing
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-macos)
                SKIP_MACOS=true
                shift
                ;;
            --output-dir)
                ARTIFACTS_DIR="$2"
                shift 2
                ;;
            --build-id)
                BUILD_ID="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Check platform compatibility
check_platform_compatibility() {
    log_section "Platform Compatibility Check"

    log_info "Host Platform: $HOST_PLATFORM ($HOST_ARCH)"

    case "$HOST_PLATFORM" in
        darwin)
            log_success "macOS host detected - all platforms available"
            if [ "$SKIP_DOCKER" = false ]; then
                BUILD_PLATFORMS="docker-linux macos-intel macos-apple-silicon macos-universal"
            else
                BUILD_PLATFORMS="macos-intel macos-apple-silicon macos-universal"
            fi
            ;;
        linux)
            log_info "Linux host detected - Docker Linux builds only"
            if [ "$SKIP_MACOS" = false ]; then
                log_warning "macOS builds not available on Linux host (skipping)"
            fi
            BUILD_PLATFORMS="docker-linux"
            ;;
        *)
            log_error "Unsupported host platform: $HOST_PLATFORM"
            log_error "Supported platforms: macOS (all builds), Linux (Docker builds only)"
            exit 2
            ;;
    esac

    log_info "Planned builds: $BUILD_PLATFORMS"

    if [ "$DRY_RUN" = true ]; then
        log_section "Dry Run - Build Plan"
        for platform in $BUILD_PLATFORMS; do
            log_info "Would build: $platform"
        done
        exit 0
    fi
}

# Check prerequisites
check_prerequisites() {
    log_section "Prerequisites Check"

    local missing_deps=()

    # Check Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        log_success "Python 3: $(python3 --version)"
    fi

    # Check uv
    if ! command -v uv &> /dev/null; then
        missing_deps+=("uv")
    else
        log_success "uv: $(uv --version)"
    fi

    # Check Git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        log_success "Git: $(git --version | head -1)"
    fi

    # Check Docker (if needed)
    if [[ "$BUILD_PLATFORMS" == *"docker"* ]]; then
        if ! command -v docker &> /dev/null; then
            missing_deps+=("docker")
        elif ! docker info &> /dev/null; then
            log_error "Docker daemon not running"
            missing_deps+=("docker-daemon")
        else
            log_success "Docker: $(docker --version)"
        fi
    fi

    # Check macOS-specific tools
    if [[ "$BUILD_PLATFORMS" == *"macos"* ]]; then
        if ! xcode-select -p &> /dev/null; then
            missing_deps+=("xcode-command-line-tools")
        else
            log_success "Xcode Command Line Tools: $(xcode-select --version)"
        fi
    fi

    # Report missing dependencies
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing prerequisites:"
        for dep in "${missing_deps[@]}"; do
            case $dep in
                python3)
                    log_error "  • Python 3.11+ - Install via Homebrew: brew install python@3.11"
                    ;;
                uv)
                    log_error "  • uv package manager - Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
                    ;;
                git)
                    log_error "  • Git - Install via Homebrew: brew install git"
                    ;;
                docker)
                    log_error "  • Docker - Install Docker Desktop or Docker Engine"
                    ;;
                docker-daemon)
                    log_error "  • Docker daemon - Start Docker Desktop or dockerd"
                    ;;
                xcode-command-line-tools)
                    log_error "  • Xcode Command Line Tools - Run: xcode-select --install"
                    ;;
            esac
        done
        exit 3
    fi

    # Check project structure
    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log_error "Not in ChunkHound project root (missing pyproject.toml)"
        log_error "Current directory: $(pwd)"
        log_error "Expected project root: $PROJECT_ROOT"
        exit 3
    fi

    log_success "All prerequisites satisfied"
}

# Setup build environment
setup_build_environment() {
    log_section "Build Environment Setup"

    # Create directory structure
    mkdir -p "$ARTIFACTS_DIR"/{linux,macos/{intel,apple-silicon,universal},checksums}
    mkdir -p "$LOGS_DIR"

    # Clean if requested
    if [ "$CLEAN_BUILD" = true ]; then
        log_info "Cleaning previous builds..."
        rm -rf "$ARTIFACTS_DIR"/*
        rm -rf "$DIST_DIR"/chunkhound-*
        log_success "Build directories cleaned"
    fi

    # Get version information
    cd "$PROJECT_ROOT"
    if [ -z "$CHUNKHOUND_VERSION" ]; then
        if command -v uv &> /dev/null && [ -f "pyproject.toml" ]; then
            CHUNKHOUND_VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "dev")
        else
            CHUNKHOUND_VERSION="dev"
        fi
    fi

    log_info "Build Configuration:"
    log_info "  Version: $CHUNKHOUND_VERSION"
    log_info "  Build ID: $BUILD_ID"
    log_info "  Timestamp: $BUILD_TIMESTAMP"
    log_info "  Parallel: $PARALLEL_BUILD"
    log_info "  Output: $ARTIFACTS_DIR"

    if [ "$HOST_PLATFORM" = "darwin" ]; then
        log_info "  Code Signing: $ENABLE_SIGNING"
        log_info "  Notarization: $ENABLE_NOTARIZATION"
    fi

    log_success "Build environment ready"
}

# Build Docker Linux binary
build_docker_linux() {
    if [[ "$BUILD_PLATFORMS" != *"docker-linux"* ]]; then
        return 0
    fi

    log_section "Building Docker Linux Binary"
    BUILD_STATUS["docker-linux"]="BUILDING"

    local start_time=$(date +%s)
    local log_file="$LOGS_DIR/docker-linux-build.log"

    log_info "Building Linux binary via Docker..."
    log_verbose "Log file: $log_file"

    # Use existing Docker build script
    local docker_output="$ARTIFACTS_DIR/linux"
    mkdir -p "$docker_output"

    if [ "$VERBOSE" = true ]; then
        "$SCRIPT_DIR/docker-build-all.sh" --platforms linux/amd64 --output "$docker_output" 2>&1 | tee "$log_file"
    else
        "$SCRIPT_DIR/docker-build-all.sh" --platforms linux/amd64 --output "$docker_output" > "$log_file" 2>&1
    fi

    local exit_code=$?
    local end_time=$(date +%s)
    local build_time=$((end_time - start_time))

    if [ $exit_code -eq 0 ]; then
        echo "docker-linux:SUCCESS:$build_time" >> "$LOGS_DIR/build_status.tmp"
        log_success "Docker Linux build completed (${build_time}s)"

        # Validate binary exists
        if find "$docker_output" -name "chunkhound*" -type f | grep -q .; then
            log_success "Linux binary artifacts validated"
        else
            log_error "Linux binary artifacts not found"
            echo "docker-linux:FAILED:$build_time" >> "$LOGS_DIR/build_status.tmp"
            return 1
        fi
    else
        echo "docker-linux:FAILED:$build_time" >> "$LOGS_DIR/build_status.tmp"
        log_error "Docker Linux build failed (exit code: $exit_code)"
        log_error "Check log: $log_file"
        return 1
    fi
}

# Build macOS binary for specific architecture
build_macos_arch() {
    local target_arch=$1
    local arch_name=$2
    local platform_key="macos-$arch_name"

    log_info "Building macOS $arch_name ($target_arch) binary..."

    local start_time=$(date +%s)
    local log_file="$LOGS_DIR/macos-$arch_name-build.log"
    local output_dir="$ARTIFACTS_DIR/macos/$arch_name"

    mkdir -p "$output_dir"

    # Set environment for specific architecture build
    export MACOS_BUILD_ARCH="$target_arch"
    export CUSTOM_BUNDLE_NAME="chunkhound-macos-$arch_name"

    if [ "$ENABLE_SIGNING" = true ]; then
        export ENABLE_SIGNING=true
    fi
    if [ "$ENABLE_NOTARIZATION" = true ]; then
        export ENABLE_NOTARIZATION=true
    fi

    # Build using existing macOS build script
    if [ "$VERBOSE" = true ]; then
        "$SCRIPT_DIR/build-macos-native.sh" --clean 2>&1 | tee "$log_file"
    else
        "$SCRIPT_DIR/build-macos-native.sh" --clean > "$log_file" 2>&1
    fi

    local exit_code=$?
    local end_time=$(date +%s)
    local build_time=$((end_time - start_time))

    if [ $exit_code -eq 0 ]; then
        # Move built binary to artifacts directory
        if [ -d "$DIST_DIR/chunkhound-macos-$arch_name" ]; then
            cp -r "$DIST_DIR/chunkhound-macos-$arch_name" "$output_dir/"

            # Create tarball
            cd "$output_dir"
            tar -czf "chunkhound-macos-$arch_name-$BUILD_TIMESTAMP.tar.gz" "chunkhound-macos-$arch_name"

            echo "$platform_key:SUCCESS:$build_time" >> "$LOGS_DIR/build_status.tmp"
            log_success "macOS $arch_name build completed (${build_time}s)"
        else
            echo "$platform_key:FAILED:$build_time" >> "$LOGS_DIR/build_status.tmp"
            log_error "macOS $arch_name binary not found after build"
            return 1
        fi
    else
        echo "$platform_key:FAILED:$build_time" >> "$LOGS_DIR/build_status.tmp"
        log_error "macOS $arch_name build failed (exit code: $exit_code)"
        log_error "Check log: $log_file"
        return 1
    fi
}

# Build Universal macOS binary
build_universal_binary() {
    local platform_key="macos-universal"

    # Check if prerequisite builds succeeded
    local intel_status=$(grep "macos-intel:" "$LOGS_DIR/build_status.tmp" 2>/dev/null | cut -d: -f2)
    local arm_status=$(grep "macos-apple-silicon:" "$LOGS_DIR/build_status.tmp" 2>/dev/null | cut -d: -f2)

    if [ "$intel_status" != "SUCCESS" ] || [ "$arm_status" != "SUCCESS" ]; then
        log_warning "Universal binary requires both Intel and Apple Silicon builds"
        echo "$platform_key:SKIPPED:0" >> "$LOGS_DIR/build_status.tmp"
        return 0
    fi

    log_info "Building Universal macOS binary..."

    local start_time=$(date +%s)
    local output_dir="$ARTIFACTS_DIR/macos/universal"
    local intel_binary="$ARTIFACTS_DIR/macos/intel/chunkhound-macos-intel/chunkhound-macos-intel"
    local arm_binary="$ARTIFACTS_DIR/macos/apple-silicon/chunkhound-macos-apple-silicon/chunkhound-macos-apple-silicon"

    mkdir -p "$output_dir/chunkhound-macos-universal"

    # Create universal binary using lipo
    if lipo -create "$intel_binary" "$arm_binary" -output "$output_dir/chunkhound-macos-universal/chunkhound-macos-universal"; then
        # Copy supporting files from Intel build
        cp -r "$ARTIFACTS_DIR/macos/intel/chunkhound-macos-intel"/* "$output_dir/chunkhound-macos-universal/" 2>/dev/null || true

        # Replace binary with universal version
        cp "$output_dir/chunkhound-macos-universal/chunkhound-macos-universal" "$output_dir/chunkhound-macos-universal/"

        # Create tarball
        cd "$output_dir"
        tar -czf "chunkhound-macos-universal-$BUILD_TIMESTAMP.tar.gz" "chunkhound-macos-universal"

        local end_time=$(date +%s)
        local build_time=$((end_time - start_time))
        echo "$platform_key:SUCCESS:$build_time" >> "$LOGS_DIR/build_status.tmp"

        log_success "Universal macOS binary created (${build_time}s)"

        # Verify universal binary
        if lipo -info "$output_dir/chunkhound-macos-universal/chunkhound-macos-universal" | grep -q "x86_64 arm64"; then
            log_success "Universal binary verification passed"
        else
            log_warning "Universal binary verification failed"
        fi
    else
        local end_time=$(date +%s)
        local build_time=$((end_time - start_time))
        echo "$platform_key:FAILED:$build_time" >> "$LOGS_DIR/build_status.tmp"
        log_error "Failed to create universal binary with lipo"
        return 1
    fi
}

# Build macOS native binaries
build_macos_native() {
    if [[ "$BUILD_PLATFORMS" != *"macos"* ]] || [ "$HOST_PLATFORM" != "darwin" ]; then
        return 0
    fi

    log_section "Building macOS Native Binaries"

    # Build Intel binary
    if [[ "$BUILD_PLATFORMS" == *"macos-intel"* ]]; then
        build_macos_arch "x86_64" "intel"
    fi

    # Build Apple Silicon binary
    if [[ "$BUILD_PLATFORMS" == *"macos-apple-silicon"* ]]; then
        build_macos_arch "arm64" "apple-silicon"
    fi

    # Build Universal binary
    if [[ "$BUILD_PLATFORMS" == *"macos-universal"* ]]; then
        build_universal_binary
    fi
}

# Generate checksums
generate_checksums() {
    log_section "Generating Checksums"

    local checksum_file="$ARTIFACTS_DIR/checksums/SHA256SUMS"
    mkdir -p "$(dirname "$checksum_file")"

    log_info "Computing SHA256 checksums..."

    # Find all binary files and tarballs
    find "$ARTIFACTS_DIR" -type f \( -name "*.tar.gz" -o -name "chunkhound*" \) -not -path "*/checksums/*" | while read -r file; do
        local relative_path=$(echo "$file" | sed "s|$ARTIFACTS_DIR/||")
        local checksum=$(shasum -a 256 "$file" | cut -d' ' -f1)
        echo "$checksum  $relative_path" >> "$checksum_file"
        log_verbose "  $checksum  $relative_path"
    done

    if [ -f "$checksum_file" ]; then
        log_success "Checksums generated: $checksum_file"
        local count=$(wc -l < "$checksum_file")
        log_info "  Files processed: $count"
    else
        log_warning "No files found for checksum generation"
    fi
}

# Test Linux binary
test_linux_binary() {
    local binary_path=$(find "$ARTIFACTS_DIR/linux" -name "chunkhound*" -type f -executable | head -1)

    if [ -z "$binary_path" ]; then
        log_error "Linux binary not found for testing"
        return 1
    fi

    log_verbose "Testing binary: $binary_path"

    # Test in Docker for consistent environment
    if docker run --rm -v "$ARTIFACTS_DIR/linux:/test" ubuntu:22.04 /bin/bash -c "
        /test/$(basename "$binary_path") --version &&
        /test/$(basename "$binary_path") --help > /dev/null
    " 2>/dev/null; then
        log_success "Linux binary tests passed"
        return 0
    else
        log_error "Linux binary tests failed"
        return 1
    fi
}

# Test macOS binary
test_macos_binary() {
    local platform=$1
    local arch_name=$(echo "$platform" | sed 's/macos-//')
    local binary_path="$ARTIFACTS_DIR/macos/$arch_name/chunkhound-macos-$arch_name/chunkhound-macos-$arch_name"

    if [ ! -f "$binary_path" ]; then
        log_error "$platform binary not found for testing: $binary_path"
        return 1
    fi

    log_verbose "Testing binary: $binary_path"

    # Basic functionality tests
    if "$binary_path" --version >/dev/null 2>&1 && "$binary_path" --help >/dev/null 2>&1; then
        log_success "$platform binary tests passed"
        return 0
    else
        log_error "$platform binary tests failed"
        return 1
    fi
}

# Run validation tests
run_validation_tests() {
    if [ "$RUN_TESTS" != true ]; then
        return 0
    fi

    log_section "Running Validation Tests"

    local failed_tests=0

    # Test each built binary using status file
    if [ -f "$LOGS_DIR/build_status.tmp" ]; then
        while IFS=: read -r platform status build_time; do
            if [ "$status" = "SUCCESS" ]; then
                log_info "Testing $platform binary..."

                case $platform in
                    docker-linux)
                        test_linux_binary || ((failed_tests++))
                        ;;
                    macos-*)
                        test_macos_binary "$platform" || ((failed_tests++))
                        ;;
                esac
            fi
        done < "$LOGS_DIR/build_status.tmp"
    fi

    if [ $failed_tests -eq 0 ]; then
        log_success "All validation tests passed"
    else
        log_error "$failed_tests validation tests failed"
        return 4
    fi
}

# Generate build report
generate_build_report() {
    log_section "Generating Build Report"

    local report_file="$LOGS_DIR/build-report-$BUILD_TIMESTAMP.json"
    local markdown_report="$LOGS_DIR/BUILD_REPORT.md"

    # JSON report
    cat > "$report_file" << EOF
{
  "build_id": "$BUILD_ID",
  "timestamp": "$BUILD_TIMESTAMP",
  "version": "$CHUNKHOUND_VERSION",
  "host_platform": "$HOST_PLATFORM",
  "host_arch": "$HOST_ARCH",
  "build_configuration": {
    "clean_build": $CLEAN_BUILD,
    "parallel_build": $PARALLEL_BUILD,
    "run_tests": $RUN_TESTS,
    "enable_signing": $ENABLE_SIGNING,
    "enable_notarization": $ENABLE_NOTARIZATION
  },
  "build_results": {
EOF

    local first=true
    if [ -f "$LOGS_DIR/build_status.tmp" ]; then
        while IFS=: read -r platform status build_time; do
            if [ "$first" = true ]; then
                first=false
            else
                echo "," >> "$report_file"
            fi
            echo "    \"$platform\": {" >> "$report_file"
            echo "      \"status\": \"$status\"," >> "$report_file"
            echo "      \"build_time\": $build_time" >> "$report_file"
            echo -n "    }" >> "$report_file"
        done < "$LOGS_DIR/build_status.tmp"
    fi

    echo "" >> "$report_file"
    echo "  }," >> "$report_file"

    local total_time=$(($(date +%s) - BUILD_START_TIME))
    echo "  \"total_build_time\": $total_time" >> "$report_file"
    echo "}" >> "$report_file"

    # Markdown report
    cat > "$markdown_report" << EOF
# ChunkHound Dual Build Pipeline Report

**Build ID:** $BUILD_ID
**Version:** $CHUNKHOUND_VERSION
**Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Host:** $HOST_PLATFORM ($HOST_ARCH)

## Build Configuration
- Clean Build: $CLEAN_BUILD
- Parallel Build: $PARALLEL_BUILD
- Run Tests: $RUN_TESTS
- Code Signing: $ENABLE_SIGNING
- Notarization: $ENABLE_NOTARIZATION

## Build Results

| Platform | Status | Build Time |
|----------|--------|------------|
EOF

    if [ -f "$LOGS_DIR/build_status.tmp" ]; then
        while IFS=: read -r platform status build_time; do
            local status_icon="❌"
            case "$status" in
                SUCCESS) status_icon="✅" ;;
                BUILDING) status_icon="🔄" ;;
                SKIPPED) status_icon="⏭️" ;;
            esac
            echo "| $platform | $status_icon $status | ${build_time}s |" >> "$markdown_report"
        done < "$LOGS_DIR/build_status.tmp"
    fi

    echo "" >> "$markdown_report"
    echo "**Total Build Time:** ${total_time}s" >> "$markdown_report"

    log_success "Build reports generated:"
    log_info "  JSON: $report_file"
    log_info "  Markdown: $markdown_report"
}

# Show final summary
show_final_summary() {
    local total_time=$(($(date +%s) - BUILD_START_TIME))
    local successful_builds=0
    local failed_builds=0

    log_section "Build Pipeline Summary"

    # Count results and show them
    log_info "Build Results:"
    if [ -f "$LOGS_DIR/build_status.tmp" ]; then
        while IFS=: read -r platform status build_time; do
            local status_icon="❌"
            local status_color="$RED"
            case "$status" in
                SUCCESS)
                    status_icon="✅"
                    status_color="$GREEN"
                    ((successful_builds++))
                    ;;
                BUILDING)
                    status_icon="🔄"
                    status_color="$YELLOW"
                    ;;
                SKIPPED)
                    status_icon="⏭️"
                    status_color="$YELLOW"
                    ;;
                FAILED)
                    status_icon="❌"
                    status_color="$RED"
                    ((failed_builds++))
                    ;;
            esac
            echo -e "  $status_color$status_icon $platform: $status (${build_time}s)$NC"
        done < "$LOGS_DIR/build_status.tmp"
    fi

    echo ""
    log_info "Summary:"
    log_info "  Successful builds: $successful_builds"
    if [ $failed_builds -gt 0 ]; then
        log_error "  Failed builds: $failed_builds"
    fi
    log_info "  Total time: ${total_time}s"

    # Show artifact locations
    if [ $successful_builds -gt 0 ]; then
        log_info "Artifacts location: $ARTIFACTS_DIR"
        echo ""
        echo -e "${BOLD}Usage Examples:${NC}"

        # Check each platform for examples
        if [ -f "$LOGS_DIR/build_status.tmp" ]; then
            if grep -q "docker-linux:SUCCESS" "$LOGS_DIR/build_status.tmp"; then
                echo "  # Extract and run Linux binary:"
                echo "  cd $ARTIFACTS_DIR/linux"
                echo "  ./chunkhound-optimized/chunkhound-optimized --help"
            fi

            if grep -q "macos-intel:SUCCESS\|macos-apple-silicon:SUCCESS" "$LOGS_DIR/build_status.tmp"; then
                echo "  # Extract and run macOS binary:"
                echo "  cd $ARTIFACTS_DIR/macos/intel"  # or apple-silicon
                echo "  tar -xzf chunkhound-macos-intel-*.tar.gz"
                echo "  ./chunkhound-macos-intel/chunkhound-macos-intel --help"
            fi

            if grep -q "macos-universal:SUCCESS" "$LOGS_DIR/build_status.tmp"; then
                echo "  # Extract and run Universal macOS binary:"
                echo "  cd $ARTIFACTS_DIR/macos/universal"
                echo "  tar -xzf chunkhound-macos-universal-*.tar.gz"
                echo "  ./chunkhound-macos-universal/chunkhound-macos-universal --help"
            fi
        fi
    fi

    # Final result
    if [ $failed_builds -eq 0 ]; then
        log_success "🎉 Build pipeline completed successfully!"
        return 0
    else
        log_error "Build pipeline completed with failures"
        return 1
    fi
}

# Main execution function
main() {
    # Parse command line
    parse_arguments "$@"

    # Show header
    log_section "ChunkHound Unified Dual Build Pipeline"
    echo "Building for all supported platforms with unified orchestration"
    echo ""

    # Platform compatibility and prerequisites
    check_platform_compatibility
    check_prerequisites
    setup_build_environment

    # Initialize status tracking
    mkdir -p "$LOGS_DIR"
    > "$LOGS_DIR/build_status.tmp"

    # Execute builds sequentially
    log_info "Starting builds..."

    for platform in $BUILD_PLATFORMS; do
        case $platform in
            docker-linux)
                build_docker_linux || log_warning "Docker Linux build failed"
                ;;
            macos-intel)
                build_macos_arch "x86_64" "intel" || log_warning "macOS Intel build failed"
                ;;
            macos-apple-silicon)
                build_macos_arch "arm64" "apple-silicon" || log_warning "macOS Apple Silicon build failed"
                ;;
            macos-universal)
                build_universal_binary || log_warning "macOS Universal build failed"
                ;;
            *)
                log_warning "Unknown platform: $platform"
                ;;
        esac
    done

    # Post-build tasks
    generate_checksums
    run_validation_tests
    generate_build_report
    show_final_summary
}

# Execute main function
main "$@"
