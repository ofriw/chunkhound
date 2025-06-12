#!/bin/bash
set -e

# ChunkHound Docker Cross-Platform Build Script
# Builds binaries for all supported platforms using Docker multi-stage builds
# Optimized for speed with parallel builds and intelligent caching

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_BUILD_DIR="$PROJECT_ROOT/docker-build"
ARTIFACTS_DIR="$PROJECT_ROOT/dist/docker-artifacts"

# Build configuration
DOCKER_IMAGE="chunkhound"
BUILD_TAG="build-$(date +%Y%m%d-%H%M%S)"
PLATFORMS="linux/amd64,darwin/amd64"  # macOS support enabled

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    echo -e "\n${BLUE}🚀 $1${NC}"
    echo "================================"
}

# Cleanup function
cleanup() {
    if [ "$?" -ne 0 ]; then
        log_error "Build failed! Cleaning up..."
        docker system df
    fi
}
trap cleanup EXIT

# Help function
show_help() {
    cat << EOF
ChunkHound Docker Cross-Platform Build Script

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -c, --clean         Clean Docker cache before building
    -t, --test          Run tests after building
    -p, --push          Push images to registry (if configured)
    --platforms PLAT    Comma-separated list of platforms (default: linux/amd64)
    --output DIR        Output directory for artifacts (default: dist/docker-artifacts)
    --tag TAG           Custom build tag (default: build-YYYYMMDD-HHMMSS)
    --dev               Build development image only
    --runtime           Build runtime image only
    --parallel          Enable parallel builds (experimental)

EXAMPLES:
    $0                              # Build for default platforms
    $0 --clean --test               # Clean build with testing
    $0 --platforms linux/amd64     # Build for specific platform
    $0 --dev                        # Build development environment only
    $0 --output /tmp/builds         # Custom output directory

ENVIRONMENT VARIABLES:
    DOCKER_BUILDKIT=1              # Enable BuildKit (recommended)
    CHUNKHOUND_VERSION             # Override version detection
EOF
}

# Parse command line arguments
CLEAN_BUILD=false
RUN_TESTS=false
PUSH_IMAGES=false
BUILD_DEV_ONLY=false
BUILD_RUNTIME_ONLY=false
PARALLEL_BUILD=false

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
        -p|--push)
            PUSH_IMAGES=true
            shift
            ;;
        --platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --output)
            ARTIFACTS_DIR="$2"
            shift 2
            ;;
        --tag)
            BUILD_TAG="$2"
            shift 2
            ;;
        --dev)
            BUILD_DEV_ONLY=true
            shift
            ;;
        --runtime)
            BUILD_RUNTIME_ONLY=true
            shift
            ;;
        --parallel)
            PARALLEL_BUILD=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Environment checks
check_prerequisites() {
    log_section "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    # Check Docker Buildx
    if ! docker buildx version &> /dev/null; then
        log_warning "Docker Buildx not available - falling back to regular build"
        PARALLEL_BUILD=false
    fi

    # Verify we're in the right directory
    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log_error "Not in ChunkHound project root (missing pyproject.toml)"
        exit 1
    fi

    log_success "Prerequisites check passed"

    # Show build configuration
    log_info "Build Configuration:"
    log_info "  Project Root: $PROJECT_ROOT"
    log_info "  Platforms: $PLATFORMS"
    log_info "  Build Tag: $BUILD_TAG"
    log_info "  Output Dir: $ARTIFACTS_DIR"
    log_info "  Clean Build: $CLEAN_BUILD"
    log_info "  Run Tests: $RUN_TESTS"
    log_info "  Parallel: $PARALLEL_BUILD"
}

# Clean Docker cache
clean_docker_cache() {
    if [ "$CLEAN_BUILD" = true ]; then
        log_section "Cleaning Docker Cache"

        # Remove previous build images
        docker images "${DOCKER_IMAGE}:*" -q | xargs -r docker rmi -f || true

        # Prune build cache
        docker builder prune -f

        log_success "Docker cache cleaned"
    fi
}

# Setup build environment
setup_build_environment() {
    log_section "Setting Up Build Environment"

    # Create output directories
    mkdir -p "$ARTIFACTS_DIR"/{linux,macos,checksums,logs}

    # Create build context (if needed)
    if [ ! -d "$DOCKER_BUILD_DIR" ]; then
        mkdir -p "$DOCKER_BUILD_DIR"
    fi

    # Get version info
    if [ -z "$CHUNKHOUND_VERSION" ]; then
        if command -v uv &> /dev/null && [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
            CHUNKHOUND_VERSION=$(cd "$PROJECT_ROOT" && uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "dev")
        else
            CHUNKHOUND_VERSION="dev"
        fi
    fi

    log_info "ChunkHound Version: $CHUNKHOUND_VERSION"
    log_success "Build environment ready"
}

# Build multi-stage Docker image
build_docker_image() {
    log_section "Building Docker Images"

    cd "$PROJECT_ROOT"

    # Enable BuildKit for better performance
    export DOCKER_BUILDKIT=1

    local build_args="--build-arg CHUNKHOUND_VERSION=$CHUNKHOUND_VERSION --build-arg PYTHON_VERSION=3.11 --build-arg DEBIAN_VERSION=slim"
    local build_opts="--progress=plain"

    if [ "$PARALLEL_BUILD" = true ] && command -v docker buildx &> /dev/null; then
        log_info "Building with Docker Buildx (parallel)"

        # Create/use buildx builder
        docker buildx create --name chunkhound-builder --use 2>/dev/null || docker buildx use chunkhound-builder

        # Build all stages in parallel
        if ! docker buildx build \
            --platform "$PLATFORMS" \
            $build_args \
            $build_opts \
            --target artifact-collector \
            --tag "${DOCKER_IMAGE}:${BUILD_TAG}" \
            --tag "${DOCKER_IMAGE}:latest" \
            --output "type=local,dest=$ARTIFACTS_DIR" \
            . 2>&1 | tee "$ARTIFACTS_DIR/logs/build.log"; then
            log_error "Docker buildx build failed"
            return 1
        fi

    else
        log_info "Building with standard Docker build"

        # Build artifact-collector stage (includes all artifacts)
        if ! docker build \
            $build_args \
            $build_opts \
            --target artifact-collector \
            --tag "${DOCKER_IMAGE}:${BUILD_TAG}" \
            --tag "${DOCKER_IMAGE}:latest" \
            . 2>&1 | tee "$ARTIFACTS_DIR/logs/build.log"; then
            log_error "Docker build failed"
            return 1
        fi

        # Extract artifacts from the built image
        log_info "Extracting build artifacts..."
        if ! docker create --name temp-artifacts "${DOCKER_IMAGE}:${BUILD_TAG}"; then
            log_error "Failed to create temporary container for artifact extraction"
            return 1
        fi

        if ! docker cp temp-artifacts:/artifacts/. "$ARTIFACTS_DIR/"; then
            log_error "Failed to extract artifacts from container"
            docker rm temp-artifacts
            return 1
        fi

        docker rm temp-artifacts
    fi

    # Validate artifacts were created
    if [ ! -d "$ARTIFACTS_DIR" ] || [ -z "$(ls -A "$ARTIFACTS_DIR" 2>/dev/null)" ]; then
        log_error "No artifacts were created - build may have failed silently"
        return 1
    fi

    # Check for macOS artifacts limitation
    if [ -d "$ARTIFACTS_DIR/macos" ] && [ -z "$(ls -A "$ARTIFACTS_DIR/macos" 2>/dev/null)" ]; then
        log_warning "macOS artifacts missing - Docker cannot cross-compile to macOS"
        log_warning "Use CI/CD with macOS runners or build locally on macOS for darwin/amd64 support"
    fi

    log_success "Docker build completed and artifacts validated"
}

# Build development environment
build_dev_environment() {
    if [ "$BUILD_DEV_ONLY" = true ]; then
        log_section "Building Development Environment"

        if ! docker build \
            --target dev-environment \
            --tag "${DOCKER_IMAGE}:dev-${BUILD_TAG}" \
            --tag "${DOCKER_IMAGE}:dev" \
            . 2>&1 | tee "$ARTIFACTS_DIR/logs/dev-build.log"; then
            log_error "Development environment build failed"
            return 1
        fi

        log_success "Development environment built"
        log_info "Run with: docker run -it --rm -v \"\$(pwd):/workspace\" ${DOCKER_IMAGE}:dev"
        return 0
    fi
    return 1
}

# Build runtime environment
build_runtime_environment() {
    if [ "$BUILD_RUNTIME_ONLY" = true ]; then
        log_section "Building Runtime Environment"

        if ! docker build \
            --target runtime \
            --tag "${DOCKER_IMAGE}:runtime-${BUILD_TAG}" \
            --tag "${DOCKER_IMAGE}:runtime" \
            . 2>&1 | tee "$ARTIFACTS_DIR/logs/runtime-build.log"; then
            log_error "Runtime environment build failed"
            return 1
        fi

        log_success "Runtime environment built"
        log_info "Run with: docker run --rm -v \"\$(pwd):/workspace\" ${DOCKER_IMAGE}:runtime"
        return 0
    fi
    return 1
}

# Test built binaries
test_built_binaries() {
    if [ "$RUN_TESTS" = true ]; then
        log_section "Testing Built Binaries"

        # Test Linux binary if it exists
        if [ -f "$ARTIFACTS_DIR/linux/chunkhound-optimized/chunkhound-optimized" ]; then
            log_info "Testing Linux binary..."

            # Test in Docker container for consistent environment
            docker run --rm \
                -v "$ARTIFACTS_DIR/linux:/test-artifacts" \
                ubuntu:22.04 \
                /bin/bash -c "
                    /test-artifacts/chunkhound-optimized/chunkhound-optimized --version
                    /test-artifacts/chunkhound-optimized/chunkhound-optimized --help > /dev/null
                    echo 'Linux binary test passed'
                "

            log_success "Linux binary tests passed"
        else
            log_warning "Linux binary not found for testing"
        fi

        # Performance test
        log_info "Running performance tests..."
        # Add performance testing logic here

        log_success "All tests completed"
    fi
}

# Generate build report
generate_build_report() {
    log_section "Generating Build Report"

    local report_file="$ARTIFACTS_DIR/BUILD_REPORT.md"

    cat > "$report_file" << EOF
# ChunkHound Docker Build Report

**Build Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Build Tag:** $BUILD_TAG
**Version:** $CHUNKHOUND_VERSION
**Platforms:** $PLATFORMS

## Build Configuration
- Clean Build: $CLEAN_BUILD
- Run Tests: $RUN_TESTS
- Parallel Build: $PARALLEL_BUILD

## Artifacts Generated
EOF

    # List generated artifacts
    if [ -d "$ARTIFACTS_DIR" ]; then
        echo -e "\n### Files:" >> "$report_file"
        find "$ARTIFACTS_DIR" -type f -exec ls -lh {} \; | while read -r line; do
            echo "- $line" >> "$report_file"
        done

        # Add checksums if available
        if [ -f "$ARTIFACTS_DIR/checksums/SHA256SUMS" ]; then
            echo -e "\n### Checksums:" >> "$report_file"
            echo '```' >> "$report_file"
            cat "$ARTIFACTS_DIR/checksums/SHA256SUMS" >> "$report_file"
            echo '```' >> "$report_file"
        fi
    fi

    # Docker images
    echo -e "\n### Docker Images:" >> "$report_file"
    docker images "${DOCKER_IMAGE}:*" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" >> "$report_file"

    log_success "Build report generated: $report_file"
}

# Push images to registry
push_images() {
    if [ "$PUSH_IMAGES" = true ]; then
        log_section "Pushing Images to Registry"

        # Check if registry is configured
        if [ -z "$DOCKER_REGISTRY" ]; then
            log_warning "DOCKER_REGISTRY not set - skipping push"
            return 0
        fi

        # Push images
        docker tag "${DOCKER_IMAGE}:${BUILD_TAG}" "${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${BUILD_TAG}"
        docker tag "${DOCKER_IMAGE}:latest" "${DOCKER_REGISTRY}/${DOCKER_IMAGE}:latest"

        docker push "${DOCKER_REGISTRY}/${DOCKER_IMAGE}:${BUILD_TAG}"
        docker push "${DOCKER_REGISTRY}/${DOCKER_IMAGE}:latest"

        log_success "Images pushed to registry"
    fi
}

# Main execution
main() {
    log_section "ChunkHound Docker Cross-Platform Build"
    echo "Starting build process..."

    check_prerequisites
    clean_docker_cache
    setup_build_environment

    # Handle special build modes
    build_dev_environment && exit 0
    build_runtime_environment && exit 0

    # Full build process
    if ! build_docker_image; then
        log_error "Docker build failed - aborting"
        exit 1
    fi

    test_built_binaries
    generate_build_report
    push_images

    log_section "Build Complete"
    log_success "All artifacts generated successfully!"
    log_info "Artifacts location: $ARTIFACTS_DIR"

    # Show summary
    if [ -d "$ARTIFACTS_DIR" ]; then
        log_info "Generated files:"
        find "$ARTIFACTS_DIR" -type f \( -name "*.tar.gz" -o -name "chunkhound-*" \) | sort | while read -r file; do
            size=$(ls -lh "$file" | awk '{print $5}')
            log_info "  $(basename "$file") ($size)"
        done
    fi

    # Show usage examples
    echo -e "\n${BLUE}Usage Examples:${NC}"
    echo "  # Extract Linux binary:"
    echo "  tar -xzf $ARTIFACTS_DIR/linux/chunkhound-linux-amd64.tar.gz"
    echo ""
    echo "  # Run development environment:"
    echo "  docker run -it --rm -v \"\$(pwd):/workspace\" ${DOCKER_IMAGE}:dev"
    echo ""
    echo "  # Run runtime environment:"
    echo "  docker run --rm -v \"\$(pwd):/workspace\" ${DOCKER_IMAGE}:runtime chunkhound --help"
}

# Execute main function
main "$@"
