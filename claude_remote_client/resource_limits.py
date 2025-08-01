"""
Resource management and limits for async operations.

This module provides utilities for managing resources and preventing
resource exhaustion in async operations such as concurrent tasks,
sessions, and connections.
"""

import asyncio
import functools
from typing import Optional, Dict, Any, Callable, TypeVar
from contextlib import asynccontextmanager

from .exceptions import QueueError
from .utils import setup_logging


logger = setup_logging()

# Type variables for generic decorators
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class ResourceLimiter:
    """
    Manages resource limits and prevents exhaustion.
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        max_concurrent_sessions: int = 5,
        max_queue_size: int = 100
    ):
        """
        Initialize resource limiter.

        Args:
            max_concurrent_tasks: Maximum concurrent async tasks
            max_concurrent_sessions: Maximum concurrent Claude sessions
            max_queue_size: Maximum task queue size
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_concurrent_sessions = max_concurrent_sessions
        self.max_queue_size = max_queue_size

        # Semaphores for limiting concurrency
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.session_semaphore = asyncio.Semaphore(max_concurrent_sessions)

        # Counters for monitoring
        self.active_tasks = 0
        self.active_sessions = 0
        self.queued_tasks = 0

        self.logger = logger

    @asynccontextmanager
    async def acquire_task(self):
        """
        Context manager for acquiring a task slot.

        Raises:
            QueueError: If unable to acquire task slot
        """
        try:
            await self.task_semaphore.acquire()
            self.active_tasks += 1
            self.logger.debug(
                f"Task acquired. Active tasks: {self.active_tasks}"
            )
            yield
        finally:
            self.task_semaphore.release()
            self.active_tasks -= 1
            self.logger.debug(
                f"Task released. Active tasks: {self.active_tasks}"
            )

    @asynccontextmanager
    async def acquire_session(self):
        """
        Context manager for acquiring a session slot.

        Raises:
            QueueError: If unable to acquire session slot
        """
        try:
            await self.session_semaphore.acquire()
            self.active_sessions += 1
            self.logger.debug(
                f"Session acquired. Active sessions: {self.active_sessions}"
            )
            yield
        finally:
            self.session_semaphore.release()
            self.active_sessions -= 1
            self.logger.debug(
                f"Session released. Active sessions: {self.active_sessions}"
            )

    def check_queue_limit(self) -> bool:
        """
        Check if queue limit is reached.

        Returns:
            True if queue has space, False if full
        """
        return self.queued_tasks < self.max_queue_size

    def increment_queue(self) -> None:
        """Increment queued tasks counter."""
        if not self.check_queue_limit():
            raise QueueError(f"Queue limit reached: {self.max_queue_size}")
        self.queued_tasks += 1

    def decrement_queue(self) -> None:
        """Decrement queued tasks counter."""
        if self.queued_tasks > 0:
            self.queued_tasks -= 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current resource statistics.

        Returns:
            Dictionary with resource usage stats
        """
        return {
            "active_tasks": self.active_tasks,
            "max_tasks": self.max_concurrent_tasks,
            "task_utilization": (
                self.active_tasks / self.max_concurrent_tasks
            ),
            "active_sessions": self.active_sessions,
            "max_sessions": self.max_concurrent_sessions,
            "session_utilization": (
                self.active_sessions / self.max_concurrent_sessions
            ),
            "queued_tasks": self.queued_tasks,
            "max_queue_size": self.max_queue_size,
            "queue_utilization": self.queued_tasks / self.max_queue_size
        }


# Global resource limiter instance
_resource_limiter: Optional[ResourceLimiter] = None


def get_resource_limiter() -> ResourceLimiter:
    """
    Get the global resource limiter instance.

    Returns:
        ResourceLimiter instance
    """
    global _resource_limiter
    if _resource_limiter is None:
        _resource_limiter = ResourceLimiter()
    return _resource_limiter


def set_resource_limits(
    max_concurrent_tasks: Optional[int] = None,
    max_concurrent_sessions: Optional[int] = None,
    max_queue_size: Optional[int] = None
) -> None:
    """
    Set global resource limits.

    Args:
        max_concurrent_tasks: Maximum concurrent async tasks
        max_concurrent_sessions: Maximum concurrent Claude sessions
        max_queue_size: Maximum task queue size
    """
    global _resource_limiter

    if _resource_limiter is None:
        _resource_limiter = ResourceLimiter()

    if max_concurrent_tasks is not None:
        _resource_limiter.max_concurrent_tasks = max_concurrent_tasks
        _resource_limiter.task_semaphore = asyncio.Semaphore(
            max_concurrent_tasks
        )

    if max_concurrent_sessions is not None:
        _resource_limiter.max_concurrent_sessions = max_concurrent_sessions
        _resource_limiter.session_semaphore = asyncio.Semaphore(
            max_concurrent_sessions
        )

    if max_queue_size is not None:
        _resource_limiter.max_queue_size = max_queue_size


def with_task_limit(func: F) -> F:
    """
    Decorator to limit concurrent execution of async tasks.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with resource limits
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        limiter = get_resource_limiter()
        async with limiter.acquire_task():
            return await func(*args, **kwargs)
    return wrapper


def with_session_limit(func: F) -> F:
    """
    Decorator to limit concurrent Claude sessions.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with session limits
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        limiter = get_resource_limiter()
        async with limiter.acquire_session():
            return await func(*args, **kwargs)
    return wrapper


class ResourcePool:
    """
    Generic resource pool for managing limited resources.
    """

    def __init__(self, max_size: int = 10):
        """
        Initialize resource pool.

        Args:
            max_size: Maximum pool size
        """
        self.max_size = max_size
        self.pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.created = 0
        self.logger = logger

    async def acquire(self) -> Any:
        """
        Acquire a resource from the pool.

        Returns:
            Resource instance
        """
        try:
            # Try to get from pool
            resource = self.pool.get_nowait()
            self.logger.debug("Resource acquired from pool")
            return resource
        except asyncio.QueueEmpty:
            # Create new if under limit
            if self.created < self.max_size:
                resource = await self._create_resource()
                self.created += 1
                self.logger.debug(
                    f"New resource created. Total: {self.created}"
                )
                return resource
            else:
                # Wait for available resource
                self.logger.debug("Waiting for available resource")
                resource = await self.pool.get()
                return resource

    async def release(self, resource: Any) -> None:
        """
        Release a resource back to the pool.

        Args:
            resource: Resource to release
        """
        try:
            self.pool.put_nowait(resource)
            self.logger.debug("Resource released to pool")
        except asyncio.QueueFull:
            # Pool is full, dispose of resource
            await self._dispose_resource(resource)
            self.created -= 1
            self.logger.debug("Resource disposed (pool full)")

    async def _create_resource(self) -> Any:
        """
        Create a new resource. Override in subclasses.

        Returns:
            New resource instance
        """
        raise NotImplementedError(
            "Subclasses must implement _create_resource"
        )

    async def _dispose_resource(self, resource: Any) -> None:
        """
        Dispose of a resource. Override in subclasses.

        Args:
            resource: Resource to dispose
        """
        pass

    async def close(self) -> None:
        """Close the pool and dispose of all resources."""
        while not self.pool.empty():
            try:
                resource = self.pool.get_nowait()
                await self._dispose_resource(resource)
            except asyncio.QueueEmpty:
                break
        self.created = 0
        self.logger.info("Resource pool closed")