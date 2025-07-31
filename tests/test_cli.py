"""
Integration tests for CLI functionality.
"""

import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_remote_client.cli import (
    setup_wizard, create_data_directory, setup_logging, main
)
from claude_remote_client.config import Config
from claude_remote_client.exceptions import ConfigurationError


class TestCLIFunctions:
    """Test cases for CLI utility functions."""
    
    def test_create_data_directory(self):
        """Test creating data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = os.path.join(temp_dir, "test_data")
            
            # Directory should not exist initially
            assert not os.path.exists(data_dir)
            
            # Create directory
            create_data_directory(data_dir)
            
            # Directory should now exist
            assert os.path.exists(data_dir)
            assert os.path.isdir(data_dir)
    
    def test_create_data_directory_nested(self):
        """Test creating nested data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = os.path.join(temp_dir, "nested", "test_data")
            
            # Create nested directory
            create_data_directory(data_dir)
            
            # Directory should exist
            assert os.path.exists(data_dir)
            assert os.path.isdir(data_dir)
    
    def test_setup_logging(self):
        """Test logging setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock expanduser to use temp directory
            with patch('os.path.expanduser') as mock_expanduser:
                log_dir = os.path.join(temp_dir, ".claude-remote-client")
                mock_expanduser.return_value = log_dir
                
                # Should not raise any exception
                setup_logging("DEBUG")
                
                # Verify log directory was created
                assert os.path.exists(log_dir)
                
                # Verify log file was created
                log_file = os.path.join(log_dir, "claude-remote-client.log")
                assert os.path.exists(log_file)


class TestSetupWizard:
    """Test cases for the setup wizard."""
    
    @patch('builtins.input')
    @patch('os.path.exists')
    def test_setup_wizard_basic(self, mock_exists, mock_input):
        """Test basic setup wizard flow."""
        # Mock user inputs
        mock_input.side_effect = [
            "xoxb-test-token-123",  # Slack bot token
            "C1234567890",          # Slack channel ID
            "",                     # Signing secret (optional)
            "claude",               # Claude CLI path
            "",                     # No projects (finish)
        ]
        
        # Mock path existence check
        mock_exists.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.path.expanduser') as mock_expanduser:
                config_dir = os.path.join(temp_dir, ".claude-remote-client")
                mock_expanduser.return_value = config_dir
                
                config_file = setup_wizard()
                
                # Check that config file was created
                assert os.path.exists(config_file)
                
                # Load and verify config
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                assert config_data['slack']['bot_token'] == 'xoxb-test-token-123'
                assert config_data['slack']['channel_id'] == 'C1234567890'
                assert config_data['claude']['cli_path'] == 'claude'
                assert config_data['projects'] == []
    
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('os.path.expanduser')
    def test_setup_wizard_with_projects(self, mock_expanduser, mock_exists, mock_input):
        """Test setup wizard with project configuration."""
        # Mock user inputs
        mock_input.side_effect = [
            "xoxb-test-token-123",  # Slack bot token
            "C1234567890",          # Slack channel ID
            "test-signing-secret",  # Signing secret
            "/usr/local/bin/claude", # Claude CLI path
            "project1",             # Project name
            "/home/user/project1",  # Project path
            "Test project 1",       # Project description
            "project2",             # Project name
            "/home/user/project2",  # Project path
            "",                     # Project description (optional)
            "",                     # No more projects
        ]
        
        # Mock path existence check
        mock_exists.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, ".claude-remote-client")
            
            # Mock expanduser to return appropriate paths
            def mock_expanduser_side_effect(path):
                if path == "~/.claude-remote-client":
                    return config_dir
                else:
                    return path  # Return the path as-is for project paths
            
            mock_expanduser.side_effect = mock_expanduser_side_effect
            
            config_file = setup_wizard()
            
            # Load and verify config
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            assert len(config_data['projects']) == 2
            assert config_data['projects'][0]['name'] == 'project1'
            assert config_data['projects'][0]['path'] == '/home/user/project1'
            assert config_data['projects'][0]['description'] == 'Test project 1'
            assert config_data['projects'][1]['name'] == 'project2'
            assert config_data['projects'][1]['path'] == '/home/user/project2'
    
    @patch('builtins.input')
    @patch('os.path.exists')
    def test_setup_wizard_invalid_tokens(self, mock_exists, mock_input):
        """Test setup wizard with invalid token validation."""
        # Mock user inputs with invalid tokens first
        mock_input.side_effect = [
            "invalid-token",        # Invalid bot token
            "xoxb-valid-token",     # Valid bot token
            "invalid-channel",      # Invalid channel ID
            "C1234567890",          # Valid channel ID
            "",                     # Signing secret (optional)
            "claude",               # Claude CLI path
            "",                     # No projects
        ]
        
        mock_exists.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.path.expanduser') as mock_expanduser:
                config_dir = os.path.join(temp_dir, ".claude-remote-client")
                mock_expanduser.return_value = config_dir
                
                config_file = setup_wizard()
                
                # Load and verify config has valid tokens
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                assert config_data['slack']['bot_token'] == 'xoxb-valid-token'
                assert config_data['slack']['channel_id'] == 'C1234567890'
    
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('os.path.expanduser')
    def test_setup_wizard_nonexistent_project_path(self, mock_expanduser, mock_exists, mock_input):
        """Test setup wizard with nonexistent project path."""
        # Mock user inputs
        mock_input.side_effect = [
            "xoxb-test-token-123",  # Slack bot token
            "C1234567890",          # Slack channel ID
            "",                     # Signing secret (optional)
            "claude",               # Claude CLI path
            "project1",             # Project name
            "/nonexistent/path",    # Nonexistent project path
            "n",                    # Don't continue with nonexistent path
            "",                     # No more projects
        ]
        
        # Mock path existence check to return False for the project path
        def mock_exists_side_effect(path):
            return not path.endswith("/nonexistent/path")
        
        mock_exists.side_effect = mock_exists_side_effect
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, ".claude-remote-client")
            
            # Mock expanduser to return appropriate paths
            def mock_expanduser_side_effect(path):
                if path == "~/.claude-remote-client":
                    return config_dir
                else:
                    return path  # Return the path as-is for project paths
            
            mock_expanduser.side_effect = mock_expanduser_side_effect
            
            config_file = setup_wizard()
            
            # Load and verify config has no projects
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            assert config_data['projects'] == []


class TestMainCLI:
    """Test cases for main CLI function."""
    
    @patch('sys.argv', ['claude-remote-client', '--version'])
    def test_main_version(self):
        """Test version argument."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # argparse exits with code 0 for --version
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['claude-remote-client', '--setup'])
    @patch('claude_remote_client.cli.setup_wizard')
    def test_main_setup(self, mock_setup_wizard):
        """Test setup argument."""
        mock_setup_wizard.return_value = "/tmp/config.yaml"
        
        main()
        
        mock_setup_wizard.assert_called_once()
    
    @patch('sys.argv', ['claude-remote-client', '--validate'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.setup_logging')
    def test_main_validate_success(self, mock_setup_logging, mock_load_config):
        """Test validate argument with valid config."""
        # Mock config that validates successfully
        mock_config = MagicMock()
        mock_config.data_dir = "/tmp/test"
        mock_load_config.return_value = mock_config
        
        with patch('claude_remote_client.cli.create_data_directory'):
            main()
        
        mock_config.validate_claude_cli.assert_called_once()
        mock_setup_logging.assert_called_once_with("INFO")
    
    @patch('sys.argv', ['claude-remote-client', '--validate'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.setup_logging')
    @patch('sys.exit')
    def test_main_validate_failure(self, mock_exit, mock_setup_logging, mock_load_config):
        """Test validate argument with invalid config."""
        # Mock config that fails validation
        mock_config = MagicMock()
        mock_config.data_dir = "/tmp/test"
        mock_config.validate_claude_cli.side_effect = ConfigurationError("Test error")
        mock_load_config.return_value = mock_config
        
        with patch('claude_remote_client.cli.create_data_directory'):
            main()
        
        mock_exit.assert_called_once_with(1)
    
    @patch('sys.argv', ['claude-remote-client'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.start_bot')
    @patch('claude_remote_client.cli.setup_logging')
    @patch('asyncio.run')
    def test_main_start_bot(self, mock_asyncio_run, mock_setup_logging, mock_start_bot, mock_load_config):
        """Test starting the bot."""
        # Mock config
        mock_config = MagicMock()
        mock_config.data_dir = "/tmp/test"
        mock_load_config.return_value = mock_config
        
        with patch('claude_remote_client.cli.create_data_directory'):
            main()
        
        mock_asyncio_run.assert_called_once()
    
    @patch('sys.argv', ['claude-remote-client'])
    @patch('claude_remote_client.cli.load_config')
    @patch('claude_remote_client.cli.setup_logging')
    @patch('sys.exit')
    def test_main_config_error(self, mock_exit, mock_setup_logging, mock_load_config):
        """Test main with configuration error."""
        mock_load_config.side_effect = ConfigurationError("Test config error")
        
        main()
        
        mock_exit.assert_called_once_with(1)


class TestStartBot:
    """Test cases for bot startup."""
    
    @pytest.mark.asyncio
    async def test_start_bot_config_error(self):
        """Test bot startup with configuration error."""
        # Mock config that fails validation
        config = MagicMock()
        config.validate_claude_cli.side_effect = ConfigurationError("Claude CLI not found")
        
        # Import here to avoid circular import issues
        from claude_remote_client.cli import start_bot
        
        with pytest.raises(SystemExit):
            await start_bot(config)