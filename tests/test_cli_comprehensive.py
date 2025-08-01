"""
Comprehensive unit tests for the CLI module.
"""

import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, MagicMock, mock_open
from claude_remote_client.cli import (
    validate_claude_cli,
    check_system_requirements
)
from claude_remote_client.exceptions import ConfigurationError


class TestCheckSystemRequirements:
    """Test system requirements checking."""
    
    @patch('claude_remote_client.cli.validate_claude_cli')
    def test_check_system_requirements_success(self, mock_validate):
        """Test successful system requirements check."""
        mock_validate.return_value = True
        
        result, issues = check_system_requirements()
        assert result is True
        assert len(issues) == 0
        mock_validate.assert_called_once()
    
    @patch('claude_remote_client.cli.validate_claude_cli')
    def test_check_system_requirements_failure(self, mock_validate):
        """Test failed system requirements check."""
        mock_validate.return_value = False
        
        result, issues = check_system_requirements()
        assert result is False
        assert len(issues) > 0


class TestValidateClaudeCli:
    """Test Claude CLI validation."""
    
    @patch('subprocess.run')
    def test_validate_claude_cli_success(self, mock_run):
        """Test successful Claude CLI validation."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = validate_claude_cli()
        assert result is True
        mock_run.assert_called_once_with(
            ['claude', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_validate_claude_cli_not_found(self, mock_run):
        """Test Claude CLI not found."""
        mock_run.side_effect = FileNotFoundError()
        
        result = validate_claude_cli()
        assert result is False
    
    @patch('subprocess.run')
    def test_validate_claude_cli_error_code(self, mock_run):
        """Test Claude CLI returns error code."""
        mock_run.return_value = MagicMock(returncode=1)
        
        result = validate_claude_cli()
        assert result is False
    
    @patch('subprocess.run')
    def test_validate_claude_cli_timeout(self, mock_run):
        """Test Claude CLI timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(['claude', '--version'], 10)
        
        result = validate_claude_cli()
        assert result is False


# Additional CLI tests can be added here as needed


# Add AsyncMock for Python < 3.8 compatibility
try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(MagicMock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)