"""
Custom exceptions for the Claude Remote Client.

This module defines the exception hierarchy used throughout the application
for proper error handling and user feedback.
"""


class ClaudeRemoteClientError(Exception):
    """Base exception for all Claude Remote Client errors."""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class SlackConnectionError(ClaudeRemoteClientError):
    """Raised when Slack connection fails or is lost."""
    
    def __init__(self, message: str = "Slack connection error", details: str = None):
        super().__init__(message, details)


class ClaudeProcessError(ClaudeRemoteClientError):
    """Raised when Claude CLI process encounters an error."""
    
    def __init__(self, message: str = "Claude process error", details: str = None):
        super().__init__(message, details)


class SessionError(ClaudeRemoteClientError):
    """Raised when session management encounters an error."""
    
    def __init__(self, message: str = "Session error", details: str = None):
        super().__init__(message, details)


class ConfigurationError(ClaudeRemoteClientError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str = "Configuration error", details: str = None):
        super().__init__(message, details)


class TaskQueueError(ClaudeRemoteClientError):
    """Raised when task queue operations fail."""
    
    def __init__(self, message: str = "Task queue error", details: str = None):
        super().__init__(message, details)


class CronScheduleError(ClaudeRemoteClientError):
    """Raised when cron schedule operations fail."""
    
    def __init__(self, message: str = "Cron schedule error", details: str = None):
        super().__init__(message, details)


class QueueError(ClaudeRemoteClientError):
    """Raised when queue operations fail."""
    
    def __init__(self, message: str = "Queue error", details: str = None):
        super().__init__(message, details)


class SlackError(ClaudeRemoteClientError):
    """Raised when Slack operations fail."""
    
    def __init__(self, message: str = "Slack error", details: str = None):
        super().__init__(message, details)


class SlackSecurityError(SlackError):
    """Raised when Slack security validation fails."""
    
    def __init__(self, message: str = "Slack security error", details: str = None):
        super().__init__(message, details)