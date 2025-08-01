"""
Advanced error handling with retry logic and error categorization.

This module provides enhanced error handling capabilities including
automatic retry logic, exponential backoff, and detailed error tracking.
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Type, Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta

from .exceptions import (
    ClaudeRemoteClientError,
    SlackConnectionError,
    ClaudeProcessError,
    SessionError,
    ConfigurationError,
    TaskQueueError
)


class ErrorHandler:
    """
    Advanced error handler with retry logic and error tracking.
    
    Provides automatic retry with exponential backoff, error categorization,
    and detailed error tracking for debugging and monitoring.
    """
    
    def __init__(self):
        """Initialize the error handler."""
        self.logger = logging.getLogger(__name__)
        self.error_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Retry configuration
        self.retry_configs = {
            SlackConnectionError: {
                'max_retries': 5,
                'base_delay': 1.0,
                'max_delay': 60.0,
                'exponential_base': 2
            },
            ClaudeProcessError: {
                'max_retries': 3,
                'base_delay': 2.0,
                'max_delay': 30.0,
                'exponential_base': 2
            },
            SessionError: {
                'max_retries': 2,
                'base_delay': 1.0,
                'max_delay': 10.0,
                'exponential_base': 2
            },
            TaskQueueError: {
                'max_retries': 3,
                'base_delay': 0.5,
                'max_delay': 5.0,
                'exponential_base': 2
            }
        }
    
    def record_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an error in the error history.
        
        Args:
            error: The exception that occurred
            context: Optional context information
        """
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {}
        }
        
        self.error_history.append(error_info)
        
        # Maintain history size limit
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]
    
    def get_retry_config(self, error_type: Type[Exception]) -> Dict[str, Any]:
        """
        Get retry configuration for a specific error type.
        
        Args:
            error_type: Type of exception
        
        Returns:
            Dict containing retry configuration
        """
        # Check for exact match first
        if error_type in self.retry_configs:
            return self.retry_configs[error_type]
        
        # Check for subclass match
        for exc_type, config in self.retry_configs.items():
            if issubclass(error_type, exc_type):
                return config
        
        # Default configuration
        return {
            'max_retries': 1,
            'base_delay': 1.0,
            'max_delay': 10.0,
            'exponential_base': 2
        }
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Execute an async function with automatic retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            exceptions: Tuple of exceptions to catch and retry
            context: Optional context for error recording
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of the function call
        
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for exc_type in exceptions:
            config = self.get_retry_config(exc_type)
            max_retries = config['max_retries']
            base_delay = config['base_delay']
            max_delay = config['max_delay']
            exponential_base = config['exponential_base']
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    self.record_error(e, context)
                    
                    if attempt == max_retries:
                        self.logger.error(
                            f"All {max_retries} retries failed for {func.__name__}: {e}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
        
        if last_exception:
            raise last_exception
    
    def retry_sync(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Execute a sync function with automatic retry logic.
        
        Args:
            func: Sync function to execute
            *args: Positional arguments for func
            exceptions: Tuple of exceptions to catch and retry
            context: Optional context for error recording
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of the function call
        
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for exc_type in exceptions:
            config = self.get_retry_config(exc_type)
            max_retries = config['max_retries']
            base_delay = config['base_delay']
            max_delay = config['max_delay']
            exponential_base = config['exponential_base']
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    self.record_error(e, context)
                    
                    if attempt == max_retries:
                        self.logger.error(
                            f"All {max_retries} retries failed for {func.__name__}: {e}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
        
        if last_exception:
            raise last_exception
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics from the error history.
        
        Returns:
            Dict containing error statistics
        """
        if not self.error_history:
            return {
                'total_errors': 0,
                'error_types': {},
                'recent_errors': []
            }
        
        # Count errors by type
        error_types = {}
        for error in self.error_history:
            error_type = error['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Get recent errors
        recent_errors = self.error_history[-10:]
        
        return {
            'total_errors': len(self.error_history),
            'error_types': error_types,
            'recent_errors': recent_errors,
            'oldest_error': self.error_history[0]['timestamp'],
            'newest_error': self.error_history[-1]['timestamp']
        }
    
    def clear_error_history(self) -> None:
        """Clear the error history."""
        self.error_history.clear()
        self.logger.info("Error history cleared")


def with_retry(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None
):
    """
    Decorator to add retry logic to async functions.
    
    Args:
        exceptions: Tuple of exceptions to catch and retry
        max_retries: Override max retries
        base_delay: Override base delay
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            handler = ErrorHandler()
            
            # Override retry config if specified
            if max_retries is not None or base_delay is not None:
                for exc_type in exceptions:
                    config = handler.get_retry_config(exc_type)
                    if max_retries is not None:
                        config['max_retries'] = max_retries
                    if base_delay is not None:
                        config['base_delay'] = base_delay
            
            return await handler.retry_async(
                func,
                *args,
                exceptions=exceptions,
                context={'function': func.__name__},
                **kwargs
            )
        
        return wrapper
    return decorator


# Global error handler instance
error_handler = ErrorHandler()