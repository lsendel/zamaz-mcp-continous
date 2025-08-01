"""
Unit tests for the utils module.
"""

import pytest
import asyncio
import tempfile
import os
import json
import logging
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from claude_remote_client.utils import (
    setup_logging,
    format_error_for_slack,
    format_success_for_slack,
    format_info_for_slack,
    format_code_block,
    format_inline_code,
    truncate_message,
    validate_project_path,
    ensure_directory_exists,
    get_timestamp,
    safe_dict_get
)


class TestSetupLogging:
    """Test logging setup utilities."""
    
    def test_setup_logging_default(self):
        """Test default logging setup."""
        logger = setup_logging()
        assert logger.name == "claude_remote_client"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1
    
    def test_setup_logging_debug_level(self):
        """Test logging setup with debug level."""
        logger = setup_logging(log_level="DEBUG")
        assert logger.level == logging.DEBUG
    
    def test_setup_logging_with_file(self):
        """Test logging setup with file output."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as temp_file:
            temp_path = temp_file.name
        
        try:
            logger = setup_logging(log_file=temp_path)
            assert len(logger.handlers) >= 2  # Console + file
            assert os.path.exists(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid level defaults to INFO."""
        logger = setup_logging(log_level="INVALID")
        assert logger.level == logging.INFO


class TestSlackFormatting:
    """Test Slack message formatting utilities."""
    
    def test_format_error_for_slack_basic(self):
        """Test basic error formatting for Slack."""
        error = ValueError("Test error")
        result = format_error_for_slack(error)
        assert "❌ **Unexpected Error**: Test error" in result
    
    def test_format_error_for_slack_claude_error(self):
        """Test Claude error formatting for Slack."""
        from claude_remote_client.exceptions import ClaudeRemoteClientError
        error = ClaudeRemoteClientError("Test error", "Additional details")
        result = format_error_for_slack(error)
        assert "❌ **Error**: Test error" in result
        assert "📝 **Details**: Additional details" in result
    
    def test_format_error_for_slack_with_traceback(self):
        """Test error formatting with traceback."""
        error = ValueError("Test error")
        result = format_error_for_slack(error, include_traceback=True)
        assert "❌ **Unexpected Error**: Test error" in result
        assert "```" in result  # Should include code block for traceback
    
    def test_format_success_for_slack(self):
        """Test success message formatting."""
        result = format_success_for_slack("Operation completed")
        assert "✅ **Success**: Operation completed" in result
    
    def test_format_success_for_slack_with_details(self):
        """Test success message formatting with details."""
        result = format_success_for_slack("Operation completed", "All files processed")
        assert "✅ **Success**: Operation completed" in result
        assert "📝 **Details**: All files processed" in result
    
    def test_format_info_for_slack(self):
        """Test info message formatting."""
        result = format_info_for_slack("Processing started")
        assert "ℹ️ **Info**: Processing started" in result
    
    def test_format_info_for_slack_with_details(self):
        """Test info message formatting with details."""
        result = format_info_for_slack("Processing started", "10 files to process")
        assert "ℹ️ **Info**: Processing started" in result
        assert "📝 **Details**: 10 files to process" in result


class TestCodeFormatting:
    """Test code formatting utilities."""
    
    def test_format_code_block(self):
        """Test code block formatting."""
        code = "print('Hello, World!')"
        result = format_code_block(code, "python")
        assert result == "```python\nprint('Hello, World!')\n```"
    
    def test_format_code_block_no_language(self):
        """Test code block formatting without language."""
        code = "some code"
        result = format_code_block(code)
        assert result == "```\nsome code\n```"
    
    def test_format_inline_code(self):
        """Test inline code formatting."""
        code = "variable_name"
        result = format_inline_code(code)
        assert result == "`variable_name`"


class TestValidateProjectPath:
    """Test project path validation."""
    
    def test_validate_existing_directory(self):
        """Test validating existing directory."""
        # Use a directory that should be safe and accessible
        import os
        home_dir = os.path.expanduser("~")
        # Create a test directory in home
        test_dir = os.path.join(home_dir, "test_claude_project")
        os.makedirs(test_dir, exist_ok=True)
        try:
            assert validate_project_path(test_dir) is True
        finally:
            # Clean up
            if os.path.exists(test_dir):
                os.rmdir(test_dir)
    
    def test_validate_nonexistent_path(self):
        """Test validating non-existent path."""
        assert validate_project_path("/nonexistent/path") is False
    
    def test_validate_file_not_directory(self):
        """Test validating file instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            assert validate_project_path(temp_file.name) is False
    
    def test_validate_sensitive_directory(self):
        """Test validating sensitive system directories."""
        assert validate_project_path("/etc") is False
        assert validate_project_path("/sys") is False
        assert validate_project_path("/proc") is False
    
    def test_validate_path_traversal_attempt(self):
        """Test validating path traversal attempts."""
        assert validate_project_path("../../../etc") is False
        assert validate_project_path("/home/user/../../../etc") is False


class TestTruncateMessage:
    """Test message truncation."""
    
    def test_truncate_short_message(self):
        """Test truncating message shorter than limit."""
        message = "Short message"
        result = truncate_message(message, 100)
        assert result == "Short message"
    
    def test_truncate_long_message(self):
        """Test truncating message longer than limit."""
        message = "A" * 3100  # Longer than default 3000
        result = truncate_message(message)
        assert len(result) < 3100
        assert result.endswith("... (message truncated)")
    
    def test_truncate_exact_limit(self):
        """Test truncating message exactly at limit."""
        message = "A" * 3000
        result = truncate_message(message, 3000)
        assert result == message
    
    def test_truncate_with_custom_limit(self):
        """Test truncating with custom limit."""
        message = "A" * 100
        result = truncate_message(message, 50)
        assert len(result) < 100
        assert result.endswith("... (message truncated)")


class TestEnsureDirectoryExists:
    """Test directory creation utility."""
    
    def test_ensure_existing_directory(self):
        """Test ensuring existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ensure_directory_exists(temp_dir)
            assert os.path.exists(temp_dir)
    
    def test_ensure_new_directory(self):
        """Test ensuring new directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "new_directory")
            ensure_directory_exists(new_dir)
            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)
    
    def test_ensure_nested_directory(self):
        """Test ensuring nested directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = os.path.join(temp_dir, "level1", "level2", "level3")
            ensure_directory_exists(nested_dir)
            assert os.path.exists(nested_dir)
            assert os.path.isdir(nested_dir)


class TestGetTimestamp:
    """Test timestamp utility."""
    
    def test_get_timestamp_format(self):
        """Test timestamp format."""
        timestamp = get_timestamp()
        # Should be ISO format
        assert "T" in timestamp
        assert len(timestamp) > 10  # Should be longer than just date
    
    def test_get_timestamp_different_calls(self):
        """Test that different calls produce different timestamps."""
        timestamp1 = get_timestamp()
        time.sleep(0.001)  # Small delay
        timestamp2 = get_timestamp()
        assert timestamp1 != timestamp2


class TestSafeDictGet:
    """Test safe dictionary access utility."""
    
    def test_safe_dict_get_simple_key(self):
        """Test getting simple key."""
        data = {"key": "value"}
        result = safe_dict_get(data, "key")
        assert result == "value"
    
    def test_safe_dict_get_nested_key(self):
        """Test getting nested key with dot notation."""
        data = {"level1": {"level2": {"level3": "value"}}}
        result = safe_dict_get(data, "level1.level2.level3")
        assert result == "value"
    
    def test_safe_dict_get_missing_key(self):
        """Test getting missing key returns default."""
        data = {"key": "value"}
        result = safe_dict_get(data, "missing_key")
        assert result is None
    
    def test_safe_dict_get_custom_default(self):
        """Test getting missing key with custom default."""
        data = {"key": "value"}
        result = safe_dict_get(data, "missing_key", "default_value")
        assert result == "default_value"
    
    def test_safe_dict_get_partial_nested_path(self):
        """Test getting nested key where path doesn't exist."""
        data = {"level1": {"level2": "value"}}
        result = safe_dict_get(data, "level1.level2.level3", "default")
        assert result == "default"
    
    def test_safe_dict_get_non_dict_value(self):
        """Test getting nested key from non-dict value."""
        data = {"level1": "not_a_dict"}
        result = safe_dict_get(data, "level1.level2", "default")
        assert result == "default"