"""
Enhanced session manager with performance optimizations.

This module extends the base session manager with:
- Connection pooling for Claude processes
- Caching for session data
- Async context managers for resource management
- Performance monitoring and metrics
- Memory optimization
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
import weakref

from ..models import ClaudeSession, SessionStatus
from ..config import Config
from ..exceptions import SessionError, ClaudeProcessError
from ..logging_config import performance_monitor, EnhancedLogger
from ..performance import (
    LRUCache, ConnectionPool, RateLimiter, AsyncResourceManager,
    performance_metrics, MemoryOptimizer
)
from .session_manager import SessionManager
from ..claude_client.subprocess_handler import SubprocessClaudeHandler


class EnhancedSessionManager(SessionManager):
    """
    Enhanced session manager with performance optimizations.
    
    Extends the base SessionManager with caching, connection pooling,
    rate limiting, and advanced resource management.
    """
    
    def __init__(self, config: Config):
        super().__init__(config)
        
        # Performance enhancements
        self.session_cache = LRUCache[ClaudeSession](
            max_size=config.max_sessions * 2,
            default_ttl=3600  # 1 hour TTL
        )
        
        self.response_cache = LRUCache[str](
            max_size=1000,
            default_ttl=300  # 5 minutes TTL for responses
        )
        
        # Rate limiting for Claude API calls
        self.claude_rate_limiter = RateLimiter(
            rate=10.0,  # 10 requests per second
            burst=20    # Allow bursts up to 20
        )
        
        # Connection pool for Claude processes
        self.process_pool = ConnectionPool(
            create_connection=self._create_claude_process,
            max_size=config.max_sessions,
            min_size=2,
            max_idle_time=1800,  # 30 minutes
            health_check=self._check_process_health
        )
        
        # Resource manager for cleanup
        self.resource_manager = AsyncResourceManager()
        
        # Performance monitoring
        self.metrics_enabled = True
        self.last_metrics_report = time.time()
        self.metrics_report_interval = 300  # 5 minutes
        
        # Memory optimization
        self.memory_optimizer = MemoryOptimizer()
        
        # Background tasks
        self.cache_cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the enhanced session manager with all optimizations."""
        await super().start()
        
        # Start connection pool
        await self.process_pool.start()
        
        # Start background tasks
        self.cache_cleanup_task = asyncio.create_task(self._cache_cleanup_loop())
        
        if self.metrics_enabled:
            self.metrics_task = asyncio.create_task(self._metrics_reporting_loop())
        
        self.logger.info("Enhanced session manager started with performance optimizations")
    
    async def stop(self) -> None:
        """Stop the enhanced session manager and cleanup resources."""
        # Cancel background tasks
        if self.cache_cleanup_task:
            self.cache_cleanup_task.cancel()
        
        if self.metrics_task:
            self.metrics_task.cancel()
        
        # Stop connection pool
        await self.process_pool.stop()
        
        # Clear caches
        await self.session_cache.clear()
        await self.response_cache.clear()
        
        # Cleanup resources
        await self.resource_manager.cleanup()
        
        await super().stop()
        
        self.logger.info("Enhanced session manager stopped")
    
    @performance_monitor("create_session")
    async def create_session(self, project_name: str, **kwargs) -> ClaudeSession:
        """Create a new Claude session with caching and rate limiting."""
        # Check rate limit
        if not await self.claude_rate_limiter.acquire():
            await self.claude_rate_limiter.wait_for_tokens()
        
        # Record metrics
        await performance_metrics.increment_counter("sessions_created")
        
        # Create session using parent method
        session = await super().create_session(project_name, **kwargs)
        
        # Cache the session
        await self.session_cache.set(session.session_id, session)
        
        # Log performance metrics
        self.logger.log_session_event(
            session.session_id,
            "created",
            project_name=project_name,
            performance_optimized=True
        )
        
        return session
    
    @performance_monitor("get_session")
    async def get_session(self, session_id: str) -> Optional[ClaudeSession]:
        """Get session with caching."""
        # Try cache first
        cached_session = await self.session_cache.get(session_id)
        if cached_session:
            await performance_metrics.increment_counter("session_cache_hits")
            return cached_session
        
        await performance_metrics.increment_counter("session_cache_misses")
        
        # Fall back to parent method
        session = await super().get_session(session_id)
        
        # Cache the result
        if session:
            await self.session_cache.set(session_id, session)
        
        return session
    
    @performance_monitor("send_message")
    async def send_message(self, session_id: str, message: str, **kwargs) -> Optional[str]:
        """Send message with response caching and rate limiting."""
        # Check rate limit
        if not await self.claude_rate_limiter.acquire():
            await self.claude_rate_limiter.wait_for_tokens()
        
        # Create cache key for response caching
        cache_key = self._create_response_cache_key(session_id, message)
        
        # Check response cache for identical messages
        cached_response = await self.response_cache.get(cache_key)
        if cached_response and kwargs.get('use_cache', True):
            await performance_metrics.increment_counter("response_cache_hits")
            self.logger.log_session_event(
                session_id,
                "message_sent_cached",
                message_length=len(message),
                cache_hit=True
            )
            return cached_response
        
        await performance_metrics.increment_counter("response_cache_misses")
        
        # Send message using parent method
        start_time = time.time()
        response = await super().send_message(session_id, message, **kwargs)
        duration = time.time() - start_time
        
        # Record performance metrics
        await performance_metrics.record_timing("send_message", duration)
        await performance_metrics.increment_counter("messages_sent")
        
        # Cache the response
        if response and kwargs.get('cache_response', True):
            await self.response_cache.set(cache_key, response, ttl=300)  # 5 minutes
        
        # Log performance metrics
        self.logger.log_session_event(
            session_id,
            "message_sent",
            message_length=len(message),
            response_length=len(response) if response else 0,
            duration=duration,
            cache_hit=False
        )
        
        return response
    
    @performance_monitor("switch_project")
    async def switch_project(self, project_name: str, **kwargs) -> ClaudeSession:
        """Switch project with optimized session reuse."""
        # Check if we already have an active session for this project
        existing_sessions = [
            session for session in self.sessions.values()
            if session.project_name == project_name and session.status == SessionStatus.ACTIVE
        ]
        
        if existing_sessions and kwargs.get('reuse_session', True):
            # Reuse existing session
            session = existing_sessions[0]
            self.active_session_id = session.session_id
            
            # Update cache
            await self.session_cache.set(session.session_id, session)
            
            await performance_metrics.increment_counter("sessions_reused")
            
            self.logger.log_session_event(
                session.session_id,
                "project_switched_reused",
                project_name=project_name
            )
            
            return session
        
        # Create new session
        return await super().switch_project(project_name, **kwargs)
    
    async def get_session_metrics(self) -> Dict[str, Any]:
        """Get comprehensive session metrics."""
        base_metrics = await super().get_session_status()
        
        # Add cache metrics
        session_cache_stats = await self.session_cache.get_stats()
        response_cache_stats = await self.response_cache.get_stats()
        
        # Add performance metrics
        performance_summary = await performance_metrics.get_summary()
        
        return {
            **base_metrics,
            'caching': {
                'session_cache': session_cache_stats,
                'response_cache': response_cache_stats
            },
            'performance': performance_summary,
            'optimization_features': {
                'connection_pooling': True,
                'response_caching': True,
                'rate_limiting': True,
                'memory_optimization': True
            }
        }
    
    async def optimize_memory_usage(self) -> Dict[str, Any]:
        """Optimize memory usage and return statistics."""
        initial_memory = {}
        
        # Get initial memory usage
        for session_id, session in self.sessions.items():
            initial_memory[session_id] = self.memory_optimizer.get_object_size(session)
        
        # Optimize conversation history
        optimized_count = 0
        for session in self.sessions.values():
            if len(session.conversation_history) > 100:  # Keep only last 100 messages
                session.conversation_history = session.conversation_history[-100:]
                optimized_count += 1
        
        # Clean up expired cache entries
        session_expired = await self.session_cache.cleanup_expired()
        response_expired = await self.response_cache.cleanup_expired()
        
        # Get final memory usage
        final_memory = {}
        for session_id, session in self.sessions.items():
            final_memory[session_id] = self.memory_optimizer.get_object_size(session)
        
        # Calculate savings
        total_initial = sum(initial_memory.values())
        total_final = sum(final_memory.values())
        memory_saved = total_initial - total_final
        
        optimization_stats = {
            'sessions_optimized': optimized_count,
            'cache_entries_expired': {
                'sessions': session_expired,
                'responses': response_expired
            },
            'memory_usage': {
                'initial_bytes': total_initial,
                'final_bytes': total_final,
                'saved_bytes': memory_saved,
                'savings_percentage': (memory_saved / total_initial * 100) if total_initial > 0 else 0
            }
        }
        
        self.logger.info(
            "Memory optimization completed",
            extra={
                'optimization_stats': optimization_stats,
                'memory_saved_mb': memory_saved / (1024 * 1024)
            }
        )
        
        return optimization_stats
    
    async def _create_claude_process(self) -> SubprocessClaudeHandler:
        """Create a new Claude process for the connection pool."""
        handler = SubprocessClaudeHandler(self.config.claude)
        await handler.start()
        return handler
    
    def _check_process_health(self, process: SubprocessClaudeHandler) -> bool:
        """Check if a Claude process is healthy."""
        return process.is_running() if hasattr(process, 'is_running') else True
    
    def _create_response_cache_key(self, session_id: str, message: str) -> str:
        """Create a cache key for response caching."""
        import hashlib
        content = f"{session_id}:{message}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def _cache_cleanup_loop(self) -> None:
        """Background task for cache cleanup."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean up expired entries
                session_expired = await self.session_cache.cleanup_expired()
                response_expired = await self.response_cache.cleanup_expired()
                
                if session_expired > 0 or response_expired > 0:
                    self.logger.info(
                        f"Cache cleanup: {session_expired} sessions, {response_expired} responses expired"
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cache cleanup: {e}")
    
    async def _metrics_reporting_loop(self) -> None:
        """Background task for metrics reporting."""
        while self.is_running:
            try:
                await asyncio.sleep(self.metrics_report_interval)
                
                # Get and log metrics
                metrics = await self.get_session_metrics()
                
                self.logger.info(
                    "Performance metrics report",
                    extra={'metrics': metrics}
                )
                
                # Reset performance metrics to avoid memory growth
                await performance_metrics.reset()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics reporting: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for the enhanced session manager."""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        try:
            # Check base session manager
            base_health = await super().get_session_status()
            health_status['components']['session_manager'] = {
                'status': 'healthy',
                'details': base_health
            }
            
            # Check caches
            session_cache_stats = await self.session_cache.get_stats()
            response_cache_stats = await self.response_cache.get_stats()
            
            health_status['components']['caching'] = {
                'status': 'healthy',
                'session_cache': session_cache_stats,
                'response_cache': response_cache_stats
            }
            
            # Check rate limiter
            health_status['components']['rate_limiter'] = {
                'status': 'healthy',
                'rate': self.claude_rate_limiter.rate,
                'burst': self.claude_rate_limiter.burst,
                'current_tokens': self.claude_rate_limiter.tokens
            }
            
            # Check background tasks
            health_status['components']['background_tasks'] = {
                'cache_cleanup': not (self.cache_cleanup_task and self.cache_cleanup_task.done()),
                'metrics_reporting': not (self.metrics_task and self.metrics_task.done())
            }
            
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
            self.logger.error(f"Health check failed: {e}")
        
        return health_status
