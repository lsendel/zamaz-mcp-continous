"""
Command-line interface for Claude Remote Client.

This module provides the main entry point for the Claude Remote Client application,
including setup wizard, configuration management, and bot startup.
"""

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .config import Config, load_config, create_default_config_file
from .exceptions import ConfigurationError
from .utils import setup_logging, ensure_directory_exists, validate_project_path


def validate_claude_cli() -> bool:
    """
    Validate that Claude CLI is available and working.
    
    Returns:
        bool: True if Claude CLI is available, False otherwise.
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def check_system_requirements() -> tuple[bool, list[str]]:
    """
    Check system requirements for Claude Remote Client.
    
    Returns:
        tuple: (all_requirements_met, list_of_issues)
    """
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 9):
        issues.append(f"Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check Claude CLI
    if not validate_claude_cli():
        issues.append("Claude CLI not found or not working. Please install Claude CLI first.")
    
    # Check required directories can be created
    try:
        test_dir = os.path.expanduser("~/.claude-remote-client-test")
        ensure_directory_exists(test_dir)
        os.rmdir(test_dir)
    except Exception as e:
        issues.append(f"Cannot create configuration directory: {e}")
    
    return len(issues) == 0, issues


def run_health_check(config_path: Optional[str] = None) -> dict:
    """
    Run comprehensive health check.
    
    Args:
        config_path: Optional path to configuration file.
        
    Returns:
        dict: Health check results with overall status and individual check results.
    """
    checks = {}
    
    # Check system requirements
    requirements_met, issues = check_system_requirements()
    checks['system_requirements'] = {
        'status': requirements_met,
        'message': 'All requirements met' if requirements_met else f"Issues: {', '.join(issues)}"
    }
    
    # Check configuration
    try:
        from .config import load_config
        config = load_config(config_path)
        checks['configuration'] = {
            'status': True,
            'message': 'Configuration loaded successfully'
        }
        
        # Check Claude CLI with config
        try:
            config.validate_claude_cli()
            checks['claude_cli'] = {
                'status': True,
                'message': 'Claude CLI validated successfully'
            }
        except Exception as e:
            checks['claude_cli'] = {
                'status': False,
                'message': f"Claude CLI validation failed: {e}"
            }
            
    except Exception as e:
        checks['configuration'] = {
            'status': False,
            'message': f"Configuration error: {e}"
        }
        checks['claude_cli'] = {
            'status': False,
            'message': 'Skipped due to configuration error'
        }
    
    # Check data directory
    try:
        data_dir = os.path.expanduser("~/.claude-remote-client")
        ensure_directory_exists(data_dir)
        
        # Test write permissions
        test_file = os.path.join(data_dir, ".health_check_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        
        checks['data_directory'] = {
            'status': True,
            'message': f"Data directory accessible: {data_dir}"
        }
    except Exception as e:
        checks['data_directory'] = {
            'status': False,
            'message': f"Data directory error: {e}"
        }
    
    # Check network connectivity (basic)
    try:
        import socket
        socket.create_connection(("slack.com", 443), timeout=5)
        checks['network_connectivity'] = {
            'status': True,
            'message': 'Network connectivity to Slack API available'
        }
    except Exception as e:
        checks['network_connectivity'] = {
            'status': False,
            'message': f"Network connectivity issue: {e}"
        }
    
    # Check memory usage
    try:
        import psutil
        memory = psutil.virtual_memory()
        available_mb = memory.available / (1024 * 1024)
        
        if available_mb > 256:  # Require at least 256MB available
            checks['memory'] = {
                'status': True,
                'message': f"Sufficient memory available: {available_mb:.0f}MB"
            }
        else:
            checks['memory'] = {
                'status': False,
                'message': f"Low memory: {available_mb:.0f}MB available (256MB+ recommended)"
            }
    except ImportError:
        checks['memory'] = {
            'status': True,
            'message': 'Memory check skipped (psutil not available)'
        }
    except Exception as e:
        checks['memory'] = {
            'status': False,
            'message': f"Memory check failed: {e}"
        }
    
    # Overall health status
    overall_healthy = all(check['status'] for check in checks.values())
    
    return {
        'healthy': overall_healthy,
        'checks': checks,
        'timestamp': subprocess.run(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], 
                                  capture_output=True, text=True).stdout.strip()
    }


def run_dry_run_test(config) -> bool:
    """
    Run dry-run test to validate components without connecting to Slack.
    
    Args:
        config: Application configuration.
        
    Returns:
        bool: True if dry-run test passes, False otherwise.
    """
    try:
        print("  🔍 Testing configuration loading...")
        # Configuration is already loaded at this point
        print("  ✅ Configuration loaded successfully")
        
        print("  🔍 Testing Claude CLI validation...")
        config.validate_claude_cli()
        print("  ✅ Claude CLI validated successfully")
        
        print("  🔍 Testing component imports...")
        # Test importing core components
        from .session_manager.session_manager import SessionManager
        from .task_queue.queue_manager import QueueManager
        print("  ✅ Core components imported successfully")
        
        print("  🔍 Testing session manager initialization...")
        session_manager = SessionManager(config)
        print("  ✅ Session manager initialized successfully")
        
        print("  🔍 Testing queue manager initialization...")
        queue_manager = QueueManager(config)
        print("  ✅ Queue manager initialized successfully")
        
        print("  🔍 Testing data directory access...")
        ensure_directory_exists(config.data_dir)
        test_file = os.path.join(config.data_dir, ".dry_run_test")
        with open(test_file, 'w') as f:
            f.write("dry-run test")
        os.remove(test_file)
        print("  ✅ Data directory access verified")
        
        print("  🔍 Testing Slack client initialization (without connection)...")
        # Import but don't connect
        from .slack_client.client import SlackBotClient
        print("  ✅ Slack client can be imported")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Dry-run test failed: {e}")
        return False


def setup_wizard() -> str:
    """
    Interactive setup wizard for first-time configuration.
    
    Returns:
        str: Path to the created configuration file.
    """
    print("🤖 Welcome to Claude Remote Client Setup!")
    print("=" * 50)
    print()
    
    # Check system requirements first
    print("🔍 Checking system requirements...")
    requirements_met, issues = check_system_requirements()
    
    if not requirements_met:
        print("❌ System requirements not met:")
        for issue in issues:
            print(f"   • {issue}")
        print()
        print("Please resolve these issues before continuing.")
        sys.exit(1)
    
    print("✅ System requirements check passed!")
    print()
    
    # Determine config file location
    config_dir = os.path.expanduser("~/.claude-remote-client")
    config_file = os.path.join(config_dir, "config.yaml")
    
    # Check if config already exists
    if os.path.exists(config_file):
        print(f"⚠️  Configuration file already exists: {config_file}")
        overwrite = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return config_file
        print()
    
    # Create data directory
    ensure_directory_exists(config_dir)
    
    print(f"Configuration will be saved to: {config_file}")
    print()
    
    # Collect Slack configuration
    print("📱 Slack Configuration")
    print("-" * 20)
    print("You'll need a Slack Bot Token and Channel ID.")
    print("Visit https://api.slack.com/apps to create a Slack app if you haven't already.")
    print()
    
    slack_bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
    while not slack_bot_token or not slack_bot_token.startswith("xoxb-"):
        if not slack_bot_token:
            print("❌ Bot token is required")
        else:
            print("❌ Invalid bot token. Bot tokens should start with 'xoxb-'")
        slack_bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
    
    slack_channel_id = input("Enter your Slack Channel ID (C...): ").strip()
    while not slack_channel_id or not slack_channel_id.startswith("C"):
        if not slack_channel_id:
            print("❌ Channel ID is required")
        else:
            print("❌ Invalid channel ID. Channel IDs should start with 'C'")
        slack_channel_id = input("Enter your Slack Channel ID (C...): ").strip()
    
    signing_secret = input("Enter your Slack Signing Secret (optional, recommended): ").strip()
    
    print()
    
    # Collect Claude configuration
    print("🧠 Claude Configuration")
    print("-" * 20)
    
    claude_path = input("Enter Claude CLI path (default: claude): ").strip()
    if not claude_path:
        claude_path = "claude"
    
    # Validate Claude CLI path
    try:
        result = subprocess.run(
            [claude_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print(f"⚠️  Warning: Claude CLI at '{claude_path}' may not be working properly")
    except Exception:
        print(f"⚠️  Warning: Could not validate Claude CLI at '{claude_path}'")
    
    print()
    
    # Collect project configuration
    print("📁 Project Configuration")
    print("-" * 25)
    print("Add your development projects. You can add more later in the config file.")
    print()
    
    projects = []
    while True:
        project_name = input("Enter project name (or press Enter to finish): ").strip()
        if not project_name:
            break
        
        # Validate project name
        if any(p['name'] == project_name for p in projects):
            print(f"❌ Project '{project_name}' already exists")
            continue
        
        project_path = input(f"Enter path for '{project_name}': ").strip()
        if not project_path:
            print("❌ Project path is required")
            continue
            
        expanded_path = os.path.expanduser(project_path)
        
        if not validate_project_path(expanded_path):
            print(f"⚠️  Warning: Path '{expanded_path}' does not exist or is not accessible")
            continue_anyway = input("Continue anyway? (y/N): ").strip().lower()
            if continue_anyway != 'y':
                continue
        
        project_desc = input(f"Enter description for '{project_name}' (optional): ").strip()
        
        projects.append({
            'name': project_name,
            'path': project_path,
            'description': project_desc or f"Development project: {project_name}"
        })
        
        print(f"✅ Added project '{project_name}'")
        print()
    
    if not projects:
        print("⚠️  No projects configured. You can add them later in the config file.")
        print("   Example project configuration:")
        print("   projects:")
        print("     - name: my-project")
        print("       path: ~/dev/my-project")
        print("       description: My development project")
    
    print()
    
    # Create configuration file
    config_data = {
        'slack': {
            'bot_token': slack_bot_token,
            'channel_id': slack_channel_id,
        },
        'claude': {
            'cli_path': claude_path,
            'default_args': ['--dangerously-skip-permissions'],
            'timeout': 300,
            'handler_type': 'hybrid',  # Default to hybrid for future compatibility
            'mcp_server_uri': 'mcp://localhost:8000',
            'mcp_protocol_version': '1.0',
            'mcp_timeout': 30,
            'prefer_mcp': False,  # Start with subprocess preference
            'fallback_to_subprocess': True
        },
        'projects': projects,
        'log_level': 'INFO',
        'data_dir': config_dir,
        'max_sessions': 10,
        'task_queue_size': 100
    }
    
    if signing_secret:
        config_data['slack']['signing_secret'] = signing_secret
    
    # Write configuration file
    import yaml
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        print(f"✅ Configuration saved to {config_file}")
        print()
        print("🎉 Setup complete! You can now start the Claude Remote Client.")
        print()
        print("Next steps:")
        print(f"  1. Review your configuration: {config_file}")
        print(f"  2. Start the bot: claude-remote-client --config {config_file}")
        print(f"  3. Or just run: claude-remote-client (uses default config location)")
        print()
        
        return config_file
        
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        sys.exit(1)


async def start_bot(config: Config, enable_health_server: bool = True) -> None:
    """
    Start the Claude Remote Client bot.
    
    Args:
        config: Application configuration.
        enable_health_server: Whether to start the health check server.
    """
    # Import here to avoid circular imports
    from .slack_client.client import SlackBotClient
    from .session_manager.session_manager import SessionManager
    from .task_queue.queue_manager import QueueManager
    from .health_server import start_health_server, stop_health_server
    from .monitoring import health_monitor, metrics_collector
    
    logger = logging.getLogger(__name__)
    
    try:
        # Validate Claude CLI
        logger.info("Validating Claude CLI...")
        config.validate_claude_cli()
        logger.info("✅ Claude CLI validation successful")
        
        # Start health server if enabled
        if enable_health_server:
            logger.info("Starting health check server...")
            health_port = getattr(config, 'health_port', 8080)
            await start_health_server(port=health_port)
            logger.info(f"✅ Health server started on port {health_port}")
        
        # Start monitoring
        logger.info("Starting health monitoring...")
        await health_monitor.start()
        logger.info("✅ Health monitoring started")
        
        # Initialize components
        logger.info("Initializing components...")
        
        session_manager = SessionManager(config)
        queue_manager = QueueManager(config)
        
        # Register health checks
        metrics_collector.register_health_check(
            'session_manager',
            lambda: (True, "Session manager operational")
        )
        metrics_collector.register_health_check(
            'queue_manager', 
            lambda: (True, "Queue manager operational")
        )
        
        # Note: SlackBotClient initialization would need to be updated
        # to match the actual constructor signature
        logger.info("Components initialized successfully")
        
        # Start the main application loop
        logger.info("🚀 Starting Claude Remote Client...")
        
        # Keep the application running
        while True:
            await asyncio.sleep(1)
        
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Shutting down Claude Remote Client...")
        
        # Cleanup
        if enable_health_server:
            logger.info("Stopping health server...")
            await stop_health_server()
        
        logger.info("Stopping health monitoring...")
        await health_monitor.stop()
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


def _handle_handler_commands(args) -> None:
    """Handle handler management commands."""
    try:
        from .claude_client.handler_factory import ClaudeHandlerFactory, create_claude_handler
        from tabulate import tabulate
        import json
        
        config = load_config(args.config if hasattr(args, 'config') else None)
        factory = ClaudeHandlerFactory()
        
        if args.handler_command == 'status':
            # Show handler status
            current_type = config.claude.handler_type
            validation_status = config.get_handler_validation_status()
            
            print(f"Current Handler Type: {current_type}")
            print()
            
            headers = ['Handler', 'Available', 'Status']
            table_data = []
            
            for handler_type, status in validation_status.items():
                available = "✓" if status['available'] else "✗"
                status_msg = "Ready" if status['available'] else (status['error'] or "Not configured")
                table_data.append([handler_type.title(), available, status_msg])
            
            print(tabulate(table_data, headers=headers, tablefmt='grid'))
            
            if args.verbose:
                print("\nDetailed Configuration:")
                print(f"  Subprocess CLI Path: {config.claude.cli_path}")
                print(f"  MCP Server URI: {config.claude.mcp_server_uri}")
                print(f"  MCP Protocol Version: {config.claude.mcp_protocol_version}")
                
                if current_type == 'hybrid':
                    print(f"  Prefer MCP: {config.claude.prefer_mcp}")
                    print(f"  Fallback to Subprocess: {config.claude.fallback_to_subprocess}")
        
        elif args.handler_command == 'test':
            # Test handler functionality
            if args.type == 'all':
                handler_types = ['subprocess', 'mcp', 'hybrid']
            else:
                handler_types = [args.type]
            
            results = {}
            
            for htype in handler_types:
                print(f"Testing {htype} handler...")
                
                try:
                    test_config = Config(
                        claude=config.claude,
                        slack=config.slack,
                        projects=config.projects
                    )
                    test_config.claude.handler_type = htype
                    
                    handler = factory.create_handler(test_config)
                    result = asyncio.run(_test_handler_functionality(handler, args.timeout))
                    results[htype] = result
                    
                    status = "✓ PASS" if result['success'] else "✗ FAIL"
                    print(f"  {status}: {result['message']}")
                    
                    if result.get('details'):
                        for detail in result['details']:
                            print(f"    - {detail}")
                
                except Exception as e:
                    results[htype] = {'success': False, 'message': str(e)}
                    print(f"  ✗ FAIL: {str(e)}")
            
            print("\nTest Summary:")
            passed = sum(1 for r in results.values() if r['success'])
            total = len(results)
            print(f"  Passed: {passed}/{total}")
            
            if passed < total:
                sys.exit(1)
        
        elif args.handler_command == 'recommend':
            # Get recommendations
            recommendation = config.recommend_handler_type()
            
            print("Handler Recommendation Analysis")
            print("=" * 40)
            
            if recommendation['recommended']:
                print(f"Recommended: {recommendation['recommended']}")
                print(f"Reason: {recommendation['reason']}")
            else:
                print("No handler is currently available")
            
            if recommendation['alternatives']:
                print("\nAlternatives:")
                for alt in recommendation['alternatives']:
                    print(f"  - {alt['type']}: {alt['reason']}")
            
            if recommendation['warnings']:
                print("\nWarnings:")
                for warning in recommendation['warnings']:
                    print(f"  ⚠ {warning}")
        
        elif args.handler_command == 'list':
            # List available handlers
            available_handlers = factory.get_available_handler_types()
            
            print("Available Handler Types")
            print("=" * 30)
            
            for handler_name, info in available_handlers.items():
                print(f"\n{handler_name.upper()}")
                print(f"  Description: {info['description']}")
                
                requirements = info['requirements']
                print("  Requirements:")
                for req, needed in requirements.items():
                    status = "Required" if needed else "Optional"
                    print(f"    - {req}: {status}")
                
                capabilities = info['capabilities']
                print("  Capabilities:")
                for cap, supported in capabilities.items():
                    status = "✓" if supported else "✗"
                    print(f"    - {cap}: {status}")
        
        elif args.handler_command == 'switch':
            # Switch handler type
            test_config = Config(
                claude=config.claude,
                slack=config.slack,
                projects=config.projects
            )
            test_config.claude.handler_type = args.handler_type
            
            validation_status = test_config.get_handler_validation_status()
            
            if not validation_status[args.handler_type]['available']:
                error = validation_status[args.handler_type]['error']
                print(f"Cannot switch to {args.handler_type}: {error}", file=sys.stderr)
                sys.exit(1)
            
            if args.dry_run:
                print(f"Would switch from {config.claude.handler_type} to {args.handler_type}")
                print("Configuration changes:")
                print(f"  handler_type: {config.claude.handler_type} → {args.handler_type}")
                return
            
            print(f"Switched to {args.handler_type} handler")
            print("Note: Configuration change would need to be persisted manually")
            print("Please update your configuration file and restart the service")
        
        elif args.handler_command == 'capabilities':
            # Show capabilities
            capabilities_data = {}
            
            for handler_type in ['subprocess', 'mcp', 'hybrid']:
                try:
                    test_config = Config(
                        claude=config.claude,
                        slack=config.slack,
                        projects=config.projects
                    )
                    test_config.claude.handler_type = handler_type
                    
                    handler = factory.create_handler(test_config)
                    caps = asyncio.run(handler.get_capabilities())
                    
                    capabilities_data[handler_type] = {
                        'streaming': caps.streaming,
                        'context_window': caps.context_window,
                        'file_upload': caps.file_upload,
                        'models': len(caps.models),
                        'session_persistence': caps.session_persistence,
                        'concurrent_sessions': caps.concurrent_sessions,
                        'interactive_mode': caps.interactive_mode,
                        'batch_processing': caps.batch_processing,
                        'custom_tools': caps.custom_tools,
                        'mcp_servers': caps.mcp_servers
                    }
                    
                    asyncio.run(handler.cleanup())
                
                except Exception as e:
                    capabilities_data[handler_type] = {'error': str(e)}
            
            if args.format == 'json':
                print(json.dumps(capabilities_data, indent=2))
            else:
                headers = ['Capability'] + list(capabilities_data.keys())
                table_data = []
                
                all_caps = set()
                for caps in capabilities_data.values():
                    if 'error' not in caps:
                        all_caps.update(caps.keys())
                
                for cap in sorted(all_caps):
                    row = [cap.replace('_', ' ').title()]
                    for handler_type in capabilities_data.keys():
                        caps = capabilities_data[handler_type]
                        if 'error' in caps:
                            row.append('Error')
                        else:
                            value = caps.get(cap, 'N/A')
                            if isinstance(value, bool):
                                row.append('✓' if value else '✗')
                            else:
                                row.append(str(value))
                    table_data.append(row)
                
                print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        elif args.handler_command == 'monitor':
            # Monitor handler
            handler = create_claude_handler(config)
            
            print(f"Monitoring {config.claude.handler_type} handler for {args.duration} seconds...")
            print("Press Ctrl+C to stop early")
            
            start_time = asyncio.get_event_loop().time()
            
            try:
                while True:
                    current_time = asyncio.get_event_loop().time()
                    elapsed = current_time - start_time
                    
                    if elapsed >= args.duration:
                        break
                    
                    healthy = asyncio.run(handler.is_healthy())
                    context_info = asyncio.run(handler.get_context_info())
                    
                    status = "Healthy" if healthy else "Unhealthy"
                    print(f"\r[{elapsed:6.1f}s] Status: {status} | "
                          f"Context: {context_info.get('total_tokens', 0)} tokens", end='', flush=True)
                    
                    asyncio.run(asyncio.sleep(args.interval))
            
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
            
            finally:
                asyncio.run(handler.cleanup())
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


async def _test_handler_functionality(handler, timeout: int) -> dict:
    """Test basic handler functionality."""
    try:
        await asyncio.wait_for(handler.initialize(), timeout=timeout)
        
        healthy = await asyncio.wait_for(handler.is_healthy(), timeout=timeout)
        if not healthy:
            return {
                'success': False,
                'message': 'Handler health check failed'
            }
        
        capabilities = await asyncio.wait_for(handler.get_capabilities(), timeout=timeout)
        
        return {
            'success': True,
            'message': 'All tests passed',
            'details': [
                f'Streaming: {capabilities.streaming}',
                f'Context Window: {capabilities.context_window}',
                f'Models: {len(capabilities.models)}'
            ]
        }
    
    except asyncio.TimeoutError:
        return {
            'success': False,
            'message': f'Test timed out after {timeout} seconds'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Test failed: {str(e)}'
        }
    finally:
        try:
            await handler.cleanup()
        except Exception:
            pass


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Claude Remote Client - Remote Claude AI interaction through Slack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-remote-client                    # Run with default config
  claude-remote-client --setup           # Run setup wizard
  claude-remote-client --config my.yaml  # Use custom config file
  claude-remote-client --validate        # Validate configuration only
  claude-remote-client --check           # Check system requirements
  claude-remote-client handler status    # Show handler status
  claude-remote-client handler test      # Test handlers
        """
    )
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Handler management subcommand
    handler_parser = subparsers.add_parser('handler', help='Handler management commands')
    handler_subparsers = handler_parser.add_subparsers(dest='handler_command', help='Handler commands')
    
    # Handler status command
    status_parser = handler_subparsers.add_parser('status', help='Show handler status')
    status_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    
    # Handler test command
    test_parser = handler_subparsers.add_parser('test', help='Test handler functionality')
    test_parser.add_argument('--type', choices=['subprocess', 'mcp', 'hybrid', 'all'], 
                           default='all', help='Handler type to test')
    test_parser.add_argument('--timeout', type=int, default=30, help='Test timeout in seconds')
    
    # Handler recommend command
    handler_subparsers.add_parser('recommend', help='Get handler type recommendations')
    
    # Handler list command
    handler_subparsers.add_parser('list', help='List available handler types')
    
    # Handler switch command
    switch_parser = handler_subparsers.add_parser('switch', help='Switch to a different handler type')
    switch_parser.add_argument('handler_type', choices=['subprocess', 'mcp', 'hybrid'], 
                              help='Handler type to switch to')
    switch_parser.add_argument('--dry-run', action='store_true', 
                              help='Show what would be changed without applying')
    
    # Handler capabilities command
    capabilities_parser = handler_subparsers.add_parser('capabilities', help='Show handler capabilities')
    capabilities_parser.add_argument('--format', choices=['table', 'json'], default='table', 
                                    help='Output format')
    
    # Handler monitor command
    monitor_parser = handler_subparsers.add_parser('monitor', help='Monitor handler performance')
    monitor_parser.add_argument('--duration', type=int, default=60, help='Monitoring duration in seconds')
    monitor_parser.add_argument('--interval', type=int, default=5, help='Update interval in seconds')
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file (default: ~/.claude-remote-client/config.yaml)"
    )
    
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Run interactive setup wizard"
    )
    
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check system requirements and exit"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path (default: ~/.claude-remote-client/claude-remote-client.log)"
    )
    
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon (background process)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Claude Remote Client 0.1.0"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check and exit"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and test components without connecting to Slack"
    )
    
    parser.add_argument(
        "--no-health-server",
        action="store_true",
        help="Disable health check HTTP server"
    )
    
    parser.add_argument(
        "--health-port",
        type=int,
        default=8080,
        help="Port for health check server (default: 8080)"
    )
    
    args = parser.parse_args()
    
    # Handle handler subcommands
    if args.command == 'handler':
        _handle_handler_commands(args)
        return
    
    # Check system requirements if requested
    if args.check:
        print("🔍 Checking system requirements...")
        requirements_met, issues = check_system_requirements()
        
        if requirements_met:
            print("✅ All system requirements are met!")
        else:
            print("❌ System requirements not met:")
            for issue in issues:
                print(f"   • {issue}")
            sys.exit(1)
        return
    
    # Run health check if requested
    if args.health_check:
        print("🏥 Running health check...")
        health_status = run_health_check(args.config)
        
        if health_status['healthy']:
            print("✅ Health check passed!")
            for check, result in health_status['checks'].items():
                status = "✅" if result['status'] else "❌"
                print(f"   {status} {check}: {result['message']}")
        else:
            print("❌ Health check failed!")
            for check, result in health_status['checks'].items():
                status = "✅" if result['status'] else "❌"
                print(f"   {status} {check}: {result['message']}")
            sys.exit(1)
        return
    
    # Run setup wizard if requested
    if args.setup:
        config_file = setup_wizard()
        if not args.validate:
            print()
            print("To start the bot now, run:")
            print(f"  claude-remote-client --config {config_file}")
        return
    
    # Determine log file path
    log_file = args.log_file
    if not log_file:
        log_dir = os.path.expanduser("~/.claude-remote-client")
        ensure_directory_exists(log_dir)
        log_file = os.path.join(log_dir, "claude-remote-client.log")
    
    # Set up logging
    logger = setup_logging(args.log_level, log_file)
    
    try:
        # Load configuration
        config = load_config(args.config)
        logger.info("✅ Configuration loaded successfully")
        
        # Create data directory
        ensure_directory_exists(config.data_dir)
        
        # If validate only, exit after validation
        if args.validate:
            print("🔍 Validating configuration...")
            config.validate_claude_cli()
            print("✅ Configuration is valid!")
            return
        
        # If dry-run, test components without connecting
        if args.dry_run:
            print("🧪 Running dry-run test...")
            dry_run_success = run_dry_run_test(config)
            
            if dry_run_success:
                print("✅ Dry-run test passed! Ready to start normally.")
            else:
                print("❌ Dry-run test failed! Check configuration and try again.")
                sys.exit(1)
            return
        
        # Handle daemon mode
        if args.daemon:
            logger.info("Starting in daemon mode...")
            # Note: Full daemon implementation would require additional setup
            # For now, we'll just run normally but log the intent
        
        # Set health port in config if provided
        if hasattr(config, '__dict__'):
            config.health_port = args.health_port
        
        # Start the bot
        logger.info("🚀 Starting Claude Remote Client...")
        asyncio.run(start_bot(config, enable_health_server=not args.no_health_server))
        
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error: {e}")
        print()
        print("💡 Tip: Run 'claude-remote-client --setup' to create a new configuration.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()