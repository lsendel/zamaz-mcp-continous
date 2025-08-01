"""
Tests for Slack security module.
"""

import pytest
import time
import hmac
import hashlib
from unittest.mock import Mock, patch

from claude_remote_client.slack_client.security import (
    verify_slack_signature,
    extract_slack_headers,
    SlackRequestValidator
)
from claude_remote_client.exceptions import SlackSecurityError


class TestVerifySlackSignature:
    """Test cases for verify_slack_signature function."""
    
    def test_valid_signature(self):
        """Test verification with valid signature."""
        # Setup test data
        signing_secret = "test_signing_secret"
        timestamp = str(int(time.time()))
        request_body = "test=data&foo=bar"
        
        # Generate valid signature
        sig_basestring = f"v0:{timestamp}:{request_body}"
        expected_signature = 'v0=' + hmac.new(
            signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Verify
        result = verify_slack_signature(
            request_body=request_body,
            timestamp=timestamp,
            signature=expected_signature,
            signing_secret=signing_secret
        )
        
        assert result is True
    
    def test_invalid_signature(self):
        """Test verification with invalid signature."""
        result = verify_slack_signature(
            request_body="test=data",
            timestamp=str(int(time.time())),
            signature="v0=invalid_signature",
            signing_secret="test_secret"
        )
        
        assert result is False
    
    def test_old_timestamp(self):
        """Test verification with old timestamp."""
        # Create timestamp 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        
        result = verify_slack_signature(
            request_body="test=data",
            timestamp=old_timestamp,
            signature="v0=doesnt_matter",
            signing_secret="test_secret",
            max_age_seconds=300
        )
        
        assert result is False
    
    def test_missing_parameters(self):
        """Test with missing required parameters."""
        with pytest.raises(SlackSecurityError) as exc_info:
            verify_slack_signature(
                request_body="",
                timestamp="",
                signature="",
                signing_secret=""
            )
        
        assert "Missing required parameters" in str(exc_info.value)
    
    def test_invalid_timestamp_format(self):
        """Test with invalid timestamp format."""
        with pytest.raises(SlackSecurityError) as exc_info:
            verify_slack_signature(
                request_body="test",
                timestamp="not_a_number",
                signature="v0=test",
                signing_secret="secret"
            )
        
        assert "Invalid timestamp format" in str(exc_info.value)


class TestExtractSlackHeaders:
    """Test cases for extract_slack_headers function."""
    
    def test_extract_all_headers(self):
        """Test extracting all Slack headers."""
        headers = {
            'X-Slack-Signature': 'v0=test_signature',
            'X-Slack-Request-Timestamp': '1234567890',
            'X-Slack-Retry-Num': '1',
            'X-Slack-Retry-Reason': 'timeout',
            'Other-Header': 'ignored'
        }
        
        result = extract_slack_headers(headers)
        
        assert result == {
            'signature': 'v0=test_signature',
            'timestamp': '1234567890',
            'retry_num': '1',
            'retry_reason': 'timeout'
        }
    
    def test_case_insensitive_headers(self):
        """Test that header extraction is case-insensitive."""
        headers = {
            'x-slack-signature': 'v0=test',
            'X-SLACK-REQUEST-TIMESTAMP': '123'
        }
        
        result = extract_slack_headers(headers)
        
        assert result['signature'] == 'v0=test'
        assert result['timestamp'] == '123'
    
    def test_missing_headers(self):
        """Test with missing Slack headers."""
        headers = {
            'Other-Header': 'value'
        }
        
        result = extract_slack_headers(headers)
        
        assert result == {}


class TestSlackRequestValidator:
    """Test cases for SlackRequestValidator class."""
    
    def setup_method(self):
        """Set up test validator."""
        self.signing_secret = "test_signing_secret"
        self.validator = SlackRequestValidator(self.signing_secret)
    
    @pytest.mark.asyncio
    async def test_validate_valid_request(self):
        """Test validating a valid request."""
        # Create valid request data
        timestamp = str(int(time.time()))
        body = "test=data"
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = 'v0=' + hmac.new(
            self.signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Slack-Signature': signature,
            'X-Slack-Request-Timestamp': timestamp
        }
        
        # Should not raise
        result = await self.validator.validate_request(body, headers)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_missing_headers(self):
        """Test validation with missing headers."""
        headers = {}
        
        with pytest.raises(SlackSecurityError) as exc_info:
            await self.validator.validate_request("body", headers)
        
        assert "Missing required Slack headers" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_invalid_signature(self):
        """Test validation with invalid signature."""
        headers = {
            'X-Slack-Signature': 'v0=invalid',
            'X-Slack-Request-Timestamp': str(int(time.time()))
        }
        
        with pytest.raises(SlackSecurityError) as exc_info:
            await self.validator.validate_request("body", headers)
        
        assert "Invalid Slack request signature" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_with_retry_info(self):
        """Test validation logs retry information."""
        # Create valid request
        timestamp = str(int(time.time()))
        body = "test"
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = 'v0=' + hmac.new(
            self.signing_secret.encode('utf-8'),
            sig_basestring.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Slack-Signature': signature,
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Retry-Num': '2',
            'X-Slack-Retry-Reason': 'timeout'
        }
        
        with patch.object(self.validator.logger, 'info') as mock_logger:
            await self.validator.validate_request(body, headers)
            
            # Check that retry info was logged
            mock_logger.assert_called_once()
            log_message = mock_logger.call_args[0][0]
            assert 'retry' in log_message.lower()
            assert 'attempt 2' in log_message
            assert 'timeout' in log_message
    
    def test_create_middleware(self):
        """Test middleware creation."""
        middleware = self.validator.create_middleware()
        
        assert callable(middleware)
        # Further testing would require a web framework context