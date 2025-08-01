"""
Unit tests for session manager.
"""

import pytest
import asyncio
import tempfile
import json
from unittest.mock import AsyncMock, MagicMock, patch
import aiofiles
import aiofiles.os
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
        assert manager.active_sessions == {}
        assert manager.max_sessions == temp_config.max_sessions
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, session_manager):
        """Test session manager start/stop lifecycle."""
        # Initially not running
        assert not session_manager.is_running
        
        # Start the manager
        await session_manager.start()
        assert session_manager.is_running
        
        # Stop the manager
        await session_manager.stop()
        assert not session_manager.is_running
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, session_manager, temp_project_dir):
        """Test successful session creation."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            session = await session_manager.create_session(
                project_path=temp_project_dir,
                project_name="test-project"
            )
            
            assert isinstance(session, ClaudeSession)
            assert session.project_path == temp_project_dir
            assert session.project_name == "test-project"
            assert session.status == SessionStatus.ACTIVE
            assert session.session_id in session_manager.active_sessions
            
            mock_handler.return_value.start_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_session_max_limit(self, session_manager, temp_project_dir):
        """Test session creation respects max limit."""
        await session_manager.start()
        session_manager.max_sessions = 2
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Create max sessions
            session1 = await session_manager.create_session(temp_project_dir, "project1")
            session2 = await session_manager.create_session(temp_project_dir, "project2")
            
            # Third session should fail
            with pytest.raises(SessionError, match="Maximum number of sessions"):
                await session_manager.create_session(temp_project_dir, "project3")
    
    @pytest.mark.asyncio
    async def test_get_session(self, session_manager, temp_project_dir):
        """Test getting existing session."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Create session
            created_session = await session_manager.create_session(temp_project_dir, "test")
            
            # Get session
            retrieved_session = await session_manager.get_session(created_session.session_id)
            
            assert retrieved_session == created_session
            assert retrieved_session.session_id == created_session.session_id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Test getting non-existent session raises error."""
        await session_manager.start()
        
        with pytest.raises(SessionError, match="Session not found"):
            await session_manager.get_session("nonexistent-id")
    
    @pytest.mark.asyncio
    async def test_switch_session(self, session_manager, temp_project_dir):
        """Test switching between sessions."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Create two sessions
            session1 = await session_manager.create_session(temp_project_dir, "project1")
            session2 = await session_manager.create_session(temp_project_dir, "project2")
            
            # Switch to session1
            current = await session_manager.switch_session(session1.session_id)
            assert current == session1
            assert session_manager.current_session_id == session1.session_id
            
            # Switch to session2
            current = await session_manager.switch_session(session2.session_id)
            assert current == session2
            assert session_manager.current_session_id == session2.session_id
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager, temp_project_dir):
        """Test listing all sessions."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Initially empty
            sessions = await session_manager.list_sessions()
            assert len(sessions) == 0
            
            # Create sessions
            session1 = await session_manager.create_session(temp_project_dir, "project1")
            session2 = await session_manager.create_session(temp_project_dir, "project2")
            
            # List sessions
            sessions = await session_manager.list_sessions()
            assert len(sessions) == 2
            
            session_ids = [s.session_id for s in sessions]
            assert session1.session_id in session_ids
            assert session2.session_id in session_ids
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self, session_manager, temp_project_dir):
        """Test session cleanup."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            mock_handler.return_value.stop_process = AsyncMock()
            
            # Create session
            session = await session_manager.create_session(temp_project_dir, "test")
            session_id = session.session_id
            
            # Verify session exists
            assert session_id in session_manager.active_sessions
            
            # Cleanup session
            await session_manager.cleanup_session(session_id)
            
            # Verify session removed
            assert session_id not in session_manager.active_sessions
            mock_handler.return_value.stop_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_session(self, session_manager):
        """Test cleanup of non-existent session."""
        await session_manager.start()
        
        # Should not raise error
        await session_manager.cleanup_session("nonexistent-id")
    
    @pytest.mark.asyncio
    async def test_send_message_to_session(self, session_manager, temp_project_dir):
        """Test sending message to session."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            mock_handler.return_value.send_message = AsyncMock()
            
            # Create session
            session = await session_manager.create_session(temp_project_dir, "test")
            
            # Send message
            message = "Hello Claude!"
            await session_manager.send_message(session.session_id, message)
            
            mock_handler.return_value.send_message.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_session_persistence(self, session_manager, temp_project_dir):
        """Test session state persistence."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Create session
            session = await session_manager.create_session(temp_project_dir, "test")
            session.add_message("user", "Test message")
            
            # Save session state
            await session_manager.save_session_state(session.session_id)
            
            # Verify state file exists
            state_file = Path(session_manager.config.data_dir) / "sessions" / f"{session.session_id}.json"
            assert state_file.exists()
            
            # Load and verify state
            loaded_session = await session_manager.load_session_state(session.session_id)
            assert loaded_session.session_id == session.session_id
            assert len(loaded_session.conversation_history) == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_process_failure(self, session_manager, temp_project_dir):
        """Test error handling when Claude process fails."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock(side_effect=Exception("Process failed"))
            
            with pytest.raises(SessionError, match="Failed to create session"):
                await session_manager.create_session(temp_project_dir, "test")
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, session_manager, temp_project_dir):
        """Test concurrent session operations."""
        await session_manager.start()
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessHandler') as mock_handler:
            mock_handler.return_value.start_process = AsyncMock()
            
            # Create multiple sessions concurrently
            tasks = []
            for i in range(3):
                task = session_manager.create_session(temp_project_dir, f"project{i}")
                tasks.append(task)
            
            sessions = await asyncio.gather(*tasks)
            
            # Verify all sessions created
            assert len(sessions) == 3
            assert len(session_manager.active_sessions) == 3
            
            # Verify unique session IDs
            session_ids = [s.session_id for s in sessions]
            assert len(set(session_ids)) == 3
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
    async def test_create_session_failure_cleanup(self, mock_streamer_class, mock_handler_class,
                                                session_manager, temp_project_dir):
        """Test that create_session cleans up partially created resources on failure."""
        # Mock SubprocessClaudeHandler to raise an exception during start_process
        mock_handler = AsyncMock()
        mock_handler.start_process.side_effect = Exception("Test subprocess error")
        mock_handler.terminate_process = AsyncMock() # Ensure terminate is mocked
        mock_handler_class.return_value = mock_handler

        # Mock MessageStreamer
        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer.stop_streaming = AsyncMock() # Ensure stop is mocked
        mock_streamer_class.return_value = mock_streamer

        # Ensure initial state is empty
        assert len(session_manager.sessions) == 0
        assert len(session_manager.subprocess_handlers) == 0
        assert len(session_manager.message_streamers) == 0

        with pytest.raises(SessionError) as exc_info:
            await session_manager.create_session(temp_project_dir)

        assert "Failed to create session" in str(exc_info.value)

        # Verify that no session was added to the manager's state
        assert len(session_manager.sessions) == 0
        assert len(session_manager.subprocess_handlers) == 0
        assert len(session_manager.message_streamers) == 0

        # Verify that terminate_process was called on the partially created handler
        mock_handler.terminate_process.assert_called_once()
        # Verify that stop_streaming was NOT called on the streamer, as it wouldn't have started
        mock_streamer.stop_streaming.assert_not_called()

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
        mock_handler.start_process.assert_called_once_with(session, resume_claude_session=None)
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
    async def test_cleanup_loop_responsiveness(self, session_manager):
        """Test that the cleanup loop is responsive to session timeouts."""
        session_manager.is_running = True
        session_manager.session_timeout = 10  # Set a short timeout for testing

        # Mock the instance methods directly
        session_manager.health_check_sessions = AsyncMock()
        session_manager._cleanup_inactive_sessions = AsyncMock()
        session_manager._save_sessions = AsyncMock()

        # Mock asyncio.sleep and asyncio.wait globally or within the test
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
             patch('asyncio.wait', new_callable=AsyncMock) as mock_wait:

            # Mock asyncio.wait to return immediately with a completed task
            mock_wait.return_value = ([asyncio.Future()], [])  # Simulate one task completing

            # Run the cleanup loop for a short period
            cleanup_task = asyncio.create_task(session_manager._cleanup_loop())
            await asyncio.sleep(0.1)  # Allow the loop to run at least once
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

            # Verify that health check, cleanup, and save were called
            session_manager.health_check_sessions.assert_called_once()
            session_manager._cleanup_inactive_sessions.assert_called_once()
            session_manager._save_sessions.assert_called_once()

            # Verify that health check, cleanup, and save were called
            session_manager.health_check_sessions.assert_called_once()
            session_manager._cleanup_inactive_sessions.assert_called_once()
            session_manager._save_sessions.assert_called_once()

            # Verify that asyncio.wait was called, indicating responsiveness
            mock_wait.assert_called_once()
            mock_sleep.assert_called_once_with(60) # Should call sleep if no timeout_tasks

    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_switch_session_inactive_state(self, mock_streamer_class, mock_handler_class,
                                                session_manager, temp_project_dir):
        """Test switching to a session in an inactive state."""
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler

        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer

        session = await session_manager.create_session(temp_project_dir)
        session.status = SessionStatus.INACTIVE # Manually set to inactive

        switched_session = await session_manager.switch_session(session.session_id)
        assert switched_session == session
        assert session_manager.active_session_id == session.session_id

    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_switch_session_error_state(self, mock_streamer_class, mock_handler_class,
                                            session_manager, temp_project_dir):
        """Test switching to a session in an error state."""
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler

        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer

        session = await session_manager.create_session(temp_project_dir)
        session.status = SessionStatus.ERROR # Manually set to error

        with pytest.raises(SessionError) as exc_info:
            await session_manager.switch_session(session.session_id)
        assert "Cannot switch to session in error state" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_switch_session_already_active(self, mock_streamer_class, mock_handler_class,
                                                session_manager, temp_project_dir):
        """Test switching to a session that is already active."""
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler_class.return_value = mock_handler

        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer

        session = await session_manager.create_session(temp_project_dir)
        initial_active_id = session.session_id

        switched_session = await session_manager.switch_session(session.session_id)
        assert switched_session == session
        assert session_manager.active_session_id == initial_active_id

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
    async def test_terminate_session_inactive(self, mock_streamer_class, mock_handler_class,
                                            session_manager, temp_project_dir):
        """Test terminating an already inactive session."""
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler.terminate_process = AsyncMock()
        mock_handler_class.return_value = mock_handler

        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer.stop_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer

        session = await session_manager.create_session(temp_project_dir)
        session.status = SessionStatus.INACTIVE # Manually set to inactive

        session_id = session.session_id
        await session_manager.terminate_session(session_id)

        assert session_id not in session_manager.sessions
        mock_streamer.stop_streaming.assert_called_once()
        mock_handler.terminate_process.assert_called_once()

    @pytest.mark.asyncio
    @patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler')
    @patch('claude_remote_client.session_manager.session_manager.MessageStreamer')
    async def test_terminate_active_session_and_switch(self, mock_streamer_class, mock_handler_class,
                                                    session_manager, temp_project_dir):
        """Test terminating the active session and ensuring a new active session is selected."""
        mock_handler = AsyncMock()
        mock_handler.start_process = AsyncMock()
        mock_handler.terminate_process = AsyncMock()
        mock_handler_class.return_value = mock_handler

        mock_streamer = AsyncMock()
        mock_streamer.start_streaming = AsyncMock()
        mock_streamer.stop_streaming = AsyncMock()
        mock_streamer_class.return_value = mock_streamer

        session1 = await session_manager.create_session(temp_project_dir)
        session2 = await session_manager.create_session(temp_project_dir)

        # Explicitly switch to session2 to make it active
        await session_manager.switch_session(session2.session_id)

        # session2 is active
        assert session_manager.active_session_id == session2.session_id

        # Terminate session2 (active one)
        await session_manager.terminate_session(session2.session_id)

        assert session2.session_id not in session_manager.sessions
        # session1 should now be active
        assert session_manager.active_session_id == session1.session_id

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
    @patch('aiofiles.open', new_callable=AsyncMock)
    @patch('aiofiles.os.path.exists', new_callable=AsyncMock)
    async def test_save_load_sessions(self, mock_exists, mock_open, session_manager, temp_project_dir):
        """Test saving and loading sessions."""
        # Mock aiofiles.os.path.exists to return True for the sessions file
        mock_exists.return_value = True

        # Mock the file content for loading
        mock_file_content = json.dumps({
            'active_session_id': 'test-session-id',
            'sessions': [{
                'session_id': 'test-session-id',
                'project_path': temp_project_dir,
                'project_name': 'test-project',
                'status': SessionStatus.INACTIVE.value,
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat()
            }]
        })
        # Mock aiofiles.open for reading
        mock_read_context = AsyncMock()
        mock_read_context.read.return_value = mock_file_content

        # Mock aiofiles.open for writing
        mock_write_context = AsyncMock()
        mock_write_context.write.return_value = None

        mock_open.side_effect = [mock_read_context, mock_write_context]

        # Create a session manually for testing persistence
        session = ClaudeSession(
            session_id='test-session-id',
            project_path=temp_project_dir,
            project_name='test-project'
        )
        session_manager.sessions[session.session_id] = session
        session_manager.active_session_id = session.session_id

        # Save sessions
        await session_manager._save_sessions()

        # Verify aiofiles.open was called for writing
        mock_open.assert_called_with(session_manager.sessions_file, 'w')
        mock_open.return_value.__aenter__.return_value.write.assert_called_once()

        # Clear sessions and load
        session_manager.sessions.clear()
        session_manager.active_session_id = None

        await session_manager._load_sessions()

        # Verify aiofiles.open was called for reading
        mock_open.assert_called_with(session_manager.sessions_file, 'r')

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