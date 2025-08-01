"""
Claude Remote Client - A Python application for remote Claude AI interaction through Slack.

This package provides a bridge between Slack and Claude CLI, enabling remote development
workflows with session management, task queuing, and automated maintenance.
"""

__version__ = "0.1.0"
__author__ = "Claude Remote Client Team"
__email__ = "support@claude-remote-client.com"

from .models import ClaudeSession, QueuedTask, CronSchedule, SlackMessage
from .config import Config, load_config
from .exceptions import (
    ClaudeRemoteClientError,
    SlackConnectionError,
    ClaudeProcessError,
    SessionError,
    ConfigurationError
)
from .resource_limits import (
    ResourceLimiter,
    get_resource_limiter,
    set_resource_limits,
    with_task_limit,
    with_session_limit
)

__all__ = [
    "ClaudeSession",
    "QueuedTask", 
    "CronSchedule",
    "SlackMessage",
    "Config",
    "load_config",
    "ClaudeRemoteClientError",
    "SlackConnectionError",
    "ClaudeProcessError",
    "SessionError",
    "ConfigurationError",
    "ResourceLimiter",
    "get_resource_limiter",
    "set_resource_limits",
    "with_task_limit",
    "with_session_limit"
]