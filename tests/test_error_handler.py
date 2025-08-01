"""
Unit tests for the error handler module.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from claude_remote_client.error_handler import (
    ErrorHandler
)
from claude_remote_client.exceptions import (
    ClaudeRemoteClientError,
    SlackConnectionError,
    ClaudeProcessError,
    SessionError,
    ConfigurationError
)





class TestErrorHandler:
    """Test the ErrorHandler class."""
    
    def test_error_handler_creation(self):
        """Test creating error handler."""
        handler = ErrorHandler()
        assert hasattr(handler, 'logger')
        assert hasattr(handler, 'error_history')
        assert hasattr(handler, 'retry_configs')
        assert len(handler.error_history) == 0
    
    def test_error_handler_has_retry_configs(self):
        """Test that error handler has retry configurations."""
        handler = ErrorHandler()
        
        # Should have retry configs for different error types
        assert SlackConnectionError in handler.retry_configs
        assert ClaudeProcessError in handler.retry_configs
        
        # Check that configs have expected structure
        slack_config = handler.retry_configs[SlackConnectionError]
        assert 'max_retries' in slack_config
        assert 'base_delay' in slack_config
        assert 'max_delay' in slack_config
    
    def test_error_handler_max_history(self):
        """Test error handler respects max history limit."""
        handler = ErrorHandler()
        assert handler.max_history == 1000
    
    @patch('claude_remote_client.error_handler.logging.getLogger')
    def test_error_handler_logger_setup(self, mock_get_logger):
        """Test that error handler sets up logger correctly."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        handler = ErrorHandler()
        assert handler.logger == mock_logger