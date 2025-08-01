"""
Performance optimization utilities for Claude Remote Client.

This module provides performance enhancements including:
- Connection pooling for external services
- Caching mechanisms for frequently accessed data
- Async context managers for resource management
- Memory optimization utilities
- Rate limiting and throttling
"""

import asyncio
import time
import weakref
from typing import Any, Dict, Optional, Callable, TypeVar, Generic, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager
import logging
import json
import hashlib

from .logging_config import performance_monitor


T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with expiration and access tracking."""
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds
    
    def touch(self) -> None:
        """Update access tracking."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._stats['expired'] += 1
                self._stats['misses'] += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            
            return entry.value
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        async with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                del self._cache[key]
            
            # Create new entry
            entry = CacheEntry(
                value=value,
                ttl_seconds=ttl or self.default_ttl
            )
            
            self._cache[key] = entry
            
            # Evict oldest entries if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats['evictions'] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate
            }
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self._stats['expired'] += 1
            
            return len(expired_keys)


class ConnectionPool:
    """Generic connection pool for managing reusable connections."""
    
    def __init__(
        self,
        create_connection: Callable[[], Any],
        max_size: int = 10,
        min_size: int = 2,
        max_idle_time: int = 300,  # 5 minutes
        health_check: Optional[Callable[[Any], bool]] = None
    ):
        self.create_connection = create_connection
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_time = max_idle_time
        self.health_check = health_check
        
        self._pool: List[Tuple[Any, datetime]] = []
        self._in_use: weakref.WeakSet = weakref.WeakSet()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._closed = False
    
    async def start(self) -> None:
        """Start the connection pool."""
        if self._cleanup_task:
            return
        
        # Create minimum connections
        async with self._lock:
            for _ in range(self.min_size):
                try:
                    conn = await self._create_connection_async()
                    self._pool.append((conn, datetime.now()))
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Failed to create initial connection: {e}")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop the connection pool and close all connections."""
        self._closed = True
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        async with self._lock:
            for conn, _ in self._pool:
                await self._close_connection_async(conn)
            self._pool.clear()
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        conn = await self._acquire_connection()
        try:
            yield conn
        finally:
            await self._release_connection(conn)
    
    async def _acquire_connection(self) -> Any:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Try to get existing connection
            while self._pool:
                conn, created_at = self._pool.pop(0)
                
                # Check if connection is still healthy
                if self.health_check and not self.health_check(conn):
                    await self._close_connection_async(conn)
                    continue
                
                # Check if connection is too old
                if (datetime.now() - created_at).total_seconds() > self.max_idle_time:
                    await self._close_connection_async(conn)
                    continue
                
                self._in_use.add(conn)
                return conn
            
            # Create new connection if pool is empty and under max size
            if len(self._in_use) < self.max_size:
                conn = await self._create_connection_async()
                self._in_use.add(conn)
                return conn
            
            # Pool is at capacity, wait for a connection to be released
            # This is a simplified implementation - in production, you might want
            # to implement a proper waiting queue with timeouts
            raise RuntimeError("Connection pool exhausted")
    
    async def _release_connection(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            if conn in self._in_use:
                self._in_use.discard(conn)
                
                # Return to pool if healthy and pool not full
                if (len(self._pool) < self.max_size and 
                    (not self.health_check or self.health_check(conn))):
                    self._pool.append((conn, datetime.now()))
                else:
                    await self._close_connection_async(conn)
    
    async def _create_connection_async(self) -> Any:
        """Create a new connection asynchronously."""
        if asyncio.iscoroutinefunction(self.create_connection):
            return await self.create_connection()
        else:
            return self.create_connection()
    
    async def _close_connection_async(self, conn: Any) -> None:
        """Close a connection asynchronously."""
        try:
            if hasattr(conn, 'close'):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error closing connection: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up idle connections."""
        while not self._closed:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                async with self._lock:
                    current_time = datetime.now()
                    active_connections = []
                    
                    for conn, created_at in self._pool:
                        if (current_time - created_at).total_seconds() <= self.max_idle_time:
                            active_connections.append((conn, created_at))
                        else:
                            await self._close_connection_async(conn)
                    
                    self._pool = active_connections
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.getLogger(__name__).error(f"Error in connection pool cleanup: {e}")


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, rate: float, burst: int = None):
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens per second
            burst: Maximum burst size (defaults to rate)
        """
        self.rate = rate
        self.burst = burst or int(rate)
        self.tokens = float(self.burst)
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            bool: True if tokens were acquired, False otherwise
        """
        async with self._lock:
            now = time.time()
            
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    async def wait_for_tokens(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            # Calculate wait time
            async with self._lock:
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.rate
                
            await asyncio.sleep(min(wait_time, 1.0))  # Cap wait time at 1 second


class BatchProcessor(Generic[T]):
    """Batch processor for efficient bulk operations."""
    
    def __init__(
        self,
        process_batch: Callable[[List[T]], Any],
        batch_size: int = 100,
        max_wait_time: float = 1.0,
        max_queue_size: int = 10000
    ):
        self.process_batch = process_batch
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=max_queue_size)
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
    
    async def stop(self) -> None:
        """Stop the batch processor."""
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
    
    async def add_item(self, item: T) -> None:
        """Add item to processing queue."""
        if not self._running:
            raise RuntimeError("Batch processor not started")
        
        await self._queue.put(item)
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        batch = []
        last_batch_time = time.time()
        
        while self._running:
            try:
                # Try to get item with timeout
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass
                
                current_time = time.time()
                
                # Process batch if conditions are met
                should_process = (
                    len(batch) >= self.batch_size or
                    (batch and current_time - last_batch_time >= self.max_wait_time)
                )
                
                if should_process and batch:
                    await self._process_batch_async(batch)
                    batch.clear()
                    last_batch_time = current_time
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.getLogger(__name__).error(f"Error in batch processor: {e}")
        
        # Process remaining items
        if batch:
            await self._process_batch_async(batch)
    
    async def _process_batch_async(self, batch: List[T]) -> None:
        """Process a batch of items."""
        try:
            if asyncio.iscoroutinefunction(self.process_batch):
                await self.process_batch(batch)
            else:
                self.process_batch(batch)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error processing batch: {e}")


class MemoryOptimizer:
    """Utilities for memory optimization."""
    
    @staticmethod
    def create_memory_efficient_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a memory-efficient dictionary using __slots__ if possible."""
        # For large dictionaries, consider using more memory-efficient structures
        if len(data) > 1000:
            # Use a more memory-efficient representation for large dicts
            return {k: v for k, v in data.items() if v is not None}
        return data
    
    @staticmethod
    def compress_string(text: str) -> bytes:
        """Compress string data for storage."""
        import gzip
        return gzip.compress(text.encode('utf-8'))
    
    @staticmethod
    def decompress_string(data: bytes) -> str:
        """Decompress string data."""
        import gzip
        return gzip.decompress(data).decode('utf-8')
    
    @staticmethod
    def get_object_size(obj: Any) -> int:
        """Get approximate size of object in bytes."""
        import sys
        return sys.getsizeof(obj)


class AsyncResourceManager:
    """Async context manager for resource lifecycle management."""
    
    def __init__(self):
        self._resources: List[Any] = []
        self._cleanup_callbacks: List[Callable] = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    def add_resource(self, resource: Any, cleanup_callback: Optional[Callable] = None):
        """Add a resource to be managed."""
        self._resources.append(resource)
        if cleanup_callback:
            self._cleanup_callbacks.append(cleanup_callback)
    
    async def cleanup(self):
        """Clean up all managed resources."""
        for callback in reversed(self._cleanup_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error in cleanup callback: {e}")
        
        self._resources.clear()
        self._cleanup_callbacks.clear()


# Performance monitoring utilities

class PerformanceMetrics:
    """Collect and track performance metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, List[float]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    async def record_timing(self, operation: str, duration: float):
        """Record timing for an operation."""
        async with self._lock:
            self._metrics[f"{operation}_duration"].append(duration)
    
    async def increment_counter(self, counter: str, value: int = 1):
        """Increment a counter."""
        async with self._lock:
            self._counters[counter] += value
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        async with self._lock:
            summary = {}
            
            # Timing metrics
            for operation, durations in self._metrics.items():
                if durations:
                    summary[operation] = {
                        'count': len(durations),
                        'avg': sum(durations) / len(durations),
                        'min': min(durations),
                        'max': max(durations),
                        'p95': sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations)
                    }
            
            # Counters
            summary['counters'] = dict(self._counters)
            
            return summary
    
    async def reset(self):
        """Reset all metrics."""
        async with self._lock:
            self._metrics.clear()
            self._counters.clear()


# Global performance metrics instance
performance_metrics = PerformanceMetrics()
