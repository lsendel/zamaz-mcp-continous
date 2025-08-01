"""
Integration tests for the complete setup and installation process.

These tests verify the end-to-end setup workflow including:
- System requirements validation
- Configuration file creation
- CLI command functionality
- Package installation verification
"""

import pytest
import tempfile
import os
import subprocess
import sys
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from claude_remote_client.cli import main, setup_wizard, check_system_requirements
from claude_remote_client.config import load_config
from claude_remote_client.exceptions import ConfigurationError


class TestCompleteSetupProcess:
    """Integration tests for the complete setup process."""
    
    def test_end_to_end_setup_workflow(self):
        """Test the complete setup workflow from start to finish."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, ".claude-remote-client")
            config_file = os.path.join(config_dir, "config.yaml")
            
            # Mock system requirements check
            with patch('claude_remote_client.cli.check_system_requirements') as mock_check:
                mock_check.return_value = (True, [])
                
                # Mock user inputs for setup wizard
                with patch('builtins.input') as mock_input:
                    mock_input.side_effect = [
                        "xoxb-integration-test-token",  # Slack bot token
                        "C1234567890",                  # Slack channel ID
                        "test-signing-secret",          # Signing secret
                        "claude",                       # Claude CLI path
                        "test-project",                 # Project name
                        temp_dir,                       # Project path (use temp dir)
                        "Integration test project",     # Project description
                        "",                             # No more projects
                    ]
                    
                    # Mock path operations
                    with patch('os.path.expanduser', return_value=config_dir):
                        with patch('subprocess.run') as mock_subprocess:
                            mock_subprocess.return_value.returncode = 0
                            
                            with patch('claude_remote_client.utils.validate_project_path', return_value=True):
                                with patch('os.path.exists', return_value=False):
                                    # Run setup wizard
                                    result_config_file = setup_wizard()
                                    
                                    # Verify config file was created
                                    assert os.path.exists(result_config_file)
                                    
                                    # Load and verify configuration
                                    with open(result_config_file, 'r') as f:
                                        config_data = yaml.safe_load(f)
                                    
                                    # Verify all expected configuration sections
                                    assert 'slack' in config_data
                                    assert 'claude' in config_data
                                    assert 'projects' in config_data
                                    assert 'log_level' in config_data
                                    assert 'data_dir' in config_data
                                    
                                    # Verify Slack configuration
                                    assert config_data['slack']['bot_token'] == 'xoxb-integration-test-token'
                                    assert config_data['slack']['channel_id'] == 'C1234567890'
                                    assert config_data['slack']['signing_secret'] == 'test-signing-secret'
                                    
                                    # Verify Claude configuration
                                    assert config_data['claude']['cli_path'] == 'claude'
                                    assert '--dangerously-skip-permissions' in config_data['claude']['default_args']
                                    
                                    # Verify project configuration
                                    assert len(config_data['projects']) == 1
                                    assert config_data['projects'][0]['name'] == 'test-project'
                                    assert config_data['projects'][0]['path'] == temp_dir
                                    assert config_data['projects'][0]['description'] == 'Integration test project'
    
    def test_config_validation_after_setup(self):
        """Test that configuration created by setup wizard can be loaded and validated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, ".claude-remote-client")
            config_file = os.path.join(config_dir, "config.yaml")
            
            # Create a valid configuration file
            config_data = {
                'slack': {
                    'bot_token': 'xoxb-test-token-123',
                    'channel_id': 'C1234567890',
                    'signing_secret': 'test-secret'
                },
                'claude': {
                    'cli_path': 'claude',
                    'default_args': ['--dangerously-skip-permissions'],
                    'timeout': 300
                },
                'projects': [
                    {
                        'name': 'test-project',
                        'path': temp_dir,
                        'description': 'Test project'
                    }
                ],
                'log_level': 'INFO',
                'data_dir': config_dir,
                'max_sessions': 10,
                'task_queue_size': 100
            }
            
            # Ensure config directory exists
            os.makedirs(config_dir, exist_ok=True)
            
            # Write configuration file
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            # Test loading the configuration
            config = load_config(config_file)
            
            # Verify configuration was loaded correctly
            assert config.slack_bot_token == 'xoxb-test-token-123'
            assert config.slack_channel_id == 'C1234567890'
            assert config.claude_cli_path == 'claude'
            assert len(config.projects) == 1
            assert config.projects[0]['name'] == 'test-project'
    
    @patch('sys.argv', ['claude-remote-client', '--setup', '--validate'])
    def test_setup_and_validate_workflow(self):
        """Test setup followed by validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, ".claude-remote-client")
            
            # Mock system requirements check
            with patch('claude_remote_client.cli.check_system_requirements') as mock_check:
                mock_check.return_value = (True, [])
                
                # Mock setup wizard
                with patch('claude_remote_client.cli.setup_wizard') as mock_setup:
                    config_file = os.path.join(config_dir, "config.yaml")
                    mock_setup.return_value = config_file
                    
                    # Create a minimal config file for validation
                    os.makedirs(config_dir, exist_ok=True)
                    config_data = {
                        'slack': {'bot_token': 'xoxb-test', 'channel_id': 'C123'},
                        'claude': {'cli_path': 'claude', 'default_args': ['--dangerously-skip-permissions']},
                        'projects': [],
                        'data_dir': config_dir
                    }
                    with open(config_file, 'w') as f:
                        yaml.dump(config_data, f)
                    
                    # Run main CLI
                    main()
                    
                    # Verify setup wizard was called
                    mock_setup.assert_called_once()
    
    def test_cli_entry_point_exists(self):
        """Test that the CLI entry point is properly configured."""
        # This test verifies that the setup.py entry point is correctly configured
        # by attempting to import the main function
        try:
            from claude_remote_client.cli import main
            assert callable(main)
        except ImportError:
            pytest.fail("CLI entry point not properly configured")
    
    def test_package_dependencies_available(self):
        """Test that all required dependencies are available."""
        required_packages = [
            'slack_sdk',
            'yaml',
            'asyncio',
        ]
        
        for package in required_packages:
            try:
                if package == 'yaml':
                    import yaml
                elif package == 'slack_sdk':
                    import slack_sdk
                elif package == 'asyncio':
                    import asyncio
            except ImportError:
                pytest.fail(f"Required package '{package}' not available")


class TestSystemRequirementsValidation:
    """Integration tests for system requirements validation."""
    
    @patch('subprocess.run')
    def test_claude_cli_detection_success(self, mock_run):
        """Test successful Claude CLI detection."""
        # Mock successful Claude CLI execution
        mock_run.return_value.returncode = 0
        
        requirements_met, issues = check_system_requirements()
        
        # Should pass if Claude CLI is available
        assert requirements_met is True
        assert len(issues) == 0
    
    @patch('subprocess.run')
    def test_claude_cli_detection_failure(self, mock_run):
        """Test failed Claude CLI detection."""
        # Mock failed Claude CLI execution
        mock_run.side_effect = FileNotFoundError()
        
        requirements_met, issues = check_system_requirements()
        
        # Should fail if Claude CLI is not available
        assert requirements_met is False
        assert any("Claude CLI not found" in issue for issue in issues)
    
    def test_python_version_check(self):
        """Test Python version requirement check."""
        # This test runs in the current Python environment
        # If we're running the tests, Python version should be adequate
        requirements_met, issues = check_system_requirements()
        
        # Should not have Python version issues in test environment
        python_version_issues = [issue for issue in issues if "Python" in issue and "required" in issue]
        assert len(python_version_issues) == 0


class TestConfigurationManagement:
    """Integration tests for configuration management."""
    
    def test_config_file_creation_and_loading(self):
        """Test creating and loading configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "test_config.yaml")
            
            # Create test configuration
            config_data = {
                'slack': {
                    'bot_token': 'xoxb-test-token',
                    'channel_id': 'C1234567890'
                },
                'claude': {
                    'cli_path': 'claude',
                    'default_args': ['--dangerously-skip-permissions']
                },
                'projects': [
                    {
                        'name': 'test-project',
                        'path': '/tmp/test',
                        'description': 'Test project'
                    }
                ],
                'data_dir': temp_dir
            }
            
            # Write configuration
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            # Load configuration
            config = load_config(config_file)
            
            # Verify configuration
            assert config.slack_bot_token == 'xoxb-test-token'
            assert config.slack_channel_id == 'C1234567890'
            assert config.claude_cli_path == 'claude'
            assert len(config.projects) == 1
            assert config.projects[0]['name'] == 'test-project'
    
    def test_invalid_config_handling(self):
        """Test handling of invalid configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "invalid_config.yaml")
            
            # Create invalid configuration (missing required fields)
            config_data = {
                'slack': {
                    'bot_token': 'xoxb-test-token'
                    # Missing channel_id
                },
                'claude': {
                    # Missing cli_path
                }
            }
            
            # Write invalid configuration
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            # Loading should raise ConfigurationError
            with pytest.raises(ConfigurationError):
                load_config(config_file)
    
    def test_default_config_location(self):
        """Test default configuration file location handling."""
        # Test that load_config handles default location properly
        with patch('os.path.expanduser') as mock_expanduser:
            with patch('os.path.exists') as mock_exists:
                mock_expanduser.return_value = "/tmp/.claude-remote-client"
                mock_exists.return_value = False
                
                # Should raise ConfigurationError when default config doesn't exist
                with pytest.raises(ConfigurationError):
                    load_config(None)


class TestCLICommandIntegration:
    """Integration tests for CLI command functionality."""
    
    @patch('sys.argv', ['claude-remote-client', '--help'])
    def test_help_command(self):
        """Test help command functionality."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # argparse exits with code 0 for --help
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['claude-remote-client', '--version'])
    def test_version_command(self):
        """Test version command functionality."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # argparse exits with code 0 for --version
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['claude-remote-client', '--log-level', 'DEBUG'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.start_bot')
    @patch('asyncio.run')
    def test_log_level_argument(self, mock_asyncio, mock_start_bot, mock_load_config):
        """Test log level argument functionality."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.data_dir = "/tmp/test"
        mock_load_config.return_value = mock_config
        
        with patch('claude_remote_client.utils.setup_logging') as mock_setup_logging:
            with patch('claude_remote_client.utils.ensure_directory_exists'):
                main()
                
                # Verify logging was set up with DEBUG level
                mock_setup_logging.assert_called_once()
                args, kwargs = mock_setup_logging.call_args
                assert args[0] == 'DEBUG'
    
    @patch('sys.argv', ['claude-remote-client', '--config', '/custom/config.yaml'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.start_bot')
    @patch('asyncio.run')
    def test_custom_config_argument(self, mock_asyncio, mock_start_bot, mock_load_config):
        """Test custom config file argument."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.data_dir = "/tmp/test"
        mock_load_config.return_value = mock_config
        
        with patch('claude_remote_client.utils.setup_logging'):
            with patch('claude_remote_client.utils.ensure_directory_exists'):
                main()
                
                # Verify load_config was called with custom path
                mock_load_config.assert_called_once_with('/custom/config.yaml')