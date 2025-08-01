# Makefile for Slack-Claude Integration
# Easy commands to manage the integration

.PHONY: help install test start demo interactive diagnose clean

# Default target - show help
help:
	@echo "🤖 Slack-Claude Integration Commands"
	@echo "===================================="
	@echo "make install      - Install required dependencies"
	@echo "make test         - Test Slack and Claude connections"
	@echo "make start        - Start the Slack-Claude bridge (polling mode)"
	@echo "make demo         - Run automated demo of bidirectional communication"
	@echo "make interactive  - Start interactive mode (type messages in terminal)"
	@echo "make diagnose     - Diagnose Slack configuration issues"
	@echo "make clean        - Clean up cache and temporary files"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make install"
	@echo "  2. make test"
	@echo "  3. make demo (or make interactive)"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip install slack-sdk python-dotenv pyyaml aiofiles
	@echo "✅ Dependencies installed!"

# Test connections
test:
	@echo "🧪 Testing Slack and Claude connections..."
	python simple_slack_claude_test.py

# Start the bridge (polling mode - requires groups:read scope)
start:
	@echo "🚀 Starting Slack-Claude bridge..."
	@echo "⚠️  Note: This requires 'groups:read' scope for private channels"
	python slack_claude_bridge.py

# Run demo
demo:
	@echo "🎭 Running bidirectional communication demo..."
	python test_bidirectional_communication.py

# Interactive mode (works without reading channel history)
interactive:
	@echo "💬 Starting interactive mode..."
	@echo "Type messages here and they'll be sent to Claude via Slack"
	@echo ""
	echo "1" | python slack_claude_interactive.py

# Auto-demo mode
auto-demo:
	@echo "🤖 Running automated demo..."
	echo "2" | python slack_claude_interactive.py

# Diagnose Slack issues
diagnose:
	@echo "🔍 Diagnosing Slack configuration..."
	python diagnose_slack_issue.py

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned!"

# Quick start - install and run demo
quickstart: install test demo

# Development mode - run with auto-restart on changes
dev:
	@echo "🔄 Starting in development mode..."
	@echo "Installing watchdog for auto-restart..."
	pip install watchdog
	watchmedo auto-restart -d . -p "*.py" --ignore-patterns="*/__pycache__/*" -- python slack_claude_interactive.py