#!/usr/bin/env python3
"""Test Claude CLI integration directly."""

import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
PROJECT_PATH = os.getenv("PROJECT_PATH", ".")


def test_claude_cli():
    """Test Claude CLI directly."""
    print("Testing Claude CLI Integration")
    print("=" * 50)
    print(f"Claude Path: {CLAUDE_PATH}")
    print(f"Project Path: {PROJECT_PATH}")
    
    # Test 1: Simple message
    print("\nTest 1: Simple message")
    print("-" * 30)
    try:
        result = subprocess.run(
            [CLAUDE_PATH, '--print', 'Say hello and tell me what project you are working on'],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Success!")
            print(f"Response: {result.stdout[:200]}...")
        else:
            print(f"❌ Failed with code {result.returncode}")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Test 2: List files
    print("\n\nTest 2: List Python files")
    print("-" * 30)
    try:
        result = subprocess.run(
            [CLAUDE_PATH, '--print', 'List the main Python files in this project'],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Success!")
            print(f"Response: {result.stdout[:300]}...")
        else:
            print(f"❌ Failed with code {result.returncode}")
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    test_claude_cli()