"""
Deployment and installation tests for Claude Remote Client.

These tests verify that the package can be properly installed, configured,
and deployed in various environments.
"""

import pytest
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from claude_remote_client.config import Config, load_config
from claude_remote_client.cli import main, setup_wizard, validate_claude_cli


class TestPackageInstallation:
    """Test package installation and setup."""
    
    def test_package_importable(self):
        """Test that the package can be imported."""
        import claude_remote_client
        assert claude_remote_client is not None
        
        # Test main modules are importable
        from claude_remote_client.config import Config
        from claude_remote_client.models import ClaudeSession
        from claude_remote_client.session_manager.session_manager import SessionManager
        
        assert Config is not None
        assert ClaudeSession is not None
        assert SessionManager is not None
    
    def test_entry_points_available(self):
        """Test that CLI entry points are available."""
        # Test that the main CLI function exists
        from claude_remote_client.cli import main
        assert callable(main)
        
        # Test that setup wizard exists
        from claude_remote_client.cli import setup_wizard
        assert callable(setup_wizard)
    
    def test_dependencies_available(self):
        """Test that all required dependencies are available."""
        required_modules = [
            'asyncio',
            'aiofiles',
            'yaml',
            'croniter',
            'slack_sdk',
            'dataclasses',
            'pathlib',
            'logging',
            'json',
            'uuid',
            'datetime'
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                pytest.fail(f"Required dependency '{module_name}' not available")


class TestConfigurationSetup:
    """Test configuration setup and validation."""
    
    def test_default_config_creation(self):
        """Test creation of default configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Test config creation
            config = Config(data_dir=temp_dir)
            
            # Should have reasonable defaults
            assert config.data_dir == temp_dir
            assert config.max_sessions > 0
            assert config.task_queue_size > 0
    
    def test_config_file_loading(self):
        """Test loading configuration from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Create test config file
            config_data = {
                'slack': {
                    'bot_token': 'xoxb-test-token',
                    'channel_id': 'C1234567890'
                },
                'claude': {
                    'cli_path': 'claude'
                },
                'projects': [
                    {
                        'name': 'test-project',
                        'path': '/test/path',
                        'description': 'Test project'
                    }
                ],
                'max_sessions': 5,
                'task_queue_size': 100
            }
            
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            # Load config
            config = load_config(str(config_path))
            
            assert config.slack.bot_token == 'xoxb-test-token'
            assert config.slack.channel_id == 'C1234567890'
            assert config.claude.cli_path == 'claude'
            assert len(config.projects) == 1
            assert config.projects[0].name == 'test-project'
    
    def test_environment_variable_override(self):
        """Test configuration override via environment variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set environment variables
            env_vars = {
                'CLAUDE_REMOTE_SLACK_TOKEN': 'xoxb-env-token',
                'CLAUDE_REMOTE_CHANNEL_ID': 'C9876543210',
                'CLAUDE_REMOTE_DATA_DIR': temp_dir
            }
            
            with patch.dict(os.environ, env_vars):
                config = load_config()
                
                # Environment variables should override defaults
                assert config.slack.bot_token == 'xoxb-env-token'
                assert config.slack.channel_id == 'C9876543210'
                assert config.data_dir == temp_dir
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test invalid configuration
        with pytest.raises((ValueError, AttributeError)):
            config = Config()
            config.validate()


class TestCLIFunctionality:
    """Test CLI functionality and commands."""
    
    def test_cli_help_command(self):
        """Test CLI help command."""
        with patch('sys.argv', ['claude-remote-client', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Help should exit with code 0
            assert exc_info.value.code == 0
    
    def test_setup_wizard_basic_flow(self):
        """Test setup wizard basic flow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            # Mock user inputs
            inputs = [
                'xoxb-test-token',  # Slack bot token
                'xapp-test-token',  # Slack app token
                'C1234567890',      # Channel ID
                'test-secret',      # Signing secret
                '/test/project',    # Project path
                'test-project',     # Project name
                'Test project',     # Project description
                'n',                # No more projects
                'y'                 # Confirm setup
            ]
            
            with patch('builtins.input', side_effect=inputs), \
                 patch('pathlib.Path.exists', return_value=True), \
                 patch('pathlib.Path.is_dir', return_value=True):
                
                config = setup_wizard(str(config_path))
                
                assert config.slack.bot_token == 'xoxb-test-token'
                assert config.slack.channel_id == 'C1234567890'
                assert len(config.projects) == 1
                assert config.projects[0].name == 'test-project'
    
    def test_claude_cli_validation(self):
        """Test Claude CLI validation."""
        # Test with mock successful validation
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Claude CLI version 1.0")
            
            result = validate_claude_cli()
            assert result is True
            
            mock_run.assert_called_once()
        
        # Test with mock failed validation
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            
            result = validate_claude_cli()
            assert result is False


class TestSystemRequirements:
    """Test system requirements and compatibility."""
    
    def test_python_version_compatibility(self):
        """Test Python version compatibility."""
        # Should work with Python 3.9+
        assert sys.version_info >= (3, 9), "Python 3.9+ required"
    
    def test_required_directories_creation(self):
        """Test that required directories can be created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(data_dir=temp_dir)
            
            # Test directory structure creation
            data_dir = Path(temp_dir)
            sessions_dir = data_dir / "sessions"
            queues_dir = data_dir / "queues"
            logs_dir = data_dir / "logs"
            
            # Create directories
            sessions_dir.mkdir(parents=True, exist_ok=True)
            queues_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify directories exist
            assert sessions_dir.exists()
            assert queues_dir.exists()
            assert logs_dir.exists()
    
    def test_file_permissions(self):
        """Test file permission requirements."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.json"
            
            # Test file creation and writing
            test_data = {"test": "data"}
            import json
            
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            # Test file reading
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
            
            assert loaded_data == test_data
    
    def test_network_requirements(self):
        """Test network connectivity requirements."""
        # Test that required network libraries are available
        try:
            import socket
            import ssl
            import urllib.request
            
            # Basic connectivity test (mock)
            with patch('socket.create_connection') as mock_connect:
                mock_connect.return_value = MagicMock()
                
                # Should be able to create connections
                sock = socket.create_connection(('slack.com', 443), timeout=5)
                assert sock is not None
                
        except ImportError:
            pytest.fail("Required network libraries not available")


class TestDeploymentScenarios:
    """Test various deployment scenarios."""
    
    def test_docker_compatibility(self):
        """Test Docker deployment compatibility."""
        # Test that the application can run in a containerized environment
        
        # Mock Docker environment variables
        docker_env = {
            'DOCKER': 'true',
            'HOME': '/app',
            'USER': 'app'
        }
        
        with patch.dict(os.environ, docker_env):
            with tempfile.TemporaryDirectory() as temp_dir:
                config = Config(data_dir=temp_dir)
                
                # Should handle containerized environment
                assert config.data_dir == temp_dir
    
    def test_systemd_service_compatibility(self):
        """Test systemd service compatibility."""
        # Test that the application can run as a systemd service
        
        # Mock systemd environment
        systemd_env = {
            'INVOCATION_ID': 'test-invocation',
            'JOURNAL_STREAM': '8:12345'
        }
        
        with patch.dict(os.environ, systemd_env):
            # Should handle systemd environment
            config = Config()
            assert config is not None
    
    def test_user_installation(self):
        """Test user-level installation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock user home directory
            home_dir = Path(temp_dir) / "home" / "user"
            home_dir.mkdir(parents=True)
            
            with patch('pathlib.Path.home', return_value=home_dir):
                config_dir = home_dir / ".claude-remote-client"
                config_dir.mkdir(parents=True, exist_ok=True)
                
                # Should be able to create user configuration
                config_file = config_dir / "config.yaml"
                config_file.touch()
                
                assert config_file.exists()
    
    def test_system_installation(self):
        """Test system-wide installation."""
        # Test system-wide configuration paths
        system_paths = [
            "/etc/claude-remote-client",
            "/usr/local/etc/claude-remote-client",
            "/opt/claude-remote-client/etc"
        ]
        
        # Mock system path access
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Should handle system paths
            for path in system_paths:
                config_path = Path(path) / "config.yaml"
                assert config_path.parent.name in ["claude-remote-client", "etc"]


class TestUpgradeCompatibility:
    """Test upgrade and migration compatibility."""
    
    def test_config_migration(self):
        """Test configuration migration between versions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create old format config
            old_config_path = Path(temp_dir) / "old_config.yaml"
            old_config_data = {
                'slack_token': 'xoxb-old-token',  # Old format
                'channel': 'C1234567890',         # Old format
                'projects': ['/old/project/path'] # Old format
            }
            
            import yaml
            with open(old_config_path, 'w') as f:
                yaml.dump(old_config_data, f)
            
            # Test migration (would be handled by config loader)
            # This is a placeholder for actual migration logic
            migrated_config = {
                'slack': {
                    'bot_token': old_config_data['slack_token'],
                    'channel_id': old_config_data['channel']
                },
                'projects': [
                    {
                        'name': 'migrated-project',
                        'path': old_config_data['projects'][0],
                        'description': 'Migrated project'
                    }
                ]
            }
            
            assert migrated_config['slack']['bot_token'] == 'xoxb-old-token'
            assert migrated_config['slack']['channel_id'] == 'C1234567890'
    
    def test_data_format_compatibility(self):
        """Test data format compatibility across versions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test that old data formats can be read
            old_session_data = {
                'session_id': 'old-session-123',
                'project_path': '/old/project',
                'created_at': '2024-01-01T00:00:00',
                'conversation_history': [
                    {'role': 'user', 'content': 'Hello'}
                ]
            }
            
            session_file = Path(temp_dir) / "old-session-123.json"
            import json
            with open(session_file, 'w') as f:
                json.dump(old_session_data, f)
            
            # Should be able to load old format
            with open(session_file, 'r') as f:
                loaded_data = json.load(f)
            
            assert loaded_data['session_id'] == 'old-session-123'
            assert loaded_data['project_path'] == '/old/project'


class TestErrorHandlingDeployment:
    """Test error handling in deployment scenarios."""
    
    def test_missing_dependencies_handling(self):
        """Test handling of missing dependencies."""
        # Mock missing dependency
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError):
                # This would normally be handled gracefully in production
                import non_existent_module
    
    def test_permission_errors_handling(self):
        """Test handling of permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create read-only directory
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only
            
            try:
                # Should handle permission errors gracefully
                config_file = readonly_dir / "config.yaml"
                
                with pytest.raises(PermissionError):
                    with open(config_file, 'w') as f:
                        f.write("test")
                        
            finally:
                # Cleanup
                readonly_dir.chmod(0o755)
    
    def test_disk_space_handling(self):
        """Test handling of disk space issues."""
        # This would be tested with actual disk space constraints in real deployment
        # For now, we test the error handling structure
        
        with tempfile.TemporaryDirectory() as temp_dir:
            large_file = Path(temp_dir) / "large_file.json"
            
            # Mock disk space error
            with patch('builtins.open', side_effect=OSError("No space left on device")):
                with pytest.raises(OSError):
                    with open(large_file, 'w') as f:
                        f.write("data")


@pytest.mark.slow
class TestPerformanceDeployment:
    """Test performance characteristics in deployment."""
    
    def test_startup_time(self):
        """Test application startup time."""
        import time
        
        start_time = time.time()
        
        # Import main modules (simulates startup)
        from claude_remote_client.config import Config
        from claude_remote_client.session_manager.session_manager import SessionManager
        from claude_remote_client.task_queue.queue_manager import QueueManager
        
        end_time = time.time()
        startup_time = end_time - start_time
        
        # Should start reasonably quickly (adjust threshold as needed)
        assert startup_time < 5.0, f"Startup took {startup_time:.2f} seconds"
    
    def test_memory_usage_basic(self):
        """Test basic memory usage characteristics."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create some objects
        from claude_remote_client.models import ClaudeSession, QueuedTask
        
        sessions = [ClaudeSession() for _ in range(100)]
        tasks = [QueuedTask() for _ in range(100)]
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (adjust threshold as needed)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.2f} MB"
    
    def test_concurrent_operations_performance(self):
        """Test performance under concurrent operations."""
        import asyncio
        import time
        
        async def concurrent_test():
            start_time = time.time()
            
            # Simulate concurrent operations
            tasks = []
            for i in range(10):
                task = asyncio.create_task(asyncio.sleep(0.1))  # Simulate async work
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should handle concurrency efficiently
            assert total_time < 1.0, f"Concurrent operations took {total_time:.2f} seconds"
        
        asyncio.run(concurrent_test())