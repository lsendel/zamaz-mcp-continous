"""
CLI commands for handler management and MCP evolution.

This module provides command-line interface commands for managing
Claude handlers, testing configurations, and facilitating MCP migration.
"""

import asyncio
import json
import sys
from typing import Dict, Any, Optional
import click
from tabulate import tabulate

from .config import load_config, Config
from .claude_client.handler_factory import (
    ClaudeHandlerFactory,
    create_claude_handler,
    get_handler_recommendations
)
from .claude_client.handler_interface import HandlerType
from .exceptions import ConfigurationError, ClaudeProcessError


@click.group()
def handler():
    """Handler management commands."""
    pass


@handler.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def status(verbose: bool):
    """Show current handler status."""
    try:
        config = load_config()
        factory = ClaudeHandlerFactory()
        
        # Get current handler type
        current_type = config.claude.handler_type
        
        # Get validation status
        validation_status = config.get_handler_validation_status()
        
        # Display current configuration
        click.echo(f"Current Handler Type: {current_type}")
        click.echo()
        
        # Display handler availability
        headers = ['Handler', 'Available', 'Status']
        table_data = []
        
        for handler_type, status in validation_status.items():
            available = "✓" if status['available'] else "✗"
            status_msg = "Ready" if status['available'] else (status['error'] or "Not configured")
            table_data.append([handler_type.title(), available, status_msg])
        
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        if verbose:
            click.echo("\nDetailed Configuration:")
            click.echo(f"  Subprocess CLI Path: {config.claude.cli_path}")
            click.echo(f"  MCP Server URI: {config.claude.mcp_server_uri}")
            click.echo(f"  MCP Protocol Version: {config.claude.mcp_protocol_version}")
            
            if current_type == 'hybrid':
                click.echo(f"  Prefer MCP: {config.claude.prefer_mcp}")
                click.echo(f"  Fallback to Subprocess: {config.claude.fallback_to_subprocess}")
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@handler.command()
@click.option('--type', 'handler_type', type=click.Choice(['subprocess', 'mcp', 'hybrid', 'all']), 
              default='all', help='Handler type to test')
@click.option('--timeout', type=int, default=30, help='Test timeout in seconds')
def test(handler_type: str, timeout: int):
    """Test handler functionality."""
    try:
        config = load_config()
        factory = ClaudeHandlerFactory()
        
        if handler_type == 'all':
            handler_types = ['subprocess', 'mcp', 'hybrid']
        else:
            handler_types = [handler_type]
        
        results = {}
        
        for htype in handler_types:
            click.echo(f"Testing {htype} handler...")
            
            try:
                # Create test configuration
                test_config = Config(
                    claude=config.claude,
                    slack=config.slack,
                    projects=config.projects
                )
                test_config.claude.handler_type = htype
                
                # Test handler creation
                handler = factory.create_handler(test_config)
                
                # Test basic functionality
                result = asyncio.run(_test_handler_functionality(handler, timeout))
                results[htype] = result
                
                status = "✓ PASS" if result['success'] else "✗ FAIL"
                click.echo(f"  {status}: {result['message']}")
                
                if result.get('details'):
                    for detail in result['details']:
                        click.echo(f"    - {detail}")
            
            except Exception as e:
                results[htype] = {'success': False, 'message': str(e)}
                click.echo(f"  ✗ FAIL: {str(e)}")
        
        # Summary
        click.echo("\nTest Summary:")
        passed = sum(1 for r in results.values() if r['success'])
        total = len(results)
        click.echo(f"  Passed: {passed}/{total}")
        
        if passed < total:
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


async def _test_handler_functionality(handler, timeout: int) -> Dict[str, Any]:
    """Test basic handler functionality."""
    try:
        # Test initialization
        await asyncio.wait_for(handler.initialize(), timeout=timeout)
        
        # Test health check
        healthy = await asyncio.wait_for(handler.is_healthy(), timeout=timeout)
        if not healthy:
            return {
                'success': False,
                'message': 'Handler health check failed'
            }
        
        # Test capabilities
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


@handler.command()
def recommend():
    """Get handler type recommendations."""
    try:
        config = load_config()
        recommendation = config.recommend_handler_type()
        
        click.echo("Handler Recommendation Analysis")
        click.echo("=" * 40)
        
        if recommendation['recommended']:
            click.echo(f"Recommended: {recommendation['recommended']}")
            click.echo(f"Reason: {recommendation['reason']}")
        else:
            click.echo("No handler is currently available")
        
        if recommendation['alternatives']:
            click.echo("\nAlternatives:")
            for alt in recommendation['alternatives']:
                click.echo(f"  - {alt['type']}: {alt['reason']}")
        
        if recommendation['warnings']:
            click.echo("\nWarnings:")
            for warning in recommendation['warnings']:
                click.echo(f"  ⚠ {warning}")
        
        # Show validation details
        validation_status = config.get_handler_validation_status()
        click.echo("\nHandler Availability:")
        
        for handler_type, status in validation_status.items():
            available = "Available" if status['available'] else "Unavailable"
            click.echo(f"  {handler_type}: {available}")
            if status['error']:
                click.echo(f"    Error: {status['error']}")
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@handler.command()
def list():
    """List available handler types."""
    try:
        factory = ClaudeHandlerFactory()
        available_handlers = factory.get_available_handler_types()
        
        click.echo("Available Handler Types")
        click.echo("=" * 30)
        
        for handler_name, info in available_handlers.items():
            click.echo(f"\n{handler_name.upper()}")
            click.echo(f"  Description: {info['description']}")
            
            # Requirements
            requirements = info['requirements']
            click.echo("  Requirements:")
            for req, needed in requirements.items():
                status = "Required" if needed else "Optional"
                click.echo(f"    - {req}: {status}")
            
            # Capabilities
            capabilities = info['capabilities']
            click.echo("  Capabilities:")
            for cap, supported in capabilities.items():
                status = "✓" if supported else "✗"
                click.echo(f"    - {cap}: {status}")
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@handler.command()
@click.argument('handler_type', type=click.Choice(['subprocess', 'mcp', 'hybrid']))
@click.option('--dry-run', is_flag=True, help='Show what would be changed without applying')
def switch(handler_type: str, dry_run: bool):
    """Switch to a different handler type."""
    try:
        config = load_config()
        
        # Validate the target handler
        test_config = Config(
            claude=config.claude,
            slack=config.slack,
            projects=config.projects
        )
        test_config.claude.handler_type = handler_type
        
        validation_status = test_config.get_handler_validation_status()
        
        if not validation_status[handler_type]['available']:
            error = validation_status[handler_type]['error']
            click.echo(f"Cannot switch to {handler_type}: {error}", err=True)
            sys.exit(1)
        
        if dry_run:
            click.echo(f"Would switch from {config.claude.handler_type} to {handler_type}")
            click.echo("Configuration changes:")
            click.echo(f"  handler_type: {config.claude.handler_type} → {handler_type}")
            return
        
        # Apply the change
        config.claude.handler_type = handler_type
        
        # Save configuration (this would need to be implemented)
        click.echo(f"Switched to {handler_type} handler")
        click.echo("Please restart the service for changes to take effect")
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@handler.command()
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), 
              default='table', help='Output format')
def capabilities(output_format: str):
    """Show capabilities of available handlers."""
    try:
        config = load_config()
        factory = ClaudeHandlerFactory()
        
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
                
                await handler.cleanup()
            
            except Exception as e:
                capabilities_data[handler_type] = {'error': str(e)}
        
        if output_format == 'json':
            click.echo(json.dumps(capabilities_data, indent=2))
        else:
            # Table format
            headers = ['Capability'] + list(capabilities_data.keys())
            table_data = []
            
            # Get all capability keys
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
            
            click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@handler.command()
@click.option('--duration', type=int, default=60, help='Monitoring duration in seconds')
@click.option('--interval', type=int, default=5, help='Update interval in seconds')
def monitor(duration: int, interval: int):
    """Monitor handler performance and health."""
    try:
        config = load_config()
        handler = create_claude_handler(config)
        
        click.echo(f"Monitoring {config.claude.handler_type} handler for {duration} seconds...")
        click.echo("Press Ctrl+C to stop early")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            while True:
                current_time = asyncio.get_event_loop().time()
                elapsed = current_time - start_time
                
                if elapsed >= duration:
                    break
                
                # Get handler status
                healthy = asyncio.run(handler.is_healthy())
                context_info = asyncio.run(handler.get_context_info())
                
                # Display status
                status = "Healthy" if healthy else "Unhealthy"
                click.echo(f"\r[{elapsed:6.1f}s] Status: {status} | "
                          f"Context: {context_info.get('total_tokens', 0)} tokens", nl=False)
                
                asyncio.run(asyncio.sleep(interval))
        
        except KeyboardInterrupt:
            click.echo("\nMonitoring stopped by user")
        
        finally:
            asyncio.run(handler.cleanup())
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    handler()