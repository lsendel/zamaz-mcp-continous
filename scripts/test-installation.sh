#!/bin/bash
# Test script for Claude Remote Client installation

set -e

echo "🧪 Testing Claude Remote Client Installation"
echo "==========================================="

# Create temporary directory for testing
TEST_DIR=$(mktemp -d)
echo "📁 Using test directory: $TEST_DIR"

# Function to cleanup on exit
cleanup() {
    echo "🧹 Cleaning up test directory..."
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# Test 1: Build package
echo ""
echo "📦 Test 1: Building package..."
python setup.py sdist bdist_wheel
echo "✅ Package built successfully"

# Test 2: Install package in virtual environment
echo ""
echo "🐍 Test 2: Installing in virtual environment..."
cd "$TEST_DIR"
python -m venv test-env
source test-env/bin/activate

# Install from wheel
pip install "$OLDPWD/dist/claude_remote_client-"*.whl

echo "✅ Package installed successfully"

# Test 3: Test CLI entry point
echo ""
echo "🖥️  Test 3: Testing CLI entry point..."
claude-remote-client --version
echo "✅ CLI entry point works"

# Test 4: Test module imports
echo ""
echo "📚 Test 4: Testing module imports..."
python -c "
import claude_remote_client
from claude_remote_client import Config, load_config
from claude_remote_client.cli import main
print('✅ All imports successful')
"

# Test 5: Test help command
echo ""
echo "❓ Test 5: Testing help command..."
claude-remote-client --help > /dev/null
echo "✅ Help command works"

# Test 6: Test system check (without actual requirements)
echo ""
echo "🔍 Test 6: Testing system check..."
claude-remote-client --check || echo "⚠️  System check failed (expected without Claude CLI)"

echo ""
echo "🎉 All installation tests passed!"
echo "Package is ready for distribution."