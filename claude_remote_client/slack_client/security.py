"""
Slack security utilities for signature verification and request validation.

This module provides security functions for verifying Slack requests including
HMAC signature verification to prevent request forgery.
"""

import hmac
import hashlib
import time
import logging
from typing import Optional, Dict, Any

from ..exceptions import SlackSecurityError
from ..utils import setup_logging


logger = setup_logging()


def verify_slack_signature(
    request_body: str,
    timestamp: str,
    signature: str,
    signing_secret: str,
    max_age_seconds: int = 300
) -> bool:
    """
    Verify Slack request signature using HMAC-SHA256.
    
    Args:
        request_body: Raw request body as string
        timestamp: X-Slack-Request-Timestamp header value
        signature: X-Slack-Signature header value
        signing_secret: Slack app signing secret
        max_age_seconds: Maximum age of request in seconds (default 5 minutes)
        
    Returns:
        True if signature is valid, False otherwise
        
    Raises:
        SlackSecurityError: If verification fails
    """
    if not all([request_body, timestamp, signature, signing_secret]):
        raise SlackSecurityError("Missing required parameters for signature verification")
    
    # Verify timestamp to prevent replay attacks
    try:
        req_timestamp = int(timestamp)
        current_timestamp = int(time.time())
        
        if abs(current_timestamp - req_timestamp) > max_age_seconds:
            logger.warning(f"Request timestamp too old: {req_timestamp} vs {current_timestamp}")
            return False
    except (ValueError, TypeError) as e:
        raise SlackSecurityError(f"Invalid timestamp format: {e}")
    
    # Verify signature
    sig_basestring = f"v0:{timestamp}:{request_body}"
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected_signature, signature)
    
    if not is_valid:
        logger.warning("Invalid Slack signature detected")
    
    return is_valid


def extract_slack_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract Slack-specific headers from request headers.
    
    Args:
        headers: Request headers dictionary
        
    Returns:
        Dictionary containing Slack headers
    """
    slack_headers = {}
    
    # Convert header keys to lowercase for case-insensitive lookup
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    # Extract Slack headers
    slack_header_names = {
        'x-slack-signature': 'signature',
        'x-slack-request-timestamp': 'timestamp',
        'x-slack-retry-num': 'retry_num',
        'x-slack-retry-reason': 'retry_reason'
    }
    
    for header_name, key_name in slack_header_names.items():
        if header_name in headers_lower:
            slack_headers[key_name] = headers_lower[header_name]
    
    return slack_headers


class SlackRequestValidator:
    """
    Validates incoming Slack requests for security.
    """
    
    def __init__(self, signing_secret: str):
        """
        Initialize the validator.
        
        Args:
            signing_secret: Slack app signing secret
        """
        self.signing_secret = signing_secret
        self.logger = logger
    
    async def validate_request(
        self,
        body: str,
        headers: Dict[str, Any]
    ) -> bool:
        """
        Validate an incoming Slack request.
        
        Args:
            body: Raw request body
            headers: Request headers
            
        Returns:
            True if request is valid
            
        Raises:
            SlackSecurityError: If validation fails
        """
        # Extract Slack headers
        slack_headers = extract_slack_headers(headers)
        
        # Check required headers
        if 'signature' not in slack_headers or 'timestamp' not in slack_headers:
            raise SlackSecurityError("Missing required Slack headers")
        
        # Verify signature
        is_valid = verify_slack_signature(
            request_body=body,
            timestamp=slack_headers['timestamp'],
            signature=slack_headers['signature'],
            signing_secret=self.signing_secret
        )
        
        if not is_valid:
            raise SlackSecurityError("Invalid Slack request signature")
        
        # Log retry information if present
        if 'retry_num' in slack_headers:
            self.logger.info(
                f"Processing Slack retry request: "
                f"attempt {slack_headers['retry_num']}, "
                f"reason: {slack_headers.get('retry_reason', 'unknown')}"
            )
        
        return True
    
    def create_middleware(self):
        """
        Create middleware function for web frameworks.
        
        Returns:
            Async middleware function
        """
        async def middleware(request, handler):
            """Middleware to validate Slack requests."""
            # Get request body and headers
            body = await request.text()
            headers = dict(request.headers)
            
            # Validate request
            await self.validate_request(body, headers)
            
            # Continue with request handling
            return await handler(request)
        
        return middleware