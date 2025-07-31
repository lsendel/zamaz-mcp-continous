"""
Configuration management for the Claude Remote Client.

This module handles loading, validation, and management of application
configuration from YAML files and environment variables.
"""

import os
import yaml
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from .exceptions import ConfigurationError


@dataclass
class SlackConfig:
    """Slack-specific configuration."""
    bot_token: str = ""
    app_token: str = ""
    channel_id: str = ""
    signing_secret: str = ""


@dataclass
class ClaudeConfig:
    """Claude CLI configuration."""
    cli_path: str = "claude"
    default_args: List[str] = field(default_factory=lambda: ["--dangerously-skip-permissions"])
    timeout: int = 300  # 5 minutes default timeout


@dataclass
class ProjectConfig:
    """Project configuration."""
    name: str = ""
    path: str = ""
    description: str = ""


@dataclass
class Config:
    """Main application configuration."""
    slack: SlackConfig = field(default_factory=SlackConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    projects: List[ProjectConfig] = field(default_factory=list)
    log_level: str = "INFO"
    data_dir: str = "~/.claude-remote-client"
    max_sessions: int = 10
    task_queue_size: int = 100
    
    def __post_init__(self):
        """Post-initialization to expand paths."""
        self.data_dir = os.path.expanduser(self.data_dir)
        
        # Expand project paths
        for project in self.projects:
            project.path = os.path.expanduser(project.path)
    
    def validate(self) -> None:
        """Validate configuration and raise ConfigurationError if invalid."""
        errors = []
        
        # Validate Slack configuration
        if not self.slack.bot_token:
            errors.append("Slack bot token is required")
        elif not self.slack.bot_token.startswith(('xoxb-', 'xoxp-')):
            errors.append("Slack bot token must start with 'xoxb-' or 'xoxp-'")
        
        if not self.slack.channel_id:
            errors.append("Slack channel ID is required")
        elif not self.slack.channel_id.startswith('C'):
            errors.append("Slack channel ID must start with 'C'")
        
        # Validate Claude configuration
        if not self.claude.cli_path:
            errors.append("Claude CLI path is required")
        
        if self.claude.timeout <= 0:
            errors.append("Claude timeout must be positive")
        
        # Validate projects
        project_names = set()
        for i, project in enumerate(self.projects):
            if not project.name:
                errors.append(f"Project {i} name is required")
            elif project.name in project_names:
                errors.append(f"Project {i} name '{project.name}' is duplicated")
            else:
                project_names.add(project.name)
            
            if not project.path:
                errors.append(f"Project {i} path is required")
            elif not os.path.exists(project.path):
                errors.append(f"Project {i} path does not exist: {project.path}")
            elif not os.path.isdir(project.path):
                errors.append(f"Project {i} path is not a directory: {project.path}")
        
        # Validate numeric values
        if self.max_sessions <= 0:
            errors.append("max_sessions must be positive")
        elif self.max_sessions > 100:
            errors.append("max_sessions should not exceed 100 for performance reasons")
        
        if self.task_queue_size <= 0:
            errors.append("task_queue_size must be positive")
        elif self.task_queue_size > 10000:
            errors.append("task_queue_size should not exceed 10000 for memory reasons")
        
        # Validate log level
        valid_log_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.log_level not in valid_log_levels:
            errors.append(f"log_level must be one of: {', '.join(valid_log_levels)}")
        
        if errors:
            raise ConfigurationError("Configuration validation failed", "; ".join(errors))
    
    def get_project_by_name(self, name: str) -> Optional[ProjectConfig]:
        """Get project configuration by name."""
        for project in self.projects:
            if project.name == name:
                return project
        return None
    
    def get_project_names(self) -> List[str]:
        """Get list of all project names."""
        return [project.name for project in self.projects]
    
    def validate_claude_cli(self) -> bool:
        """
        Validate that Claude CLI is available and working.
        
        Returns:
            bool: True if Claude CLI is available and working.
        
        Raises:
            ConfigurationError: If Claude CLI is not available or not working.
        """
        # Check if Claude CLI is in PATH
        if not shutil.which(self.claude.cli_path):
            raise ConfigurationError(
                f"Claude CLI not found at '{self.claude.cli_path}'. "
                "Please ensure Claude CLI is installed and in your PATH."
            )
        
        # Try to run Claude CLI with --version to verify it works
        try:
            result = subprocess.run(
                [self.claude.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise ConfigurationError(
                    f"Claude CLI at '{self.claude.cli_path}' returned error code {result.returncode}. "
                    f"Error: {result.stderr}"
                )
            
            return True
            
        except subprocess.TimeoutExpired:
            raise ConfigurationError(
                f"Claude CLI at '{self.claude.cli_path}' timed out. "
                "Please check your Claude CLI installation."
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to validate Claude CLI at '{self.claude.cli_path}': {str(e)}"
            )


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file and environment variables.
    
    Args:
        config_path: Path to configuration file. If None, uses default locations.
    
    Returns:
        Config: Loaded and validated configuration.
    
    Raises:
        ConfigurationError: If configuration cannot be loaded or is invalid.
    """
    config = Config()
    
    # Determine config file path
    if config_path is None:
        # Try default locations
        possible_paths = [
            "claude-remote-client.yaml",
            "~/.claude-remote-client/config.yaml",
            "/etc/claude-remote-client/config.yaml"
        ]
        
        config_path = None
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                config_path = expanded_path
                break
    
    # Load from YAML file if it exists
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
            
            if yaml_data:
                config = _merge_config_data(config, yaml_data)
        
        except Exception as e:
            raise ConfigurationError(f"Failed to load config file {config_path}", str(e))
    
    # Override with environment variables
    config = _load_env_overrides(config)
    
    # Validate configuration
    config.validate()
    
    return config


def _merge_config_data(config: Config, data: Dict[str, Any]) -> Config:
    """Merge YAML data into configuration object."""
    
    # Slack configuration
    if 'slack' in data:
        slack_data = data['slack']
        if 'bot_token' in slack_data:
            config.slack.bot_token = slack_data['bot_token']
        if 'app_token' in slack_data:
            config.slack.app_token = slack_data['app_token']
        if 'channel_id' in slack_data:
            config.slack.channel_id = slack_data['channel_id']
        if 'signing_secret' in slack_data:
            config.slack.signing_secret = slack_data['signing_secret']
    
    # Claude configuration
    if 'claude' in data:
        claude_data = data['claude']
        if 'cli_path' in claude_data:
            config.claude.cli_path = claude_data['cli_path']
        if 'default_args' in claude_data:
            config.claude.default_args = claude_data['default_args']
        if 'timeout' in claude_data:
            config.claude.timeout = claude_data['timeout']
    
    # Projects configuration
    if 'projects' in data:
        config.projects = []
        for project_data in data['projects']:
            project = ProjectConfig(
                name=project_data.get('name', ''),
                path=project_data.get('path', ''),
                description=project_data.get('description', '')
            )
            config.projects.append(project)
    
    # General configuration
    if 'log_level' in data:
        config.log_level = data['log_level']
    if 'data_dir' in data:
        config.data_dir = data['data_dir']
    if 'max_sessions' in data:
        config.max_sessions = data['max_sessions']
    if 'task_queue_size' in data:
        config.task_queue_size = data['task_queue_size']
    
    return config


def _load_env_overrides(config: Config) -> Config:
    """Load configuration overrides from environment variables."""
    
    # Slack environment variables
    slack_bot_token = os.getenv('SLACK_BOT_TOKEN')
    if slack_bot_token:
        config.slack.bot_token = slack_bot_token
    
    slack_app_token = os.getenv('SLACK_APP_TOKEN')
    if slack_app_token:
        config.slack.app_token = slack_app_token
    
    slack_channel_id = os.getenv('SLACK_CHANNEL_ID')
    if slack_channel_id:
        config.slack.channel_id = slack_channel_id
    
    slack_signing_secret = os.getenv('SLACK_SIGNING_SECRET')
    if slack_signing_secret:
        config.slack.signing_secret = slack_signing_secret
    
    # Claude environment variables
    claude_cli_path = os.getenv('CLAUDE_CLI_PATH')
    if claude_cli_path:
        config.claude.cli_path = claude_cli_path
    
    claude_timeout = os.getenv('CLAUDE_TIMEOUT')
    if claude_timeout:
        try:
            config.claude.timeout = int(claude_timeout)
        except ValueError:
            pass
    
    # General environment variables
    log_level = os.getenv('LOG_LEVEL')
    if log_level:
        config.log_level = log_level
    
    data_dir = os.getenv('DATA_DIR')
    if data_dir:
        config.data_dir = data_dir
    
    max_sessions = os.getenv('MAX_SESSIONS')
    if max_sessions:
        try:
            config.max_sessions = int(max_sessions)
        except ValueError:
            pass
    
    task_queue_size = os.getenv('TASK_QUEUE_SIZE')
    if task_queue_size:
        try:
            config.task_queue_size = int(task_queue_size)
        except ValueError:
            pass
    
    return config


def create_default_config_file(path: str) -> None:
    """Create a default configuration file at the specified path."""
    
    default_config = {
        'slack': {
            'bot_token': 'xoxb-your-bot-token-here',
            'channel_id': 'C1234567890',
            'signing_secret': 'your-signing-secret-here'
        },
        'claude': {
            'cli_path': 'claude',
            'default_args': ['--dangerously-skip-permissions'],
            'timeout': 300
        },
        'projects': [
            {
                'name': 'example-project',
                'path': '~/projects/example',
                'description': 'Example project configuration'
            }
        ],
        'log_level': 'INFO',
        'data_dir': '~/.claude-remote-client',
        'max_sessions': 10,
        'task_queue_size': 100
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, indent=2)