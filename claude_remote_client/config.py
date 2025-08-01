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
from .yaml_env_loader import load_yaml_with_env


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
    
    # Handler configuration
    handler_type: str = "subprocess"  # "subprocess", "mcp", or "hybrid"
    
    # MCP-specific configuration
    mcp_server_uri: str = "mcp://localhost:8000"
    mcp_protocol_version: str = "1.0"
    mcp_timeout: int = 30
    
    # Hybrid mode configuration
    prefer_mcp: bool = True  # In hybrid mode, prefer MCP over subprocess
    fallback_to_subprocess: bool = True  # Fall back to subprocess if MCP fails


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
        if not self.claude.cli_path and self.claude.handler_type in ["subprocess", "hybrid"]:
            errors.append("Claude CLI path is required for subprocess and hybrid modes")
        
        if self.claude.timeout <= 0:
            errors.append("Claude timeout must be positive")
        
        # Validate handler type
        valid_handler_types = {"subprocess", "mcp", "hybrid"}
        if self.claude.handler_type not in valid_handler_types:
            errors.append(f"handler_type must be one of: {', '.join(valid_handler_types)}")
        
        # Validate MCP configuration if using MCP
        if self.claude.handler_type in ["mcp", "hybrid"]:
            if not self.claude.mcp_server_uri:
                errors.append("MCP server URI is required for MCP and hybrid modes")
            elif not self._validate_mcp_uri(self.claude.mcp_server_uri):
                errors.append(f"Invalid MCP server URI format: {self.claude.mcp_server_uri}")
            
            if self.claude.mcp_timeout <= 0:
                errors.append("MCP timeout must be positive")
            
            if not self.claude.mcp_protocol_version:
                errors.append("MCP protocol version is required for MCP and hybrid modes")
        
        # Validate hybrid-specific configuration
        if self.claude.handler_type == "hybrid":
            # Ensure at least one handler can be used
            has_subprocess = bool(self.claude.cli_path)
            has_mcp = bool(self.claude.mcp_server_uri)
            
            if not has_subprocess and not has_mcp:
                errors.append("Hybrid mode requires either Claude CLI or MCP server configuration")
        
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
    
    def _validate_mcp_uri(self, uri: str) -> bool:
        """
        Validate MCP server URI format.
        
        Args:
            uri: URI to validate
        
        Returns:
            bool: True if URI is valid, False otherwise
        """
        if not uri:
            return False
        
        # Basic URI validation for MCP protocol
        valid_schemes = ['mcp', 'mcps', 'ws', 'wss', 'http', 'https']
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(uri)
            
            # Check scheme
            if parsed.scheme not in valid_schemes:
                return False
            
            # Check hostname
            if not parsed.hostname:
                return False
            
            # Check port (if specified)
            if parsed.port is not None and (parsed.port < 1 or parsed.port > 65535):
                return False
            
            return True
        except Exception:
            return False
    
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
    
    def validate_mcp_server(self) -> bool:
        """
        Validate that MCP server is accessible.
        
        Returns:
            bool: True if MCP server is accessible.
        
        Raises:
            ConfigurationError: If MCP server is not accessible.
        """
        if not self.claude.mcp_server_uri:
            raise ConfigurationError("MCP server URI is not configured")
        
        try:
            from urllib.parse import urlparse
            import socket
            
            parsed = urlparse(self.claude.mcp_server_uri)
            
            if not parsed.hostname:
                raise ConfigurationError(f"Invalid MCP server URI: {self.claude.mcp_server_uri}")
            
            port = parsed.port or 8000  # Default MCP port
            
            # Test connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.claude.mcp_timeout)
            
            try:
                result = sock.connect_ex((parsed.hostname, port))
                if result != 0:
                    raise ConfigurationError(
                        f"Cannot connect to MCP server at {parsed.hostname}:{port}. "
                        "Please ensure the MCP server is running and accessible."
                    )
                return True
            finally:
                sock.close()
                
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to validate MCP server: {str(e)}")
    
    def get_handler_validation_status(self) -> Dict[str, Any]:
        """
        Get validation status for all configured handlers.
        
        Returns:
            Dict containing validation status for each handler type
        """
        status = {
            'subprocess': {'available': False, 'error': None},
            'mcp': {'available': False, 'error': None},
            'hybrid': {'available': False, 'error': None}
        }
        
        # Test subprocess handler
        if self.claude.handler_type in ['subprocess', 'hybrid']:
            try:
                self.validate_claude_cli()
                status['subprocess']['available'] = True
            except ConfigurationError as e:
                status['subprocess']['error'] = str(e)
        
        # Test MCP handler
        if self.claude.handler_type in ['mcp', 'hybrid']:
            try:
                self.validate_mcp_server()
                status['mcp']['available'] = True
            except ConfigurationError as e:
                status['mcp']['error'] = str(e)
        
        # Hybrid is available if at least one handler is available
        if self.claude.handler_type == 'hybrid':
            status['hybrid']['available'] = (
                status['subprocess']['available'] or 
                status['mcp']['available']
            )
            if not status['hybrid']['available']:
                status['hybrid']['error'] = (
                    "Neither subprocess nor MCP handler is available"
                )
        
        return status
    
    def recommend_handler_type(self) -> Dict[str, Any]:
        """
        Recommend the best handler type based on current configuration and environment.
        
        Returns:
            Dict containing recommendation information
        """
        validation_status = self.get_handler_validation_status()
        
        recommendation = {
            'recommended': None,
            'reason': '',
            'alternatives': [],
            'warnings': []
        }
        
        # Determine best option
        if validation_status['hybrid']['available']:
            recommendation['recommended'] = 'hybrid'
            recommendation['reason'] = (
                'Hybrid mode provides maximum reliability with automatic fallback'
            )
            
            # Add alternatives
            if validation_status['mcp']['available']:
                recommendation['alternatives'].append({
                    'type': 'mcp',
                    'reason': 'MCP-only for maximum performance when stable'
                })
            
            if validation_status['subprocess']['available']:
                recommendation['alternatives'].append({
                    'type': 'subprocess',
                    'reason': 'Subprocess-only for maximum compatibility'
                })
        
        elif validation_status['mcp']['available']:
            recommendation['recommended'] = 'mcp'
            recommendation['reason'] = 'MCP provides enhanced capabilities and performance'
            
            if not validation_status['subprocess']['available']:
                recommendation['warnings'].append(
                    'No fallback available - consider installing Claude CLI for backup'
                )
        
        elif validation_status['subprocess']['available']:
            recommendation['recommended'] = 'subprocess'
            recommendation['reason'] = 'Subprocess is the most reliable option available'
            
            recommendation['warnings'].append(
                'Consider setting up MCP server for enhanced capabilities'
            )
        
        else:
            recommendation['recommended'] = None
            recommendation['reason'] = 'No handlers are currently available'
            recommendation['warnings'].append(
                'Please install Claude CLI or set up MCP server'
            )
        
        return recommendation


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
            # Use custom loader that expands environment variables
            yaml_data = load_yaml_with_env(config_path)
            
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
        if 'default_channel' in slack_data:
            config.slack.channel_id = slack_data['default_channel']
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
        if 'handler_type' in claude_data:
            config.claude.handler_type = claude_data['handler_type']
        if 'mcp_server_uri' in claude_data:
            config.claude.mcp_server_uri = claude_data['mcp_server_uri']
        if 'mcp_protocol_version' in claude_data:
            config.claude.mcp_protocol_version = claude_data['mcp_protocol_version']
        if 'mcp_timeout' in claude_data:
            config.claude.mcp_timeout = claude_data['mcp_timeout']
        if 'prefer_mcp' in claude_data:
            config.claude.prefer_mcp = claude_data['prefer_mcp']
        if 'fallback_to_subprocess' in claude_data:
            config.claude.fallback_to_subprocess = claude_data['fallback_to_subprocess']
    
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
    
    claude_handler_type = os.getenv('CLAUDE_HANDLER_TYPE')
    if claude_handler_type:
        config.claude.handler_type = claude_handler_type
    
    mcp_server_uri = os.getenv('MCP_SERVER_URI')
    if mcp_server_uri:
        config.claude.mcp_server_uri = mcp_server_uri
    
    mcp_timeout = os.getenv('MCP_TIMEOUT')
    if mcp_timeout:
        try:
            config.claude.mcp_timeout = int(mcp_timeout)
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
            'timeout': 300,
            'handler_type': 'subprocess',  # Options: subprocess, mcp, hybrid
            'mcp_server_uri': 'mcp://localhost:8000',
            'mcp_protocol_version': '1.0',
            'mcp_timeout': 30,
            'prefer_mcp': True,
            'fallback_to_subprocess': True
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