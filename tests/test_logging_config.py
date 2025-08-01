"""
Unit tests for the logging configuration module.
"""

import pytest
import logging
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open
from claude_remote_client.logging_config import (
    StructuredFormatter
)





class TestStructuredFormatter:
    """Test the StructuredFormatter class."""
    
    def test_format_basic_record(self):
        """Test formatting a basic log record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        # Should be JSON format
        assert "timestamp" in formatted
        assert "test_logger" in formatted
        assert "INFO" in formatted
        assert "Test message" in formatted
    
    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = StructuredFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.session_id = "test-session"
        record.user_id = "test-user"
        
        formatted = formatter.format(record)
        assert "session_id" in formatted
        assert "user_id" in formatted
    
    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = StructuredFormatter()
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="/test/path.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=True
            )
        
        formatted = formatter.format(record)
        assert "exception" in formatted
        assert "ValueError" in formatted