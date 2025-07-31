"""
Utility functions and helpers for the Claude Remote Client.

This module provides common utilities for logging, error handling,
and other shared functionality.
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from .exceptions import ClaudeRemoteClientError


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, logs to console only.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    
    # Create logger
    logger = logging.getLogger("claude_remote_client")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def format_error_for_slack(error: Exception, include_traceback: bool = False) -> str:
    """
    Format an error for display in Slack with user-friendly messaging.
    
    Args:
        error: The exception to format
        include_traceback: Whether to include full traceback
    
    Returns:
        str: Formatted error message for Slack
    """
    
    if isinstance(error, ClaudeRemoteClientError):
        message = f"❌ **Error**: {error.message}"
        if error.details:
            message += f"\n📝 **Details**: {error.details}"
    else:
        message = f"❌ **Unexpected Error**: {str(error)}"
    
    if include_traceback:
        tb = traceback.format_exc()
        message += f"\n```\n{tb}\n```"
    
    return message


def format_success_for_slack(message: str, details: Optional[str] = None) -> str:
    """
    Format a success message for display in Slack.
    
    Args:
        message: Success message
        details: Optional additional details
    
    Returns:
        str: Formatted success message for Slack
    """
    
    formatted = f"✅ **Success**: {message}"
    if details:
        formatted += f"\n📝 **Details**: {details}"
    
    return formatted


def format_info_for_slack(message: str, details: Optional[str] = None) -> str:
    """
    Format an info message for display in Slack.
    
    Args:
        message: Info message
        details: Optional additional details
    
    Returns:
        str: Formatted info message for Slack
    """
    
    formatted = f"ℹ️ **Info**: {message}"
    if details:
        formatted += f"\n📝 **Details**: {details}"
    
    return formatted


def format_code_block(code: str, language: str = "") -> str:
    """
    Format code as a Slack code block.
    
    Args:
        code: Code content
        language: Programming language for syntax highlighting
    
    Returns:
        str: Formatted code block
    """
    return f"```{language}\n{code}\n```"


def format_inline_code(code: str) -> str:
    """
    Format code as inline Slack code.
    
    Args:
        code: Code content
    
    Returns:
        str: Formatted inline code
    """
    return f"`{code}`"


def truncate_message(message: str, max_length: int = 3000) -> str:
    """
    Truncate a message to fit within Slack's message limits.
    
    Args:
        message: Message to truncate
        max_length: Maximum message length
    
    Returns:
        str: Truncated message
    """
    
    if len(message) <= max_length:
        return message
    
    truncated = message[:max_length - 50]  # Leave room for truncation notice
    truncated += "\n\n... (message truncated)"
    
    return truncated


def validate_project_path(path: str) -> bool:
    """
    Validate that a project path exists and is accessible.
    
    Args:
        path: Project path to validate
    
    Returns:
        bool: True if path is valid, False otherwise
    """
    
    try:
        expanded_path = Path(path).expanduser().resolve()
        return expanded_path.exists() and expanded_path.is_dir()
    except Exception:
        return False


def ensure_directory_exists(path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
    
    Raises:
        OSError: If directory cannot be created
    """
    
    Path(path).mkdir(parents=True, exist_ok=True)


def get_timestamp() -> str:
    """
    Get current timestamp as ISO format string.
    
    Returns:
        str: Current timestamp in ISO format
    """
    return datetime.now().isoformat()


def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from a dictionary with nested key support.
    
    Args:
        data: Dictionary to search
        key: Key to look for (supports dot notation for nested keys)
        default: Default value if key not found
    
    Returns:
        Any: Value from dictionary or default
    """
    
    try:
        keys = key.split('.')
        value = data
        
        for k in keys:
            value = value[k]
        
        return value
    
    except (KeyError, TypeError):
        return default