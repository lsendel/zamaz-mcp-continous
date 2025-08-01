"""
Simplified tests for enhanced session manager.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from claude_remote_client.session_manager.enhanced_session_manager import EnhancedSessionManager
from claude_remote_client.enhanced_config import EnhancedConfig
from claude_remote_client.config import SlackConfig, ClaudeConfig
from claude_remote_client.models import ClaudeSession, SessionStatus
from claude_remote_client.performance import LRUCache, ConnectionPool, RateLimiter


class TestEnhancedSessionManagerBasic:
    """Basic tests for EnhancedSessionManager."""
    
    def test_initialization(self):
        """Test basic initialization."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude"),
            max_sessions=5
        )
        
        # Mock dependencies
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Check core attributes
            assert manager.config == config
            assert isinstance(manager.session_cache, LRUCache)
            assert isinstance(manager.response_cache, LRUCache)
            assert isinstance(manager.claude_rate_limiter, RateLimiter)
            assert manager.metrics_enabled is True
    
    def test_cache_key_creation(self):
        """Test response cache key creation."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            key1 = manager._create_response_cache_key("session1", "message1")
            key2 = manager._create_response_cache_key("session1", "message1")
            key3 = manager._create_response_cache_key("session1", "message2")
            
            # Same inputs should produce same key
            assert key1 == key2
            # Different inputs should produce different keys
            assert key1 != key3
    
    def test_process_health_check(self):
        """Test process health check logic."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Test with process that has is_running method
            mock_process = MagicMock()
            mock_process.is_running.return_value = True
            assert manager._check_process_health(mock_process) is True
            
            mock_process.is_running.return_value = False
            assert manager._check_process_health(mock_process) is False
            
            # Test with process without is_running method
            mock_process_no_method = MagicMock()
            del mock_process_no_method.is_running
            assert manager._check_process_health(mock_process_no_method) is True
    
    @pytest.mark.asyncio
    async def test_session_cache_operations(self):
        """Test session cache operations."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Create test session
            session = ClaudeSession(
                session_id="test-123",
                project_path="/test/path",
                created_at=datetime.now(),
                status=SessionStatus.ACTIVE
            )
            
            # Test cache set and get
            await manager.session_cache.set("test-123", session)
            cached = await manager.session_cache.get("test-123")
            
            assert cached is not None
            assert cached.session_id == "test-123"
    
    @pytest.mark.asyncio
    async def test_response_cache_operations(self):
        """Test response cache operations."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Test cache operations
            cache_key = "test-key"
            response = "test response"
            
            await manager.response_cache.set(cache_key, response)
            cached = await manager.response_cache.get(cache_key)
            
            assert cached == response
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test rate limiter basic functionality."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Rate limiter should allow initial requests
            result = await manager.claude_rate_limiter.acquire()
            assert result is True


class TestEnhancedSessionManagerMethods:
    """Tests for EnhancedSessionManager methods."""
    
    @pytest.mark.asyncio
    async def test_get_session_with_cache_hit(self):
        """Test get_session when item is in cache."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Create test session
            session = ClaudeSession(
                session_id="test-123",
                project_path="/test/path",
                created_at=datetime.now(),
                status=SessionStatus.ACTIVE
            )
            
            # Pre-populate cache
            await manager.session_cache.set("test-123", session)
            
            # Mock performance metrics
            with patch('claude_remote_client.session_manager.enhanced_session_manager.performance_metrics') as mock_metrics:
                mock_metrics.increment_counter = AsyncMock()
                
                # Get session (should hit cache)
                result = await manager.get_session("test-123")
                
                assert result == session
                mock_metrics.increment_counter.assert_called_with("session_cache_hits")
    
    def test_cache_operations_complete(self):
        """Test complete cache operations flow."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        with patch('claude_remote_client.session_manager.session_manager.setup_logging'):
            manager = EnhancedSessionManager(config)
            
            # Test that caches are properly initialized
            assert manager.session_cache is not None
            assert manager.response_cache is not None
            
            # Test cache stats methods exist
            assert hasattr(manager.session_cache, 'get_stats')
            assert hasattr(manager.response_cache, 'get_stats')