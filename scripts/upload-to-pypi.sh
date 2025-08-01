#!/bin/bash
# Script to build and upload Claude Remote Client to PyPI

set -e

echo "🚀 Building and Uploading Claude Remote Client to PyPI"
echo "====================================================="

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo "❌ Error: setup.py not found. Please run this script from the project root."
    exit 1
fi

# Check if required tools are installed
if ! command -v twine &> /dev/null; then
    echo "📦 Installing twine..."
    pip install twine
fi

if ! command -v build &> /dev/null; then
    echo "📦 Installing build..."
    pip install build
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Run tests first
echo "🧪 Running tests..."
python -m pytest tests/ -v

# Check code quality
echo "🔍 Checking code quality..."
python -m black --check claude_remote_client tests
python -m flake8 claude_remote_client tests
python -m mypy claude_remote_client

# Build the package
echo "📦 Building package..."
python -m build

# Check the built package
echo "🔍 Checking built package..."
python -m twine check dist/*

# List built files
echo "📋 Built files:"
ls -la dist/

# Ask for confirmation before uploading
echo ""
echo "🤔 Ready to upload to PyPI?"
echo "Files to upload:"
ls -1 dist/

read -p "Continue with upload? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Upload cancelled."
    exit 1
fi

# Upload to PyPI
echo "🚀 Uploading to PyPI..."
python -m twine upload dist/*

echo ""
echo "🎉 Successfully uploaded to PyPI!"
echo "📦 Package should be available at: https://pypi.org/project/claude-remote-client/"
echo ""
echo "To install the uploaded package:"
echo "  pip install claude-remote-client"
echo ""
echo "To install with enhanced features:"
echo "  pip install claude-remote-client[enhanced]"