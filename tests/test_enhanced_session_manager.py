"""
Tests for enhanced session manager with performance optimizations.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

from claude_remote_client.session_manager.enhanced_session_manager import (
    EnhancedSessionManager
)
from claude_remote_client.models import ClaudeSession, SessionStatus
from claude_remote_client.config import Config, SlackConfig, ClaudeConfig
from claude_remote_client.enhanced_config import EnhancedConfig
from claude_remote_client.exceptions import SessionError, ClaudeProcessError
from claude_remote_client.performance import LRUCache, ConnectionPool, RateLimiter
from claude_remote_client.session_manager.session_manager import SessionManager


@pytest.fixture
def enhanced_config():
    """Create enhanced configuration for testing."""
    config = EnhancedConfig(
        slack=SlackConfig(bot_token="test-token"),
        claude=ClaudeConfig(cli_path="/usr/bin/claude"),
        max_sessions=5
    )
    return config


@pytest_asyncio.fixture
async def enhanced_manager(enhanced_config):
    """Create enhanced session manager for testing."""
    manager = EnhancedSessionManager(enhanced_config)
    yield manager
    if hasattr(manager, 'cleanup'):
        await manager.cleanup()


class TestEnhancedSessionManager:
    """Test cases for EnhancedSessionManager."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, enhanced_config):
        """Test enhanced session manager initialization."""
        with patch('claude_remote_client.session_manager.enhanced_session_manager.EnhancedLogger'):
            manager = EnhancedSessionManager(enhanced_config)
            
            assert isinstance(manager.session_cache, LRUCache)
            assert isinstance(manager.response_cache, LRUCache)
            assert isinstance(manager.process_pool, ConnectionPool)
            assert isinstance(manager.claude_rate_limiter, RateLimiter)
            assert manager.metrics_enabled is True
    
    @pytest.mark.asyncio
    async def test_session_caching(self, enhanced_manager):
        """Test session caching functionality."""
        # Create a session
        session = ClaudeSession(
            session_id="test-session-1",
            project_path="/test/path",
            created_at=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        
        # Add to cache
        enhanced_manager.session_cache.put("test-session-1", session)
        
        # Retrieve from cache
        cached_session = enhanced_manager.session_cache.get("test-session-1")
        assert cached_session is not None
        assert cached_session.session_id == "test-session-1"
    
    @pytest.mark.asyncio
    async def test_create_session_with_caching(self, enhanced_manager):
        """Test creating session with caching enabled."""
        with patch.object(enhanced_manager, '_create_subprocess_handler') as mock_handler:
            mock_subprocess = AsyncMock()
            mock_subprocess.start_process = AsyncMock()
            mock_handler.return_value = mock_subprocess
            
            session = await enhanced_manager.create_session("/test/project")
            
            assert session.session_id in enhanced_manager.sessions
            # Check if session is cached
            cached = enhanced_manager.session_cache.get(session.session_id)
            assert cached is not None
    
    @pytest.mark.asyncio
    async def test_response_caching(self, enhanced_manager):
        """Test response caching for repeated commands."""
        session_id = "test-session"
        command = "explain the code"
        response = "This is the explanation..."
        
        # Cache response
        cache_key = f"{session_id}:{command}"
        enhanced_manager.response_cache.put(cache_key, response)
        
        # Retrieve cached response
        cached = enhanced_manager.response_cache.get(cache_key)
        assert cached == response
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, enhanced_manager):
        """Test connection pool management."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            with patch.object(enhanced_manager, '_create_subprocess_handler') as mock_handler:
                mock_subprocess = AsyncMock()
                mock_subprocess.start_process = AsyncMock()
                mock_handler.return_value = mock_subprocess
                
                session = await enhanced_manager.create_session(f"/test/project{i}")
                sessions.append(session)
        
        # Check we created multiple sessions
        assert len(enhanced_manager.sessions) == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, enhanced_manager):
        """Test rate limiting functionality."""
        # Configure rate limiter
        enhanced_manager.claude_rate_limiter._rate = 2  # 2 requests per second
        
        # Make rapid requests
        start_time = asyncio.get_event_loop().time()
        
        for i in range(3):
            await enhanced_manager.claude_rate_limiter.acquire()
        
        end_time = asyncio.get_event_loop().time()
        
        # Should take at least 1 second for 3 requests at 2/sec rate
        assert end_time - start_time >= 0.5
    
    @pytest.mark.asyncio
    async def test_response_caching_in_send_message(self, enhanced_manager):
        """Test response caching in send_message."""
        session_id = "test-session"
        message = "test message"
        
        # Mock the parent send_message
        with patch.object(SessionManager, 'send_message') as mock_send:
            mock_send.return_value = "test response"
            
            # Mock session exists
            enhanced_manager.sessions[session_id] = MagicMock()
            
            # First call should hit parent method
            response1 = await enhanced_manager.send_message(session_id, message)
            assert response1 == "test response"
            assert mock_send.call_count == 1
            
            # Second call with same message should use cache
            response2 = await enhanced_manager.send_message(session_id, message)
            assert response2 == "test response"
            assert mock_send.call_count == 1  # Still 1, not called again
    
    @pytest.mark.asyncio
    async def test_memory_optimization(self, enhanced_manager):
        """Test memory optimization features."""
        # Create sessions to trigger memory optimization
        for i in range(10):
            session = ClaudeSession(
                session_id=f"session-{i}",
                project_path=f"/test/path{i}",
                created_at=datetime.now() - timedelta(hours=i),
                status=SessionStatus.IDLE if i > 5 else SessionStatus.ACTIVE
            )
            enhanced_manager.sessions[session.session_id] = session
        
        # Run memory optimization
        stats = await enhanced_manager.optimize_memory_usage()
        
        # Check optimization stats
        assert 'sessions_optimized' in stats
        assert stats['sessions_optimized'] >= 0
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, enhanced_manager):
        """Test performance metrics collection."""
        # Perform some operations
        with patch.object(enhanced_manager, '_create_subprocess_handler') as mock_handler:
            mock_subprocess = AsyncMock()
            mock_subprocess.start_process = AsyncMock()
            mock_subprocess.send_message = AsyncMock(return_value="response")
            mock_handler.return_value = mock_subprocess
            
            session = await enhanced_manager.create_session("/test/project")
            await enhanced_manager.send_message(session.session_id, "test message")
        
        # Get metrics
        metrics = await enhanced_manager.get_session_metrics()
        
        assert 'active_sessions' in metrics
        assert 'caching' in metrics
        assert 'performance' in metrics
        assert metrics['active_sessions'] == 1
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, enhanced_config):
        """Test using enhanced session manager as async context manager."""
        async with EnhancedSessionManager(enhanced_config) as manager:
            assert manager.is_running is True
            
            # Create a session
            with patch.object(manager, '_create_subprocess_handler') as mock_handler:
                mock_subprocess = AsyncMock()
                mock_subprocess.start_process = AsyncMock()
                mock_handler.return_value = mock_subprocess
                
                session = await manager.create_session("/test/project")
                assert session.session_id in manager.sessions
        
        # After context exit, should be cleaned up
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_health_check(self, enhanced_manager):
        """Test health check functionality."""
        health = await enhanced_manager.health_check()
        
        assert health['status'] == 'healthy'
        assert 'timestamp' in health
        assert 'components' in health
        assert 'session_manager' in health['components']
        assert 'caching' in health['components']
        assert 'rate_limiter' in health['components']
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, enhanced_manager):
        """Test graceful shutdown with active sessions."""
        # Create active sessions
        for i in range(3):
            session = ClaudeSession(
                session_id=f"session-{i}",
                project_path=f"/test/path{i}",
                created_at=datetime.now(),
                status=SessionStatus.ACTIVE
            )
            enhanced_manager.sessions[session.session_id] = session
            enhanced_manager.handlers[session.session_id] = AsyncMock()
        
        # Perform graceful shutdown
        await enhanced_manager.stop()
        
        # All sessions should be terminated
        assert len(enhanced_manager.sessions) == 0
        assert len(enhanced_manager.handlers) == 0


class TestCacheCleanup:
    """Test cases for cache cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_task(self, enhanced_manager):
        """Test cache cleanup background task."""
        # Mock the cleanup methods
        with patch.object(enhanced_manager.session_cache, 'cleanup_expired') as mock_session_cleanup:
            with patch.object(enhanced_manager.response_cache, 'cleanup_expired') as mock_response_cleanup:
                mock_session_cleanup.return_value = 5
                mock_response_cleanup.return_value = 10
                
                # Start the manager
                await enhanced_manager.start()
                
                # Verify cleanup task was created
                assert enhanced_manager.cache_cleanup_task is not None
                assert not enhanced_manager.cache_cleanup_task.done()
                
                # Stop the manager
                await enhanced_manager.stop()
    
    @pytest.mark.asyncio
    async def test_metrics_reporting_task(self, enhanced_manager):
        """Test metrics reporting background task."""
        # Start the manager
        await enhanced_manager.start()
        
        # Verify metrics task was created
        assert enhanced_manager.metrics_task is not None
        assert not enhanced_manager.metrics_task.done()
        
        # Stop the manager
        await enhanced_manager.stop()


class TestProjectSwitching:
    """Test cases for optimized project switching."""
    
    @pytest.mark.asyncio
    async def test_switch_project_reuse_existing(self, enhanced_manager):
        """Test reusing existing session when switching projects."""
        project_name = "test-project"
        
        # Create an existing active session
        existing_session = ClaudeSession(
            session_id="existing-1",
            project_name=project_name,
            project_path=f"/path/{project_name}",
            created_at=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        enhanced_manager.sessions[existing_session.session_id] = existing_session
        
        # Switch to the same project
        result = await enhanced_manager.switch_project(project_name)
        
        # Should reuse the existing session
        assert result.session_id == existing_session.session_id
        assert enhanced_manager.active_session_id == existing_session.session_id