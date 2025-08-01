"""
Integration tests for CLI functionality.
"""

import pytest
import tempfile
import os
import subprocess
import yaml
from unittest.mock import patch, MagicMock
from pathlib import Path

from claude_remote_client.cli import (
    setup_wizard, main, validate_claude_cli, check_system_requirements
)
from claude_remote_client.config import Config
from claude_remote_client.exceptions import ConfigurationError


class TestCLIFunctions:
    """Test cases for CLI utility functions."""
    
    @patch('subprocess.run')
    def test_validate_claude_cli_success(self, mock_run):
        """Test successful Claude CLI validation."""
        mock_run.return_value.returncode = 0
        
        result = validate_claude_cli()
        
        assert result is True
        mock_run.assert_called_once_with(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_validate_claude_cli_failure(self, mock_run):
        """Test failed Claude CLI validation."""
        mock_run.return_value.returncode = 1
        
        result = validate_claude_cli()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_validate_claude_cli_not_found(self, mock_run):
        """Test Claude CLI not found."""
        mock_run.side_effect = FileNotFoundError()
        
        result = validate_claude_cli()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_validate_claude_cli_timeout(self, mock_run):
        """Test Claude CLI validation timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 10)
        
        result = validate_claude_cli()
        
        assert result is False
    
    @patch('claude_remote_client.cli.validate_claude_cli')
    @patch('claude_remote_client.utils.ensure_directory_exists')
    def test_check_system_requirements_success(self, mock_ensure_dir, mock_validate_claude):
        """Test successful system requirements check."""
        mock_validate_claude.return_value = True
        
        requirements_met, issues = check_system_requirements()
        
        assert requirements_met is True
        assert len(issues) == 0
    
    @patch('claude_remote_client.cli.validate_claude_cli')
    def test_check_system_requirements_claude_missing(self, mock_validate_claude):
        """Test system requirements check with missing Claude CLI."""
        mock_validate_claude.return_value = False
        
        requirements_met, issues = check_system_requirements()
        
        assert requirements_met is False
        assert any("Claude CLI not found" in issue for issue in issues)
    
    @patch('claude_remote_client.cli.validate_claude_cli')
    @patch('claude_remote_client.cli.ensure_directory_exists')
    @patch('os.rmdir')
    def test_check_system_requirements_directory_error(self, mock_rmdir, mock_ensure_dir, mock_validate_claude):
        """Test system requirements check with directory creation error."""
        mock_validate_claude.return_value = True
        mock_ensure_dir.side_effect = PermissionError("Permission denied")
        
        requirements_met, issues = check_system_requirements()
        
        assert requirements_met is False
        assert any("Cannot create configuration directory" in issue for issue in issues)


class TestSetupWizard:
    """Test cases for the setup wizard."""
    
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('claude_remote_client.cli.check_system_requirements')
    @patch('subprocess.run')
    def test_setup_wizard_basic(self, mock_subprocess, mock_check_requirements, mock_exists, mock_input):
        """Test basic setup wizard flow."""
        # Mock system requirements check
        mock_check_requirements.return_value = (True, [])
        
        # Mock Claude CLI validation
        mock_subprocess.return_value.returncode = 0
        
        # Mock user inputs
        mock_input.side_effect = [
            "xoxb-test-token-123",  # Slack bot token
            "C1234567890",          # Slack channel ID
            "",                     # Signing secret (optional)
            "claude",               # Claude CLI path
            "",                     # No projects (finish)
        ]
        
        # Mock path existence check
        mock_exists.return_value = False  # Config doesn't exist yet
        
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
    @patch('claude_remote_client.cli.check_system_requirements')
    @patch('subprocess.run')
    @patch('claude_remote_client.utils.validate_project_path')
    def test_setup_wizard_with_projects(self, mock_validate_path, mock_subprocess, mock_check_requirements, mock_expanduser, mock_exists, mock_input):
        """Test setup wizard with project configuration."""
        # Mock system requirements check
        mock_check_requirements.return_value = (True, [])
        
        # Mock Claude CLI validation
        mock_subprocess.return_value.returncode = 0
        
        # Mock project path validation
        mock_validate_path.return_value = True
        
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
        mock_exists.return_value = False  # Config doesn't exist yet
        
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
            assert config_data['projects'][1]['description'] == 'Development project: project2'
    
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
    
    @patch('builtins.input')
    @patch('claude_remote_client.cli.check_system_requirements')
    @patch('sys.exit')
    def test_setup_wizard_system_requirements_failure(self, mock_exit, mock_check_requirements, mock_input):
        """Test setup wizard with failed system requirements."""
        # Mock system requirements check failure
        mock_check_requirements.return_value = (False, ["Claude CLI not found", "Python version too old"])
        
        setup_wizard()
        
        mock_exit.assert_called_once_with(1)
    
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('claude_remote_client.cli.check_system_requirements')
    def test_setup_wizard_config_exists_overwrite_no(self, mock_check_requirements, mock_exists, mock_input):
        """Test setup wizard when config exists and user chooses not to overwrite."""
        # Mock system requirements check
        mock_check_requirements.return_value = (True, [])
        
        # Mock config file exists
        mock_exists.return_value = True
        
        # Mock user input - don't overwrite
        mock_input.side_effect = ["n"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.path.expanduser') as mock_expanduser:
                config_dir = os.path.join(temp_dir, ".claude-remote-client")
                config_file = os.path.join(config_dir, "config.yaml")
                mock_expanduser.return_value = config_dir
                
                result = setup_wizard()
                
                # Should return the config file path even if not overwritten
                assert result == config_file
    
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('claude_remote_client.cli.check_system_requirements')
    @patch('subprocess.run')
    def test_setup_wizard_empty_required_fields(self, mock_subprocess, mock_check_requirements, mock_exists, mock_input):
        """Test setup wizard with empty required fields."""
        # Mock system requirements check
        mock_check_requirements.return_value = (True, [])
        
        # Mock Claude CLI validation
        mock_subprocess.return_value.returncode = 0
        
        # Mock user inputs with empty required fields first
        mock_input.side_effect = [
            "",                     # Empty bot token
            "xoxb-test-token-123",  # Valid bot token
            "",                     # Empty channel ID
            "C1234567890",          # Valid channel ID
            "",                     # Signing secret (optional)
            "claude",               # Claude CLI path
            "project1",             # Project name
            "",                     # Empty project path
            "/home/user/project1",  # Valid project path
            "Test project",         # Project description
            "",                     # No more projects
        ]
        
        # Mock path existence check
        mock_exists.return_value = False
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.path.expanduser') as mock_expanduser:
                config_dir = os.path.join(temp_dir, ".claude-remote-client")
                mock_expanduser.return_value = config_dir
                
                with patch('claude_remote_client.utils.validate_project_path', return_value=True):
                    config_file = setup_wizard()
                
                # Load and verify config
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                assert config_data['slack']['bot_token'] == 'xoxb-test-token-123'
                assert config_data['slack']['channel_id'] == 'C1234567890'
                assert len(config_data['projects']) == 1


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
    
    @patch('sys.argv', ['claude-remote-client', '--check'])
    @patch('claude_remote_client.cli.check_system_requirements')
    def test_main_check_success(self, mock_check_requirements):
        """Test check argument with successful requirements."""
        mock_check_requirements.return_value = (True, [])
        
        main()
        
        mock_check_requirements.assert_called_once()
    
    @patch('sys.argv', ['claude-remote-client', '--check'])
    @patch('claude_remote_client.cli.check_system_requirements')
    @patch('sys.exit')
    def test_main_check_failure(self, mock_exit, mock_check_requirements):
        """Test check argument with failed requirements."""
        mock_check_requirements.return_value = (False, ["Claude CLI not found"])
        
        main()
        
        mock_check_requirements.assert_called_once()
        mock_exit.assert_called_once_with(1)
    
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