# Makefile for Claude Remote Client
# Comprehensive commands for development, testing, and deployment

.PHONY: help install test start demo interactive diagnose clean
.PHONY: dev test-unit test-integration test-all coverage
.PHONY: lint format type-check quality
.PHONY: docs serve-docs
.PHONY: docker-build docker-run docker-clean
.PHONY: setup configure validate

# Variables
PYTHON := python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
SRC_DIR := claude_remote_client
TEST_DIR := tests
DOC_DIR := docs

# Default target - show help
help:
	@echo "🤖 Claude Remote Client - Development Commands"
	@echo "============================================="
	@echo ""
	@echo "📦 Setup & Installation:"
	@echo "  make install        - Install all dependencies"
	@echo "  make install-dev    - Install with dev dependencies"
	@echo "  make setup          - Complete project setup"
	@echo "  make configure      - Configure Slack and Claude settings"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests"
	@echo "  make coverage       - Run tests with coverage report"
	@echo "  make test-slack     - Test Slack connection"
	@echo "  make test-claude    - Test Claude CLI connection"
	@echo ""
	@echo "🔍 Code Quality:"
	@echo "  make lint           - Run all linters"
	@echo "  make format         - Auto-format code"
	@echo "  make type-check     - Run type checking"
	@echo "  make quality        - Run all quality checks"
	@echo ""
	@echo "🚀 Running:"
	@echo "  make start          - Start Slack-Claude bridge"
	@echo "  make interactive    - Start interactive mode"
	@echo "  make demo           - Run demonstration"
	@echo "  make diagnose       - Diagnose configuration issues"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make docs           - Build documentation"
	@echo "  make serve-docs     - Serve docs locally"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make clean-all      - Deep clean (including .venv)"
	@echo ""
	@echo "🏃 Quick Start:"
	@echo "  1. make setup"
	@echo "  2. make test"
	@echo "  3. make start"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	@echo "✅ Dependencies installed!"

install-dev: install
	@echo "📦 Installing development dependencies..."
	$(PIP) install pytest pytest-asyncio pytest-cov pytest-mock
	$(PIP) install black flake8 mypy isort bandit pylint
	$(PIP) install pre-commit
	pre-commit install
	@echo "✅ Development environment ready!"

# Complete setup
setup: install-dev
	@echo "🔧 Setting up Claude Remote Client..."
	@if [ ! -f ~/.claude-remote-client/config.yaml ]; then \
		mkdir -p ~/.claude-remote-client; \
		cp claude-remote-client.example.yaml ~/.claude-remote-client/config.yaml; \
		echo "📝 Created config file at ~/.claude-remote-client/config.yaml"; \
		echo "⚠️  Please edit the config file with your settings"; \
	fi
	@echo "✅ Setup complete!"

# Configure settings
configure:
	@echo "⚙️  Running configuration wizard..."
	$(PYTHON) -m claude_remote_client.cli configure

# Testing commands
test: test-unit test-integration
	@echo "✅ All tests completed!"

test-unit:
	@echo "🧪 Running unit tests..."
	$(PYTEST) $(TEST_DIR) -v -m "not integration and not performance" --tb=short

test-integration:
	@echo "🧪 Running integration tests..."
	$(PYTEST) $(TEST_DIR) -v -m "integration" --tb=short || true

test-all:
	@echo "🧪 Running all tests..."
	$(PYTEST) $(TEST_DIR) -v --tb=short

coverage:
	@echo "📊 Running tests with coverage..."
	$(PYTEST) $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing
	@echo "📈 Coverage report generated in htmlcov/index.html"

test-slack:
	@echo "🧪 Testing Slack connection..."
	$(PYTHON) test_slack_connection.py

test-claude:
	@echo "🧪 Testing Claude CLI..."
	$(PYTHON) test_claude_direct.py

# Code quality commands
lint:
	@echo "🔍 Running linters..."
	@echo "Running flake8..."
	@flake8 $(SRC_DIR) $(TEST_DIR) || true
	@echo "Running pylint..."
	@pylint $(SRC_DIR) --disable=C0111,R0903,R0801 || true
	@echo "Running bandit..."
	@bandit -r $(SRC_DIR) -ll || true

format:
	@echo "✨ Formatting code..."
	@black $(SRC_DIR) $(TEST_DIR)
	@isort $(SRC_DIR) $(TEST_DIR)
	@echo "✅ Code formatted!"

type-check:
	@echo "🔍 Running type checker..."
	@mypy $(SRC_DIR) --ignore-missing-imports

quality: lint type-check
	@echo "✅ Quality checks completed!"

# Running commands
start:
	@echo "🚀 Starting Claude Remote Client..."
	$(PYTHON) -m claude_remote_client start

# Demo and interactive modes
demo:
	@echo "🎭 Running demonstration..."
	$(PYTHON) demo_slack_claude_integration.py

interactive:
	@echo "💬 Starting interactive mode..."
	$(PYTHON) -m claude_remote_client interactive

# Documentation
docs:
	@echo "📚 Building documentation..."
	@if [ -d "$(DOC_DIR)" ]; then \
		sphinx-build -b html $(DOC_DIR) $(DOC_DIR)/_build/html; \
		echo "✅ Documentation built in $(DOC_DIR)/_build/html"; \
	else \
		echo "⚠️  Documentation directory not found"; \
	fi

serve-docs: docs
	@echo "🌐 Serving documentation at http://localhost:8000"
	$(PYTHON) -m http.server 8000 -d $(DOC_DIR)/_build/html

# Diagnostic and validation
diagnose:
	@echo "🔍 Running diagnostics..."
	$(PYTHON) -m claude_remote_client diagnose

validate:
	@echo "✓ Validating configuration..."
	$(PYTHON) -m claude_remote_client validate

# Cleanup commands
clean:
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info 2>/dev/null || true
	@echo "✅ Cleaned!"

clean-all: clean
	@echo "🧹 Deep cleaning..."
	@rm -rf .venv venv env 2>/dev/null || true
	@echo "✅ Deep clean complete!"

# Development shortcuts
dev: install-dev
	@echo "🔄 Starting in development mode..."
	$(PYTHON) -m claude_remote_client start --dev

# Quick commands
quick-test: test-unit
	@echo "✅ Quick tests completed!"

quick-check: format lint
	@echo "✅ Quick checks completed!"

# CI/CD helpers
ci-test:
	$(PYTEST) $(TEST_DIR) -v --tb=short --cov=$(SRC_DIR) --cov-report=xml

ci-lint:
	flake8 $(SRC_DIR) $(TEST_DIR) --max-line-length=120
	black --check $(SRC_DIR) $(TEST_DIR)
	isort --check-only $(SRC_DIR) $(TEST_DIR)
	mypy $(SRC_DIR) --ignore-missing-imports