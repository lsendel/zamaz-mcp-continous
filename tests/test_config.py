"""
Unit tests for configuration management.
"""

import pytest
import tempfile
import os
import yaml
import subprocess
import shutil
from pathlib import Path

from claude_remote_client.config import (
    Config, SlackConfig, ClaudeConfig, ProjectConfig,
    load_config, create_default_config_file, _merge_config_data, _load_env_overrides
)
from claude_remote_client.exceptions import ConfigurationError


class TestSlackConfig:
    """Test cases for SlackConfig."""
    
    def test_slack_config_creation(self):
        """Test basic SlackConfig creation."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            channel_id="C1234567890",
            signing_secret="test-secret"
        )
        
        assert config.bot_token == "xoxb-test-token"
        assert config.channel_id == "C1234567890"
        assert config.signing_secret == "test-secret"


class TestClaudeConfig:
    """Test cases for ClaudeConfig."""
    
    def test_claude_config_creation(self):
        """Test basic ClaudeConfig creation."""
        config = ClaudeConfig(
            cli_path="/usr/local/bin/claude",
            timeout=600
        )
        
        assert config.cli_path == "/usr/local/bin/claude"
        assert config.default_args == ["--dangerously-skip-permissions"]
        assert config.timeout == 600


class TestProjectConfig:
    """Test cases for ProjectConfig."""
    
    def test_project_config_creation(self):
        """Test basic ProjectConfig creation."""
        config = ProjectConfig(
            name="test-project",
            path="/home/user/projects/test",
            description="A test project"
        )
        
        assert config.name == "test-project"
        assert config.path == "/home/user/projects/test"
        assert config.description == "A test project"


class TestConfig:
    """Test cases for main Config class."""
    
    def test_config_creation(self):
        """Test basic Config creation with defaults."""
        config = Config()
        
        assert isinstance(config.slack, SlackConfig)
        assert isinstance(config.claude, ClaudeConfig)
        assert config.projects == []
        assert config.log_level == "INFO"
        assert config.max_sessions == 10
        assert config.task_queue_size == 100
    
    def test_config_post_init(self):
        """Test post-initialization path expansion."""
        config = Config(data_dir="~/test-dir")
        
        # Should expand the tilde
        assert config.data_dir == os.path.expanduser("~/test-dir")
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-test-token"
            config.slack.channel_id = "C1234567890"
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test project")
            ]
            
            # Should not raise any exception
            config.validate()
    
    def test_validate_missing_slack_token(self):
        """Test validation failure for missing Slack token."""
        config = Config()
        config.slack.channel_id = "C1234567890"
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        assert "Slack bot token is required" in str(exc_info.value)
    
    def test_validate_missing_channel_id(self):
        """Test validation failure for missing channel ID."""
        config = Config()
        config.slack.bot_token = "xoxb-test-token"
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        assert "Slack channel ID is required" in str(exc_info.value)
    
    def test_validate_invalid_project_path(self):
        """Test validation failure for invalid project path."""
        config = Config()
        config.slack.bot_token = "xoxb-test-token"
        config.slack.channel_id = "C1234567890"
        config.projects = [
            ProjectConfig(name="test", path="/nonexistent/path", description="Test")
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        assert "path does not exist" in str(exc_info.value)
    
    def test_validate_invalid_numeric_values(self):
        """Test validation failure for invalid numeric values."""
        config = Config()
        config.slack.bot_token = "xoxb-test-token"
        config.slack.channel_id = "C1234567890"
        config.max_sessions = -1
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        assert "max_sessions must be positive" in str(exc_info.value)
    
    def test_get_project_by_name(self):
        """Test getting project by name."""
        config = Config()
        config.projects = [
            ProjectConfig(name="project1", path="/path1"),
            ProjectConfig(name="project2", path="/path2")
        ]
        
        project = config.get_project_by_name("project1")
        assert project is not None
        assert project.name == "project1"
        assert project.path == "/path1"
        
        # Non-existent project
        project = config.get_project_by_name("nonexistent")
        assert project is None
    
    def test_get_project_names(self):
        """Test getting list of project names."""
        config = Config()
        config.projects = [
            ProjectConfig(name="project1", path="/path1"),
            ProjectConfig(name="project2", path="/path2")
        ]
        
        names = config.get_project_names()
        assert names == ["project1", "project2"]
    
    def test_validate_claude_cli_not_found(self):
        """Test Claude CLI validation when CLI is not found."""
        config = Config()
        config.claude.cli_path = "nonexistent-claude-cli"
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate_claude_cli()
        
        assert "Claude CLI not found" in str(exc_info.value)
    
    def test_validate_claude_cli_success(self, monkeypatch):
        """Test successful Claude CLI validation."""
        import subprocess
        
        # Mock shutil.which to return a path
        def mock_which(cmd):
            return "/usr/local/bin/claude" if cmd == "claude" else None
        
        # Mock subprocess.run to return success
        def mock_run(*args, **kwargs):
            class MockResult:
                returncode = 0
                stderr = ""
            return MockResult()
        
        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr("subprocess.run", mock_run)
        
        config = Config()
        config.claude.cli_path = "claude"
        
        # Should not raise any exception
        result = config.validate_claude_cli()
        assert result is True
    
    def test_validate_claude_cli_error_code(self, monkeypatch):
        """Test Claude CLI validation when CLI returns error code."""
        import subprocess
        
        # Mock shutil.which to return a path
        def mock_which(cmd):
            return "/usr/local/bin/claude" if cmd == "claude" else None
        
        # Mock subprocess.run to return error
        def mock_run(*args, **kwargs):
            class MockResult:
                returncode = 1
                stderr = "Command not found"
            return MockResult()
        
        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr("subprocess.run", mock_run)
        
        config = Config()
        config.claude.cli_path = "claude"
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate_claude_cli()
        
        assert "returned error code 1" in str(exc_info.value)
    
    def test_validate_claude_cli_timeout(self, monkeypatch):
        """Test Claude CLI validation when CLI times out."""
        import subprocess
        
        # Mock shutil.which to return a path
        def mock_which(cmd):
            return "/usr/local/bin/claude" if cmd == "claude" else None
        
        # Mock subprocess.run to raise TimeoutExpired
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("claude", 10)
        
        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr("subprocess.run", mock_run)
        
        config = Config()
        config.claude.cli_path = "claude"
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate_claude_cli()
        
        assert "timed out" in str(exc_info.value)


class TestConfigLoading:
    """Test cases for configuration loading functions."""
    
    def test_load_config_no_file(self):
        """Test loading config when no file exists."""
        # Should create default config but fail validation due to missing required fields
        with pytest.raises(ConfigurationError):
            load_config("/nonexistent/config.yaml")
    
    def test_load_config_from_yaml(self):
        """Test loading config from YAML file."""
        config_data = {
            'slack': {
                'bot_token': 'xoxb-test-token',
                'channel_id': 'C1234567890'
            },
            'claude': {
                'cli_path': '/usr/local/bin/claude',
                'timeout': 600
            },
            'projects': [
                {
                    'name': 'test-project',
                    'path': tempfile.gettempdir(),  # Use temp dir that exists
                    'description': 'Test project'
                }
            ],
            'log_level': 'DEBUG',
            'max_sessions': 5
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name
        
        try:
            config = load_config(config_file)
            
            assert config.slack.bot_token == 'xoxb-test-token'
            assert config.slack.channel_id == 'C1234567890'
            assert config.claude.cli_path == '/usr/local/bin/claude'
            assert config.claude.timeout == 600
            assert len(config.projects) == 1
            assert config.projects[0].name == 'test-project'
            assert config.log_level == 'DEBUG'
            assert config.max_sessions == 5
        
        finally:
            os.unlink(config_file)
    
    def test_load_config_with_env_overrides(self, monkeypatch):
        """Test loading config with environment variable overrides."""
        # Set environment variables with valid formats
        monkeypatch.setenv('SLACK_BOT_TOKEN', 'xoxb-env-bot-token')
        monkeypatch.setenv('SLACK_CHANNEL_ID', 'C1234567890')
        monkeypatch.setenv('LOG_LEVEL', 'ERROR')
        monkeypatch.setenv('MAX_SESSIONS', '20')
        
        config_data = {
            'slack': {
                'bot_token': 'xoxb-yaml-bot-token',
                'channel_id': 'C0987654321'
            },
            'projects': [
                {
                    'name': 'test-project',
                    'path': tempfile.gettempdir(),
                    'description': 'Test project'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name
        
        try:
            config = load_config(config_file)
            
            # Environment variables should override YAML values
            assert config.slack.bot_token == 'xoxb-env-bot-token'
            assert config.slack.channel_id == 'C1234567890'
            assert config.log_level == 'ERROR'
            assert config.max_sessions == 20
        
        finally:
            os.unlink(config_file)
    
    def test_merge_config_data(self):
        """Test merging YAML data into config object."""
        config = Config()
        
        data = {
            'slack': {
                'bot_token': 'test-token',
                'channel_id': 'test-channel'
            },
            'claude': {
                'cli_path': '/test/claude',
                'timeout': 900
            },
            'projects': [
                {
                    'name': 'project1',
                    'path': '/path1',
                    'description': 'Project 1'
                }
            ],
            'log_level': 'WARNING',
            'max_sessions': 15
        }
        
        merged_config = _merge_config_data(config, data)
        
        assert merged_config.slack.bot_token == 'test-token'
        assert merged_config.slack.channel_id == 'test-channel'
        assert merged_config.claude.cli_path == '/test/claude'
        assert merged_config.claude.timeout == 900
        assert len(merged_config.projects) == 1
        assert merged_config.projects[0].name == 'project1'
        assert merged_config.log_level == 'WARNING'
        assert merged_config.max_sessions == 15
    
    def test_load_env_overrides(self, monkeypatch):
        """Test loading environment variable overrides."""
        config = Config()
        
        # Set environment variables
        monkeypatch.setenv('SLACK_BOT_TOKEN', 'xoxb-env-token')
        monkeypatch.setenv('CLAUDE_CLI_PATH', '/env/claude')
        monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
        monkeypatch.setenv('MAX_SESSIONS', '25')
        monkeypatch.setenv('INVALID_NUMBER', 'not-a-number')  # Should be ignored
        
        config_with_env = _load_env_overrides(config)
        
        assert config_with_env.slack.bot_token == 'xoxb-env-token'
        assert config_with_env.claude.cli_path == '/env/claude'
        assert config_with_env.log_level == 'DEBUG'
        assert config_with_env.max_sessions == 25
    
    def test_create_default_config_file(self):
        """Test creating default configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, 'config.yaml')
            
            create_default_config_file(config_file)
            
            assert os.path.exists(config_file)
            
            # Load and verify the created config
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
            
            assert 'slack' in data
            assert 'claude' in data
            assert 'projects' in data
            assert data['slack']['bot_token'] == 'xoxb-your-bot-token-here'
            assert data['claude']['cli_path'] == 'claude'
            assert len(data['projects']) == 1
    
    def test_load_config_invalid_yaml(self):
        """Test loading config with invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            config_file = f.name
        
        try:
            with pytest.raises(ConfigurationError) as exc_info:
                load_config(config_file)
            
            assert "Failed to load config file" in str(exc_info.value)
        
        finally:
            os.unlink(config_file)
    
    def test_load_config_empty_yaml(self):
        """Test loading config with empty YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")  # Empty file
            config_file = f.name
        
        try:
            # Should create default config but fail validation
            with pytest.raises(ConfigurationError):
                load_config(config_file)
        
        finally:
            os.unlink(config_file)
    
    def test_load_env_overrides_invalid_numbers(self, monkeypatch):
        """Test that invalid numeric environment variables are ignored."""
        config = Config()
        config.max_sessions = 10  # Set initial value
        config.task_queue_size = 100  # Set initial value
        config.claude.timeout = 300  # Set initial value
        
        # Set invalid numeric environment variables
        monkeypatch.setenv('MAX_SESSIONS', 'not-a-number')
        monkeypatch.setenv('TASK_QUEUE_SIZE', 'invalid')
        monkeypatch.setenv('CLAUDE_TIMEOUT', 'bad-timeout')
        
        config_with_env = _load_env_overrides(config)
        
        # Values should remain unchanged due to invalid env vars
        assert config_with_env.max_sessions == 10
        assert config_with_env.task_queue_size == 100
        assert config_with_env.claude.timeout == 300
    
    def test_config_validate_multiple_errors(self):
        """Test validation with multiple errors."""
        config = Config()
        # Leave all required fields empty and set invalid values
        config.max_sessions = -1
        config.task_queue_size = 0
        config.projects = [
            ProjectConfig(name="", path="", description=""),  # Missing name and path
            ProjectConfig(name="test", path="/nonexistent", description="")  # Invalid path
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()
        
        error_message = str(exc_info.value)
        # Should contain multiple error messages
        assert "Slack bot token is required" in error_message
        assert "Slack channel ID is required" in error_message
        assert "max_sessions must be positive" in error_message
        assert "task_queue_size must be positive" in error_message
        assert "Project 0 name is required" in error_message
        assert "Project 0 path is required" in error_message
        assert "Project 1 path does not exist" in error_message
    
    def test_config_project_path_expansion(self):
        """Test that project paths are expanded during post-init."""
        config = Config()
        config.projects = [
            ProjectConfig(name="test", path="~/test-project", description="Test")
        ]
        
        # Trigger post-init
        config.__post_init__()
        
        # Path should be expanded
        assert config.projects[0].path == os.path.expanduser("~/test-project")
    
    def test_merge_config_data_partial(self):
        """Test merging partial configuration data."""
        config = Config()
        config.slack.bot_token = "original-token"
        config.claude.timeout = 300
        
        # Only provide partial data
        data = {
            'slack': {
                'channel_id': 'new-channel'
                # bot_token not provided, should keep original
            },
            'claude': {
                'timeout': 600
                # cli_path not provided, should keep original
            }
        }
        
        merged_config = _merge_config_data(config, data)
        
        # Should merge new values while keeping existing ones
        assert merged_config.slack.bot_token == "original-token"  # Kept original
        assert merged_config.slack.channel_id == "new-channel"    # New value
        assert merged_config.claude.cli_path == "claude"          # Kept original
        assert merged_config.claude.timeout == 600               # New value
    
    def test_validate_slack_token_format(self):
        """Test validation of Slack token format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "invalid-token-format"
            config.slack.channel_id = "C1234567890"
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test project")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "must start with 'xoxb-' or 'xoxp-'" in str(exc_info.value)
    
    def test_validate_channel_id_format(self):
        """Test validation of Slack channel ID format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "invalid-channel-id"
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test project")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "must start with 'C'" in str(exc_info.value)
    
    def test_validate_duplicate_project_names(self):
        """Test validation of duplicate project names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.projects = [
                ProjectConfig(name="duplicate", path=temp_dir, description="First"),
                ProjectConfig(name="duplicate", path=temp_dir, description="Second")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "is duplicated" in str(exc_info.value)
    
    def test_validate_project_not_directory(self):
        """Test validation when project path is not a directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.projects = [
                ProjectConfig(name="test", path=temp_file.name, description="Test")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "is not a directory" in str(exc_info.value)
    
    def test_validate_claude_timeout_negative(self):
        """Test validation of negative Claude timeout."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.claude.timeout = -1
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Claude timeout must be positive" in str(exc_info.value)
    
    def test_validate_max_sessions_limits(self):
        """Test validation of max_sessions limits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.max_sessions = 150  # Too high
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "should not exceed 100" in str(exc_info.value)
    
    def test_validate_task_queue_size_limits(self):
        """Test validation of task_queue_size limits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.task_queue_size = 15000  # Too high
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "should not exceed 10000" in str(exc_info.value)
    
    def test_validate_invalid_log_level(self):
        """Test validation of invalid log level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config()
            config.slack.bot_token = "xoxb-valid-token"
            config.slack.channel_id = "C1234567890"
            config.log_level = "INVALID_LEVEL"
            config.projects = [
                ProjectConfig(name="test", path=temp_dir, description="Test")
            ]
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "log_level must be one of" in str(exc_info.value)