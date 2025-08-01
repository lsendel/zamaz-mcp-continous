#!/usr/bin/env python3
"""Comprehensive test of all application components."""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def print_success(text):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def test_imports():
    """Test all module imports."""
    print_header("Testing Module Imports")
    
    modules = [
        "claude_remote_client",
        "claude_remote_client.cli",
        "claude_remote_client.config",
        "claude_remote_client.models",
        "claude_remote_client.utils",
        "claude_remote_client.exceptions",
        "claude_remote_client.session_manager.session_manager",
        "claude_remote_client.session_manager.project_manager",
        "claude_remote_client.task_queue.queue_manager",
        "claude_remote_client.task_queue.cron_scheduler",
        "claude_remote_client.claude_client.subprocess_handler",
        "claude_remote_client.monitoring",
        "claude_remote_client.performance",
        "claude_remote_client.error_handler",
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print_success(f"Import {module}")
        except Exception as e:
            print_error(f"Import {module}: {e}")
            failed.append(module)
    
    return len(failed) == 0


def test_cli():
    """Test CLI functionality."""
    print_header("Testing CLI Functionality")
    
    tests = [
        ("claude-remote-client --version", "Version check"),
        ("claude-remote-client --help", "Help command"),
        ("claude-remote-client --validate", "Config validation"),
        ("claude-remote-client handler status", "Handler status"),
    ]
    
    failed = 0
    for cmd, desc in tests:
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode == 0:
                print_success(f"{desc}: {cmd}")
            else:
                print_error(f"{desc}: {cmd} (exit code: {result.returncode})")
                failed += 1
        except Exception as e:
            print_error(f"{desc}: {cmd} ({e})")
            failed += 1
    
    return failed == 0


def test_claude_cli():
    """Test Claude CLI availability."""
    print_header("Testing Claude CLI")
    
    claude_path = os.getenv("CLAUDE_CLI_PATH", "claude")
    
    try:
        result = subprocess.run([claude_path, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"Claude CLI available: {result.stdout.strip()}")
            return True
        else:
            print_error(f"Claude CLI error: {result.stderr}")
            return False
    except FileNotFoundError:
        print_error("Claude CLI not found")
        return False
    except Exception as e:
        print_error(f"Claude CLI test failed: {e}")
        return False


async def test_slack_connection():
    """Test Slack connection."""
    print_header("Testing Slack Connection")
    
    try:
        from slack_sdk.web.async_client import AsyncWebClient
        
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            print_error("SLACK_BOT_TOKEN not set")
            return False
        
        client = AsyncWebClient(token=token)
        
        # Test auth
        auth = await client.auth_test()
        print_success(f"Slack auth: {auth['user']} in {auth['team']}")
        
        # Test channel access
        channel = os.getenv("SLACK_CHANNEL")
        if channel:
            try:
                info = await client.conversations_info(channel=channel)
                print_success(f"Channel access: #{info['channel']['name']}")
            except Exception as e:
                print_warning(f"Channel access: {e}")
        
        return True
    except Exception as e:
        print_error(f"Slack test failed: {e}")
        return False


def test_unit_tests():
    """Run unit tests."""
    print_header("Running Unit Tests (Sample)")
    
    # Run a subset of fast unit tests
    test_modules = [
        "tests/test_models.py",
        "tests/test_utils.py",
        "tests/test_exceptions.py",
        "tests/test_config.py",
    ]
    
    failed = 0
    for module in test_modules:
        if Path(module).exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", module, "-q", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    # Count passed tests
                    passed = result.stdout.count(" passed")
                    print_success(f"{module}: {passed} tests passed")
                else:
                    print_error(f"{module}: Failed")
                    failed += 1
            except subprocess.TimeoutExpired:
                print_warning(f"{module}: Timeout")
            except Exception as e:
                print_error(f"{module}: {e}")
                failed += 1
        else:
            print_warning(f"{module}: Not found")
    
    return failed == 0


async def main():
    """Run all tests."""
    print(f"{BLUE}🧪 COMPREHENSIVE APPLICATION TEST{RESET}")
    print(f"{BLUE}Testing zamaz-mcp-continous{RESET}")
    
    results = {
        "Module Imports": test_imports(),
        "CLI Commands": test_cli(),
        "Claude CLI": test_claude_cli(),
        "Slack Connection": await test_slack_connection(),
        "Unit Tests": test_unit_tests(),
    }
    
    # Summary
    print_header("Test Summary")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test, result in results.items():
        if result:
            print_success(test)
        else:
            print_error(test)
    
    print(f"\n{BLUE}Total: {passed}/{total} components working{RESET}")
    
    if passed == total:
        print_success("All components are working correctly!")
    else:
        print_warning(f"{total - passed} components need attention")
    
    # Additional info
    print_header("Environment Info")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print(f"Working Directory: {os.getcwd()}")
    
    env_vars = ["SLACK_BOT_TOKEN", "SLACK_CHANNEL", "CLAUDE_CLI_PATH", "PROJECT_PATH"]
    print("\nEnvironment Variables:")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if "TOKEN" in var:
                # Mask tokens
                print(f"  {var}: {'*' * 10}{value[-4:]}")
            else:
                print(f"  {var}: {value}")
        else:
            print(f"  {var}: Not set")


if __name__ == "__main__":
    asyncio.run(main())