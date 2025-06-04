# ChunkHound Development Makefile
# Makes development dead simple with common tasks

.PHONY: help install install-dev test test-watch lint format clean setup dev-server build check-deps health validate test-examples

# Default target
help: ## Show this help message
	@echo "ChunkHound Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup     # One-time development setup"
	@echo "  make test      # Run tests"
	@echo "  make dev       # Start development server"

setup: ## One-time development setup (creates venv, installs deps)
	@echo "🔧 Setting up ChunkHound development environment..."
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -e ".[dev]"
	@echo "✅ Setup complete! Activate with: source venv/bin/activate"

install: ## Install package in development mode
	pip install -e .

install-dev: ## Install with development dependencies
	pip install -e ".[dev]"

test: ## Run all tests
	python -m pytest -v

test-watch: ## Run tests in watch mode
	python -m pytest -f

test-api: ## Run API integration tests
	python test_api.py
	python test_api_simple.py

lint: ## Run linting (ruff + mypy)
	ruff check chunkhound/
	mypy chunkhound/

format: ## Format code with black and ruff
	black chunkhound/ test_*.py
	ruff check --fix chunkhound/

check-deps: ## Check for dependency issues
	pip check
	@echo "Dependencies look good!"

dev: dev-server ## Alias for dev-server

dev-server: ## Start development server with file watching
	@echo "🚀 Starting ChunkHound development server..."
	@echo "   Indexing current directory..."
	chunkhound run . --verbose

server: ## Start API server only (no indexing)
	@echo "🌐 Starting ChunkHound API server..."
	chunkhound server

health: ## Check system health
	@echo "🏥 ChunkHound Health Check"
	@echo "Python: $$(python --version)"
	@echo "ChunkHound: $$(chunkhound --version)"
	@curl -s http://localhost:7474/health 2>/dev/null || echo "Server not running (start with 'make dev')"

validate: ## Run end-to-end validation tests
	@echo "🧪 Running comprehensive validation..."
	./scripts/validate.sh

test-examples: ## Test all README examples to ensure they work
	@echo "📖 Testing README examples..."
	./scripts/test-examples.sh

build: ## Build distribution packages
	python -m build

clean: ## Clean up temporary files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-db: ## Clean database cache
	rm -rf ~/.cache/chunkhound/
	@echo "🗑️  Database cache cleared"

install-system: ## Install globally on system
	pip install .

# Advanced targets
requirements: ## Generate requirements.txt from pyproject.toml
	pip-compile pyproject.toml --output-file requirements.txt --strip-extras

docker-build: ## Build Docker image
	docker build -t chunkhound:latest .

docker-run: ## Run in Docker container
	docker run -p 7474:7474 -v "$(PWD):/workspace" chunkhound:latest

# Development quality checks
check: lint test ## Run all quality checks

pre-commit: format lint test ## Pre-commit hook (format, lint, test)

ci: ## Continuous integration checks
	pip install -e ".[dev]"
	make check
	make test-examples