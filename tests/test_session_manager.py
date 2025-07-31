"""
Unit tests for session manager.
"""

import pytest
import asyncio
import tempfile
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import datetime

from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.config import Config, ClaudeConfig, SlackConfig
from claude_remote_client.models import ClaudeSession, SessionStatus
from claude_remote_client.exceptions import SessionError


@pytest.fixture
def temp_config():
    """Create a test configuration with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            data_dir=temp_dir,
            max_sessions=5,
            claude=ClaudeConfig(cli_path="claude"),
            slack=SlackConfig()
        )
        yield config


@pytest.fixture
def session_manager(temp_config):
    """Create a session manager with test configuration."""
    return SessionManager(temp_config)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


class TestSessionManager:
    """Test cases for SessionManager."""
    
    def test_manager_initialization(self, temp_config):
        """Test session manager initialization."""
        manager = SessionManager(temp_config)
        
        assert manager.config == temp_config
        assert manager.sessions == {}
        assert manager.subprocess_handlers == {}
        assert manager.message_streamers == {}
        assert manager.active_session_id is None
        assert manager.max_sessions == 5
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_start_stop_manager(self, session_manager):
        """Test starting and stopping the session manager."""
        # Start manager
        await session_manager.start()
        
        assert session_manager.is_running is True
        assert session_manager.cleanup_task is not None
        
        # Stop manager
        await session_manager.stop()
        
        assert session_manager.is_running is False
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_create_session_success(self, mock_streamer_class, mock_handler_class, 
                                        session_manager, temp_project_dir):
        """Test successful session creation."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        
        # Verify session was created
        assert isinstance(session, ClaudeSession)
        assert session.project_path == temp_project_dir
        assert session.session_id in session_manager.sessions
        assert session_manager.active_session_id == session.session_id
        
        # Verify handlers were created and started
        mock_handler.start_process.assert_called_once_with(session)
        mock_streamer.start_streaming.assert_called_once_with(session)
    
    @pytest.mark.asyncio
    async def test_create_session_invalid_path(self, session_manager):
        """Test session creation with invalid project path."""
        with pytest.raises(SessionError) as exc_info:
            await session_manager.create_session("/nonexistent/path")
        
        assert "Invalid project path" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_create_session_max_sessions(self, mock_streamer_class, mock_handler_class,
                                             session_manager, temp_project_dir):
        """Test session creation when max sessions reached."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Set low max sessions limit
        session_manager.max_sessions = 1
        
        # Create first session
        await session_manager.create_session(temp_project_dir)
        
        # Try to create second session
        with pytest.raises(SessionError) as exc_info:
            await session_manager.create_session(temp_project_dir)
        
        assert "Maximum number of sessions" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_switch_session(self, mock_streamer_class, mock_handler_class,
                                session_manager, temp_project_dir):
        """Test switching between sessions."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create two sessions
        session1 = await session_manager.create_session(temp_project_dir)
        session2 = await session_manager.create_session(temp_project_dir)
        
        # Initially, session1 should be active
        assert session_manager.active_session_id == session1.session_id
        
        # Switch to session2
        switched_session = await session_manager.switch_session(session2.session_id)
        
        assert switched_session == session2
        assert session_manager.active_session_id == session2.session_id
    
    @pytest.mark.asyncio
    async def test_switch_session_not_found(self, session_manager):
        """Test switching to non-existent session."""
        with pytest.raises(SessionError) as exc_info:
            await session_manager.switch_session("nonexistent-session")
        
        assert "Session nonexistent-session not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_get_active_session(self, mock_streamer_class, mock_handler_class,
                                    session_manager, temp_project_dir):
        """Test getting active session."""
        # No active session initially
        active = await session_manager.get_active_session()
        assert active is None
        
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        
        # Should now have active session
        active = await session_manager.get_active_session()
        assert active == session
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_list_sessions(self, mock_streamer_class, mock_handler_class,
                               session_manager, temp_project_dir):
        """Test listing sessions."""
        # Empty list initially
        sessions = await session_manager.list_sessions()
        assert sessions == []
        
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler.get_process_info = MagicMock(return_value={"is_running": True})
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer.get_streaming_stats = MagicMock(return_value={"is_streaming": True})
        mock_streamer_class.return_value = mock_streamer
        
        # Create sessions
        session1 = await session_manager.create_session(temp_project_dir)
        session2 = await session_manager.create_session(temp_project_dir)
        
        # List sessions
        sessions = await session_manager.list_sessions()
        
        assert len(sessions) == 2
        assert all("session_id" in s for s in sessions)
        assert all("project_name" in s for s in sessions)
        assert all("status" in s for s in sessions)
        assert any(s["is_active"] for s in sessions)  # One should be active
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_terminate_session(self, mock_streamer_class, mock_handler_class,
                                   session_manager, temp_project_dir):
        """Test terminating a session."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler.terminate_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer.stop_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        session_id = session.session_id
        
        # Verify session exists
        assert session_id in session_manager.sessions
        assert session_manager.active_session_id == session_id
        
        # Terminate session
        await session_manager.terminate_session(session_id)
        
        # Verify session was removed
        assert session_id not in session_manager.sessions
        assert session_manager.active_session_id is None
        
        # Verify handlers were cleaned up
        mock_streamer.stop_streaming.assert_called_once()
        mock_handler.terminate_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_terminate_session_not_found(self, session_manager):
        """Test terminating non-existent session."""
        with pytest.raises(SessionError) as exc_info:
            await session_manager.terminate_session("nonexistent-session")
        
        assert "Session nonexistent-session not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_get_session_handler(self, mock_streamer_class, mock_handler_class,
                                     session_manager, temp_project_dir):
        """Test getting session handler."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        
        # Get handler
        handler = await session_manager.get_session_handler(session.session_id)
        assert handler == mock_handler
        
        # Non-existent session
        handler = await session_manager.get_session_handler("nonexistent")
        assert handler is None
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_get_session_streamer(self, mock_streamer_class, mock_handler_class,
                                      session_manager, temp_project_dir):
        """Test getting session streamer."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        
        # Get streamer
        streamer = await session_manager.get_session_streamer(session.session_id)
        assert streamer == mock_streamer
        
        # Non-existent session
        streamer = await session_manager.get_session_streamer("nonexistent")
        assert streamer is None
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_health_check_sessions(self, mock_streamer_class, mock_handler_class,
                                       session_manager, temp_project_dir):
        """Test health checking sessions."""
        # Mock handlers
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler.health_check = AsyncMock(return_value=True)
        mock_handler_class.return_value = mock_handler
        
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer
        
        # Create session
        session = await session_manager.create_session(temp_project_dir)
        
        # Health check
        health_status = await session_manager.health_check_sessions()
        
        assert session.session_id in health_status
        assert health_status[session.session_id] is True
        mock_handler.health_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_load_sessions(self, session_manager, temp_project_dir):
        """Test saving and loading sessions."""
        # Create a session manually for testing persistence
        session = ClaudeSession(
            project_path=temp_project_dir,
            project_name="test-project"
        )
        session_manager.sessions[session.session_id] = session
        session_manager.active_session_id = session.session_id
        
        # Save sessions
        await session_manager._save_sessions()
        
        # Verify file was created
        assert session_manager.sessions_file.exists()
        
        # Clear sessions and load
        session_manager.sessions.clear()
        session_manager.active_session_id = None
        
        await session_manager._load_sessions()
        
        # Verify session was loaded
        assert session.session_id in session_manager.sessions
        assert session_manager.active_session_id == session.session_id
        
        loaded_session = session_manager.sessions[session.session_id]
        assert loaded_session.project_path == temp_project_dir
        assert loaded_session.project_name == "test-project"
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(self, session_manager, temp_project_dir):
        """Test cleanup of inactive sessions."""
        # Create a session and mark it as old
        session = ClaudeSession(
            project_path=temp_project_dir,
            project_name="test-project",
            status=SessionStatus.INACTIVE
        )
        # Set old timestamp
        session.last_activity = datetime.fromtimestamp(0)  # Very old
        
        session_manager.sessions[session.session_id] = session
        session_manager.session_timeout = 1  # 1 second timeout for testing
        
        # Run cleanup
        await session_manager._cleanup_inactive_sessions()
        
        # Session should be removed
        assert session.session_id not in session_manager.sessions
    
    def test_get_manager_stats(self, session_manager, temp_project_dir):
        """Test getting manager statistics."""
        # Add a session manually
        session = ClaudeSession(
            project_path=temp_project_dir,
            project_name="test-project"
        )
        session_manager.sessions[session.session_id] = session
        session_manager.active_session_id = session.session_id
        
        stats = session_manager.get_manager_stats()
        
        assert stats["is_running"] is False
        assert stats["total_sessions"] == 1
        assert stats["active_session_id"] == session.session_id
        assert stats["max_sessions"] == 5
        assert "session_statuses" in stats
        assert stats["session_statuses"]["inactive"] == 1