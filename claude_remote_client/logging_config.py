"""
Enhanced logging configuration with structured logging, metrics, and performance tracking.

This module provides comprehensive logging capabilities including:
- Structured JSON logging for production
- Performance metrics and timing
- Error tracking with context
- Log rotation and retention
- Async logging for high-performance scenarios
"""

import logging
import logging.handlers
import json
import time
import asyncio
import functools
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union, Callable
from pathlib import Path
from contextlib import contextmanager
import sys
import traceback

from .exceptions import ClaudeRemoteClientError


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if enabled
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in ('name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                              'filename', 'module', 'lineno', 'funcName', 'created',
                              'msecs', 'relativeCreated', 'thread', 'threadName',
                              'processName', 'process', 'getMessage', 'exc_info',
                              'exc_text', 'stack_info'):
                    log_data[key] = value
        
        return json.dumps(log_data, default=str)


class PerformanceLogger:
    """Logger for performance metrics and timing."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.metrics = {}
    
    @contextmanager
    def time_operation(self, operation_name: str, **context):
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        
        self.logger.info(
            f"Starting operation: {operation_name}",
            extra={'operation': operation_name, 'phase': 'start', **context}
        )
        
        try:
            yield
            duration = time.perf_counter() - start_time
            
            self.logger.info(
                f"Completed operation: {operation_name} in {duration:.3f}s",
                extra={
                    'operation': operation_name,
                    'phase': 'complete',
                    'duration_seconds': duration,
                    **context
                }
            )
            
            # Store metrics
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(duration)
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            
            self.logger.error(
                f"Failed operation: {operation_name} after {duration:.3f}s",
                extra={
                    'operation': operation_name,
                    'phase': 'error',
                    'duration_seconds': duration,
                    'error': str(e),
                    **context
                },
                exc_info=True
            )
            raise
    
    def log_metrics_summary(self):
        """Log summary of collected performance metrics."""
        for operation, durations in self.metrics.items():
            if durations:
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                
                self.logger.info(
                    f"Performance summary for {operation}",
                    extra={
                        'operation': operation,
                        'metrics_type': 'summary',
                        'count': len(durations),
                        'avg_duration': avg_duration,
                        'min_duration': min_duration,
                        'max_duration': max_duration
                    }
                )


class AsyncLogHandler(logging.Handler):
    """Async log handler for high-performance logging."""
    
    def __init__(self, handler: logging.Handler, queue_size: int = 1000):
        super().__init__()
        self.handler = handler
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.task = None
        self.running = False
    
    async def start(self):
        """Start the async logging task."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._process_logs())
    
    async def stop(self):
        """Stop the async logging task."""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            await self.task
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record asynchronously."""
        try:
            self.queue.put_nowait(record)
        except asyncio.QueueFull:
            # Drop the log record if queue is full
            pass
    
    async def _process_logs(self):
        """Process log records from the queue."""
        while self.running:
            try:
                record = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                self.handler.emit(record)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                # Avoid logging errors in the log handler
                pass


class EnhancedLogger:
    """Enhanced logger with additional functionality."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger(self.logger)
        self.async_handler = None
        
        self._setup_logger()
    
    def _setup_logger(self):
        """Set up the logger with handlers and formatters."""
        self.logger.setLevel(getattr(logging, self.config.get('level', 'INFO').upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        if self.config.get('console', {}).get('enabled', True):
            console_handler = logging.StreamHandler(sys.stdout)
            
            if self.config.get('console', {}).get('structured', False):
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
            
            self.logger.addHandler(console_handler)
        
        # File handler with rotation
        if self.config.get('file', {}).get('enabled', True):
            log_file = Path(self.config['file']['path'])
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.config.get('file', {}).get('max_bytes', 10 * 1024 * 1024),  # 10MB
                backupCount=self.config.get('file', {}).get('backup_count', 5)
            )
            
            if self.config.get('file', {}).get('structured', True):
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
            
            self.logger.addHandler(file_handler)
        
        # Error file handler
        if self.config.get('error_file', {}).get('enabled', True):
            error_file = Path(self.config['error_file']['path'])
            error_file.parent.mkdir(parents=True, exist_ok=True)
            
            error_handler = logging.handlers.RotatingFileHandler(
                error_file,
                maxBytes=self.config.get('error_file', {}).get('max_bytes', 5 * 1024 * 1024),  # 5MB
                backupCount=self.config.get('error_file', {}).get('backup_count', 3)
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(StructuredFormatter())
            
            self.logger.addHandler(error_handler)
    
    async def setup_async_logging(self):
        """Set up async logging for high-performance scenarios."""
        if self.async_handler:
            return
        
        # Create async wrapper for file handler
        file_handlers = [h for h in self.logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        if file_handlers:
            self.async_handler = AsyncLogHandler(file_handlers[0])
            await self.async_handler.start()
            
            # Replace sync handler with async handler
            self.logger.removeHandler(file_handlers[0])
            self.logger.addHandler(self.async_handler)
    
    async def cleanup_async_logging(self):
        """Clean up async logging resources."""
        if self.async_handler:
            await self.async_handler.stop()
            self.async_handler = None
    
    def log_with_context(self, level: int, message: str, **context):
        """Log with additional context information."""
        self.logger.log(level, message, extra=context)
    
    def log_api_call(self, service: str, method: str, duration: float, status: str, **context):
        """Log API call with standardized format."""
        self.logger.info(
            f"API call: {service}.{method}",
            extra={
                'api_service': service,
                'api_method': method,
                'api_duration': duration,
                'api_status': status,
                **context
            }
        )
    
    def log_user_action(self, user_id: str, action: str, **context):
        """Log user action with standardized format."""
        self.logger.info(
            f"User action: {action}",
            extra={
                'user_id': user_id,
                'action': action,
                **context
            }
        )
    
    def log_session_event(self, session_id: str, event: str, **context):
        """Log session event with standardized format."""
        self.logger.info(
            f"Session event: {event}",
            extra={
                'session_id': session_id,
                'session_event': event,
                **context
            }
        )


def setup_enhanced_logging(config: Dict[str, Any]) -> EnhancedLogger:
    """
    Set up enhanced logging with the provided configuration.
    
    Args:
        config: Logging configuration dictionary
    
    Returns:
        EnhancedLogger: Configured enhanced logger instance
    """
    return EnhancedLogger("claude_remote_client", config)


def performance_monitor(operation_name: str = None):
    """Decorator for monitoring function performance."""
    def decorator(func: Callable) -> Callable:
        name = operation_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                logger = logging.getLogger("claude_remote_client.performance")
                start_time = time.perf_counter()
                
                try:
                    result = await func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    
                    logger.info(
                        f"Performance: {name} completed",
                        extra={
                            'operation': name,
                            'duration_seconds': duration,
                            'status': 'success'
                        }
                    )
                    
                    return result
                
                except Exception as e:
                    duration = time.perf_counter() - start_time
                    
                    logger.error(
                        f"Performance: {name} failed",
                        extra={
                            'operation': name,
                            'duration_seconds': duration,
                            'status': 'error',
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    raise
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                logger = logging.getLogger("claude_remote_client.performance")
                start_time = time.perf_counter()
                
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    
                    logger.info(
                        f"Performance: {name} completed",
                        extra={
                            'operation': name,
                            'duration_seconds': duration,
                            'status': 'success'
                        }
                    )
                    
                    return result
                
                except Exception as e:
                    duration = time.perf_counter() - start_time
                    
                    logger.error(
                        f"Performance: {name} failed",
                        extra={
                            'operation': name,
                            'duration_seconds': duration,
                            'status': 'error',
                            'error': str(e)
                        },
                        exc_info=True
                    )
                    raise
            
            return sync_wrapper
    
    return decorator


# Default logging configuration
DEFAULT_LOGGING_CONFIG = {
    'level': 'INFO',
    'console': {
        'enabled': True,
        'structured': False
    },
    'file': {
        'enabled': True,
        'path': '~/.claude-remote-client/logs/app.log',
        'structured': True,
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5
    },
    'error_file': {
        'enabled': True,
        'path': '~/.claude-remote-client/logs/errors.log',
        'max_bytes': 5 * 1024 * 1024,  # 5MB
        'backup_count': 3
    }
}
