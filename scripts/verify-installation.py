#!/usr/bin/env python3
"""
Installation verification script for Claude Remote Client.

This script verifies that Claude Remote Client is properly installed and configured.
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path


def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_step(step, description):
    """Print a formatted step."""
    print(f"\n{step}. {description}")
    print("-" * 40)


def check_python_version():
    """Check Python version compatibility."""
    print(f"Python version: {sys.version}")
    
    if sys.version_info < (3, 9):
        print("❌ ERROR: Python 3.9+ required")
        return False
    elif sys.version_info >= (3, 11):
        print("✅ Python version is optimal (3.11+)")
    else:
        print("✅ Python version is compatible (3.9+)")
    
    return True


def check_package_installation():
    """Check if the package is properly installed."""
    try:
        import claude_remote_client
        print(f"✅ Package installed: version {claude_remote_client.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Package not installed: {e}")
        return False


def check_module_imports():
    """Check if all required modules can be imported."""
    modules_to_check = [
        'claude_remote_client.cli',
        'claude_remote_client.config',
        'claude_remote_client.models',
        'claude_remote_client.slack_client.client',
        'claude_remote_client.session_manager.session_manager',
        'claude_remote_client.task_queue.queue_manager',
    ]
    
    all_imported = True
    
    for module_name in modules_to_check:
        try:
            importlib.import_module(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            all_imported = False
    
    return all_imported


def check_cli_entry_point():
    """Check if CLI entry point works."""
    try:
        result = subprocess.run(
            ['claude-remote-client', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"✅ CLI entry point works: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ CLI entry point failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ CLI entry point timed out")
        return False
    except FileNotFoundError:
        print("❌ CLI entry point not found in PATH")
        return False
    except Exception as e:
        print(f"❌ CLI entry point error: {e}")
        return False


def check_dependencies():
    """Check if required dependencies are available."""
    required_deps = [
        'slack_sdk',
        'yaml',
        'asyncio',
    ]
    
    optional_deps = [
        'croniter',
        'psutil',
        'aiofiles',
    ]
    
    all_required = True
    
    print("Required dependencies:")
    for dep in required_deps:
        try:
            if dep == 'yaml':
                import yaml
            elif dep == 'asyncio':
                import asyncio
            else:
                importlib.import_module(dep)
            print(f"  ✅ {dep}")
        except ImportError:
            print(f"  ❌ {dep} (REQUIRED)")
            all_required = False
    
    print("\nOptional dependencies:")
    for dep in optional_deps:
        try:
            importlib.import_module(dep)
            print(f"  ✅ {dep}")
        except ImportError:
            print(f"  ⚠️  {dep} (optional - install with pip install claude-remote-client[enhanced])")
    
    return all_required


def check_configuration_directory():
    """Check if configuration directory can be created."""
    config_dir = Path.home() / '.claude-remote-client'
    
    try:
        config_dir.mkdir(exist_ok=True)
        
        # Test write permissions
        test_file = config_dir / '.test_write'
        test_file.write_text('test')
        test_file.unlink()
        
        print(f"✅ Configuration directory accessible: {config_dir}")
        return True
        
    except Exception as e:
        print(f"❌ Configuration directory error: {e}")
        return False


def check_claude_cli():
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(
            ['claude', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"✅ Claude CLI available: {result.stdout.strip()}")
            return True
        else:
            print(f"⚠️  Claude CLI found but may not be working properly")
            print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️  Claude CLI check timed out")
        return False
    except FileNotFoundError:
        print("⚠️  Claude CLI not found in PATH")
        print("   Install from: https://docs.anthropic.com/claude/reference/cli-quickstart")
        return False
    except Exception as e:
        print(f"⚠️  Claude CLI check error: {e}")
        return False


def check_system_resources():
    """Check system resources."""
    try:
        import psutil
        
        # Check memory
        memory = psutil.virtual_memory()
        available_mb = memory.available / (1024 * 1024)
        
        if available_mb > 512:
            print(f"✅ Memory: {available_mb:.0f}MB available")
        else:
            print(f"⚠️  Memory: {available_mb:.0f}MB available (512MB+ recommended)")
        
        # Check disk space
        disk = psutil.disk_usage('/')
        free_gb = disk.free / (1024 * 1024 * 1024)
        
        if free_gb > 1:
            print(f"✅ Disk space: {free_gb:.1f}GB free")
        else:
            print(f"⚠️  Disk space: {free_gb:.1f}GB free (1GB+ recommended)")
        
        return True
        
    except ImportError:
        print("⚠️  psutil not available - install with: pip install psutil")
        return True  # Not critical
    except Exception as e:
        print(f"⚠️  System resource check failed: {e}")
        return True  # Not critical


def run_basic_functionality_test():
    """Run basic functionality test."""
    try:
        # Test configuration loading
        from claude_remote_client.config import Config
        
        # Test model imports
        from claude_remote_client.models import ClaudeSession, QueuedTask
        
        # Test basic object creation
        session = ClaudeSession(
            session_id="test",
            project_path="/tmp",
            project_name="test-project"
        )
        
        print("✅ Basic functionality test passed")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def main():
    """Main verification function."""
    print_header("Claude Remote Client Installation Verification")
    
    all_checks_passed = True
    
    # Check 1: Python version
    print_step(1, "Checking Python version")
    if not check_python_version():
        all_checks_passed = False
    
    # Check 2: Package installation
    print_step(2, "Checking package installation")
    if not check_package_installation():
        all_checks_passed = False
        print("\n❌ CRITICAL: Package not installed. Install with:")
        print("   pip install claude-remote-client")
        return False
    
    # Check 3: Module imports
    print_step(3, "Checking module imports")
    if not check_module_imports():
        all_checks_passed = False
    
    # Check 4: CLI entry point
    print_step(4, "Checking CLI entry point")
    if not check_cli_entry_point():
        all_checks_passed = False
    
    # Check 5: Dependencies
    print_step(5, "Checking dependencies")
    if not check_dependencies():
        all_checks_passed = False
    
    # Check 6: Configuration directory
    print_step(6, "Checking configuration directory")
    if not check_configuration_directory():
        all_checks_passed = False
    
    # Check 7: Claude CLI (optional but recommended)
    print_step(7, "Checking Claude CLI")
    claude_cli_available = check_claude_cli()
    
    # Check 8: System resources
    print_step(8, "Checking system resources")
    check_system_resources()
    
    # Check 9: Basic functionality
    print_step(9, "Running basic functionality test")
    if not run_basic_functionality_test():
        all_checks_passed = False
    
    # Summary
    print_header("Verification Summary")
    
    if all_checks_passed:
        print("🎉 All critical checks passed!")
        print("✅ Claude Remote Client is properly installed and ready to use.")
        
        if not claude_cli_available:
            print("\n⚠️  Note: Claude CLI not found. Install it for full functionality:")
            print("   https://docs.anthropic.com/claude/reference/cli-quickstart")
        
        print("\nNext steps:")
        print("1. Run setup wizard: claude-remote-client --setup")
        print("2. Configure your Slack bot token and projects")
        print("3. Start the bot: claude-remote-client")
        
    else:
        print("❌ Some checks failed!")
        print("Please resolve the issues above before using Claude Remote Client.")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)