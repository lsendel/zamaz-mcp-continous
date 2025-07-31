"""
Unit tests for utility functions.
"""

import pytest
import tempfile
import logging
from pathlib import Path

from claude_remote_client.utils import (
    setup_logging, format_error_for_slack, format_success_for_slack,
    format_info_for_slack, format_code_block, format_inline_code,
    truncate_message, validate_project_path, ensure_directory_exists,
    get_timestamp, safe_dict_get
)
from claude_remote_client.exceptions import ClaudeRemoteClientError, SlackConnectionError


class TestLogging:
    """Test cases for logging setup."""
    
    def test_setup_logging_console_only(self):
        """Test setting up console-only logging."""
        logger = setup_logging("DEBUG")
        
        assert logger.name == "claude_remote_client"
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
    
    def test_setup_logging_with_file(self):
        """Test setting up logging with file output."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_file = temp_file.name
        
        logger = setup_logging("INFO", log_file)
        
        assert len(logger.handlers) == 2
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        
        # Clean up
        Path(log_file).unlink()
    
    def test_setup_logging_invalid_level(self):
        """Test setting up logging with invalid level."""
        logger = setup_logging("INVALID_LEVEL")
        
        # Should default to INFO level
        assert logger.level == logging.INFO


class TestSlackFormatting:
    """Test cases for Slack message formatting."""
    
    def test_format_error_for_slack_custom_error(self):
        """Test formatting custom error for Slack."""
        error = SlackConnectionError("Connection failed", "Network timeout")
        result = format_error_for_slack(error)
        
        assert "❌ **Error**: Connection failed" in result
        assert "📝 **Details**: Network timeout" in result
    
    def test_format_error_for_slack_generic_error(self):
        """Test formatting generic error for Slack."""
        error = ValueError("Invalid value")
        result = format_error_for_slack(error)
        
        assert "❌ **Unexpected Error**: Invalid value" in result
    
    def test_format_error_for_slack_with_traceback(self):
        """Test formatting error with traceback."""
        error = ValueError("Test error")
        result = format_error_for_slack(error, include_traceback=True)
        
        assert "❌ **Unexpected Error**: Test error" in result
        assert "```" in result  # Should contain code block for traceback
    
    def test_format_success_for_slack(self):
        """Test formatting success message for Slack."""
        result = format_success_for_slack("Operation completed", "All files processed")
        
        assert "✅ **Success**: Operation completed" in result
        assert "📝 **Details**: All files processed" in result
    
    def test_format_success_for_slack_no_details(self):
        """Test formatting success message without details."""
        result = format_success_for_slack("Operation completed")
        
        assert "✅ **Success**: Operation completed" in result
        assert "📝 **Details**:" not in result
    
    def test_format_info_for_slack(self):
        """Test formatting info message for Slack."""
        result = format_info_for_slack("System status", "All services running")
        
        assert "ℹ️ **Info**: System status" in result
        assert "📝 **Details**: All services running" in result
    
    def test_format_code_block(self):
        """Test formatting code block."""
        code = "def hello():\n    print('Hello, world!')"
        
        # Without language
        result = format_code_block(code)
        assert result == "```\ndef hello():\n    print('Hello, world!')\n```"
        
        # With language
        result = format_code_block(code, "python")
        assert result == "```python\ndef hello():\n    print('Hello, world!')\n```"
    
    def test_format_inline_code(self):
        """Test formatting inline code."""
        result = format_inline_code("variable_name")
        assert result == "`variable_name`"
    
    def test_truncate_message_short(self):
        """Test truncating short message (no truncation needed)."""
        message = "This is a short message"
        result = truncate_message(message, max_length=100)
        assert result == message
    
    def test_truncate_message_long(self):
        """Test truncating long message."""
        message = "A" * 1000
        result = truncate_message(message, max_length=100)
        
        assert len(result) <= 100
        assert result.endswith("... (message truncated)")
        assert result.startswith("A")


class TestPathValidation:
    """Test cases for path validation and management."""
    
    def test_validate_project_path_valid(self):
        """Test validating valid project path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            assert validate_project_path(temp_dir) is True
    
    def test_validate_project_path_invalid(self):
        """Test validating invalid project path."""
        assert validate_project_path("/nonexistent/path") is False
    
    def test_validate_project_path_file(self):
        """Test validating path that points to file (not directory)."""
        with tempfile.NamedTemporaryFile() as temp_file:
            assert validate_project_path(temp_file.name) is False
    
    def test_validate_project_path_with_tilde(self):
        """Test validating path with tilde expansion."""
        # This should work if home directory exists
        home_exists = Path.home().exists()
        result = validate_project_path("~")
        assert result == home_exists
    
    def test_ensure_directory_exists_new(self):
        """Test ensuring new directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new" / "nested" / "directory"
            
            assert not new_dir.exists()
            ensure_directory_exists(str(new_dir))
            assert new_dir.exists()
            assert new_dir.is_dir()
    
    def test_ensure_directory_exists_existing(self):
        """Test ensuring existing directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Should not raise error for existing directory
            ensure_directory_exists(temp_dir)
            assert Path(temp_dir).exists()


class TestUtilityFunctions:
    """Test cases for general utility functions."""
    
    def test_get_timestamp(self):
        """Test getting ISO timestamp."""
        timestamp = get_timestamp()
        
        # Should be valid ISO format
        from datetime import datetime
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)
    
    def test_safe_dict_get_simple(self):
        """Test safe dictionary get with simple key."""
        data = {"key1": "value1", "key2": "value2"}
        
        assert safe_dict_get(data, "key1") == "value1"
        assert safe_dict_get(data, "nonexistent") is None
        assert safe_dict_get(data, "nonexistent", "default") == "default"
    
    def test_safe_dict_get_nested(self):
        """Test safe dictionary get with nested keys."""
        data = {
            "level1": {
                "level2": {
                    "level3": "nested_value"
                }
            }
        }
        
        assert safe_dict_get(data, "level1.level2.level3") == "nested_value"
        assert safe_dict_get(data, "level1.level2") == {"level3": "nested_value"}
        assert safe_dict_get(data, "level1.nonexistent") is None
        assert safe_dict_get(data, "level1.nonexistent.deep", "default") == "default"
    
    def test_safe_dict_get_invalid_data(self):
        """Test safe dictionary get with invalid data types."""
        # Non-dictionary data
        assert safe_dict_get("not_a_dict", "key") is None
        assert safe_dict_get(None, "key", "default") == "default"
        
        # Dictionary with non-dictionary nested value
        data = {"key": "string_value"}
        assert safe_dict_get(data, "key.nested") is None