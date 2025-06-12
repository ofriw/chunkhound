# ChunkHound Development Makefile
# Makes development dead simple with common tasks

.PHONY: help install install-dev test test-watch lint format clean setup dev build check-deps validate test-examples

# Default target
help: ## Show this help message
	@echo "ChunkHound Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup     # One-time development setup"
	@echo "  make test      # Run tests"
	@echo "  make dev       # Index current directory"
	@echo ""
	@echo "Unified Build System:"
	@echo "  make build-all-platforms   # Build all supported platforms"
	@echo "  make build-all-clean       # Clean build with validation"
	@echo "  make build-macos-only      # Native macOS builds only"
	@echo "  make build-linux-only      # Docker Linux builds only"
	@echo "  make validate-binaries     # Validate built binaries"
	@echo ""
	@echo "Direct build script usage:"
	@echo "  ./scripts/build.sh all     # Build both platforms"
	@echo "  ./scripts/build.sh mac     # Build macOS binary"
	@echo "  ./scripts/build.sh ubuntu  # Build Ubuntu binary"
	@echo ""
	@echo "Development commands:"
	@echo "  ./scripts/dev-setup.sh     # Index + start MCP server"
	@echo "  ./scripts/mcp-server.sh    # Start MCP server only"

setup: ## One-time development setup (syncs deps with uv)
	@echo "🔧 Setting up ChunkHound development environment..."
	uv sync
	@echo "✅ Setup complete! Use 'uv run' commands or activate with: source .venv/bin/activate"

install: ## Install package in development mode
	uv sync

install-dev: ## Install with development dependencies
	uv sync --group dev

test: ## Run all tests
	uv run pytest -v

test-watch: ## Run tests in watch mode
	uv run pytest -f

test-api: ## Run API integration tests
	uv run python test_api.py
	uv run python test_api_simple.py

lint: ## Run linting (ruff + mypy)
	uv run ruff check chunkhound/
	uv run mypy chunkhound/

format: ## Format code with black and ruff
	uv run black chunkhound/ test_*.py
	uv run ruff check --fix chunkhound/

check-deps: ## Check for dependency issues
	uv tree
	@echo "Dependencies look good!"

dev: ## Index current directory for development
	@echo "🚀 Starting ChunkHound development indexing..."
	@echo "   Processing current directory..."
	uv run chunkhound run . --verbose

health: ## Check system health
	@echo "🏥 System Health Check"
	@echo "Python: $$(uv run python --version)"
	@echo "ChunkHound: $$(uv run chunkhound --version)"
	@echo "MCP server available via 'uv run chunkhound mcp'"

validate: ## Run end-to-end validation tests
	@echo "🧪 Running comprehensive validation..."
	./scripts/validate.sh

test-examples: ## Test all README examples to ensure they work
	@echo "📖 Testing README examples..."
	./scripts/test-examples.sh

build: ## Build distribution packages
	uv build

build-standalone: ## Build standalone executable with PyInstaller
	@echo "🚀 Building standalone executable..."
	./scripts/build.sh mac

build-all-platforms: ## Build for all supported platforms (Docker + Native)
	@echo "🚀 Building for all platforms with unified orchestration..."
	./scripts/build.sh all

build-all-clean: ## Clean build for all platforms with validation
	@echo "🚀 Clean build for all platforms with validation..."
	./scripts/build.sh all --clean --validate

build-macos-only: ## Build native macOS binaries only (macOS host only)
	@echo "🍎 Building macOS native binaries only..."
	./scripts/build.sh mac

build-linux-only: ## Build Docker Linux binary only
	@echo "🐧 Building Docker Linux binary only..."
	./scripts/build.sh ubuntu

prepare-release: ## Prepare release with documentation, builds, and packaging
	@echo "🎯 Preparing release..."
	./scripts/prepare_release.sh

clean: ## Clean up temporary files
	rm -rf build/
	rm -rf dist/
	rm -rf release/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-db: ## Clean database cache
	rm -rf ~/.cache/chunkhound/
	@echo "🗑️  Database cache cleared"

install-system: ## Install globally on system
	uv pip install .

# Advanced targets
requirements: ## Generate requirements.txt from uv.lock
	uv export --format requirements-txt --output-file requirements.txt

docker-build: ## Build Docker image
	docker build -t chunkhound:latest .

docker-run: ## Run in Docker container
	docker run -p 7474:7474 -v "$(PWD):/workspace" chunkhound:latest

docker-build-all: ## Build cross-platform binaries with Docker
	@echo "🐳 Building cross-platform binaries with Docker..."
	./scripts/build.sh ubuntu

docker-build-linux: ## Build Linux binary only
	@echo "🐧 Building Linux binary with Docker..."
	./scripts/build.sh ubuntu



docker-clean: ## Clean Docker images and volumes
	@echo "🧹 Cleaning Docker artifacts..."
	docker-compose -f docker-compose.build.yml down -v --remove-orphans || true
	docker images chunkhound:* -q | xargs -r docker rmi -f || true
	docker system prune -f
	rm -rf dist/docker-artifacts/
	rm -rf .docker-cache/

validate-binaries: ## Validate cross-platform binaries
	@echo "🧪 Validating cross-platform binaries..."
	./scripts/build.sh all --validate

cross-platform-ci: ## Run complete cross-platform CI pipeline locally
	@echo "🚀 Running complete cross-platform CI pipeline..."
	make clean
	make build-all-clean

# Development quality checks
check: lint test ## Run all quality checks

pre-commit: format lint test ## Pre-commit hook (format, lint, test)

ci: ## Continuous integration checks
	uv sync
	make check
	make test-examples
