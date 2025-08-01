"""
Unit tests for the exceptions module.
"""

import pytest
from claude_remote_client.exceptions import (
    ClaudeRemoteClientError,
    SlackConnectionError,
    ClaudeProcessError,
    SessionError,
    ConfigurationError,
    TaskQueueError,
    CronScheduleError,
    QueueError,
    SlackError
)


class TestClaudeRemoteClientError:
    """Test the base exception class."""
    
    def test_basic_exception(self):
        """Test basic exception creation."""
        error = ClaudeRemoteClientError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details is None
    
    def test_exception_with_details(self):
        """Test exception with details."""
        error = ClaudeRemoteClientError("Test error", "Additional details")
        assert str(error) == "Test error: Additional details"
        assert error.message == "Test error"
        assert error.details == "Additional details"
    
    def test_exception_inheritance(self):
        """Test that it inherits from Exception."""
        error = ClaudeRemoteClientError("Test")
        assert isinstance(error, Exception)


class TestSlackConnectionError:
    """Test Slack connection error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = SlackConnectionError()
        assert error.message == "Slack connection error"
        assert str(error) == "Slack connection error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = SlackConnectionError("Custom slack error")
        assert error.message == "Custom slack error"
    
    def test_with_details(self):
        """Test error with details."""
        error = SlackConnectionError("Connection failed", "Network timeout")
        assert str(error) == "Connection failed: Network timeout"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = SlackConnectionError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestClaudeProcessError:
    """Test Claude process error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = ClaudeProcessError()
        assert error.message == "Claude process error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = ClaudeProcessError("Process crashed")
        assert error.message == "Process crashed"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = ClaudeProcessError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestSessionError:
    """Test session error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = SessionError()
        assert error.message == "Session error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = SessionError("Session not found")
        assert error.message == "Session not found"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = SessionError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestConfigurationError:
    """Test configuration error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = ConfigurationError()
        assert error.message == "Configuration error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = ConfigurationError("Invalid config file")
        assert error.message == "Invalid config file"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = ConfigurationError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestTaskQueueError:
    """Test task queue error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = TaskQueueError()
        assert error.message == "Task queue error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = TaskQueueError("Queue is full")
        assert error.message == "Queue is full"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = TaskQueueError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestCronScheduleError:
    """Test cron schedule error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = CronScheduleError()
        assert error.message == "Cron schedule error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = CronScheduleError("Invalid cron pattern")
        assert error.message == "Invalid cron pattern"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = CronScheduleError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestQueueError:
    """Test queue error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = QueueError()
        assert error.message == "Queue error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = QueueError("Queue operation failed")
        assert error.message == "Queue operation failed"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = QueueError()
        assert isinstance(error, ClaudeRemoteClientError)


class TestSlackError:
    """Test slack error."""
    
    def test_default_message(self):
        """Test default error message."""
        error = SlackError()
        assert error.message == "Slack error"
    
    def test_custom_message(self):
        """Test custom error message."""
        error = SlackError("API call failed")
        assert error.message == "API call failed"
    
    def test_inheritance(self):
        """Test inheritance from base error."""
        error = SlackError()
        assert isinstance(error, ClaudeRemoteClientError)