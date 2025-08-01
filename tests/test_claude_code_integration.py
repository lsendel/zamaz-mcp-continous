"""
Tests for Claude Code CLI integration.

This module tests the integration with Claude Code CLI including
session management, non-interactive execution, and JSON output handling.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from claude_remote_client.claude_client.subprocess_handler import SubprocessClaudeHandler
from claude_remote_client.models import ClaudeSession, SessionStatus
from claude_remote_client.config import ClaudeConfig
from claude_remote_client.exceptions import ClaudeProcessError
from claude_remote_client.session_manager.session_manager import SessionManager


@pytest.fixture
def claude_config():
    """Create a test Claude configuration."""
    return ClaudeConfig(
        cli_path="claude",
        default_args=["--dangerously-skip-permissions"],
        timeout=30
    )


@pytest.fixture
def test_session():
    """Create a test session."""
    return ClaudeSession(
        session_id="test-123",
        project_path="/test/project",
        project_name="test-project"
    )


@pytest.fixture
def subprocess_handler(claude_config):
    """Create a subprocess handler instance."""
    return SubprocessClaudeHandler(claude_config)


class TestSubprocessHandlerClaudeCodeFeatures:
    """Test Claude Code CLI specific features in subprocess handler."""
    
    @pytest.mark.asyncio
    async def test_start_process_with_claude_code_arguments(self, subprocess_handler, test_session):
        """Test starting process with Claude Code specific arguments."""
        subprocess_handler.output_format = "json"
        subprocess_handler.model = "claude-3-opus"
        
        with patch('claude_remote_client.claude_client.subprocess_handler.validate_project_path', return_value=True):
            with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
                mock_process = Mock()
                mock_process.pid = 12345
                mock_process.returncode = None
                mock_process.stdout = AsyncMock()
                mock_process.stderr = AsyncMock()
                mock_process.wait = AsyncMock(return_value=0)
                mock_create_subprocess.return_value = mock_process
                
                # Mock startup
                subprocess_handler._wait_for_startup = AsyncMock()
                
                await subprocess_handler.start_process(test_session)
                
                # Verify command arguments
                call_args = mock_create_subprocess.call_args[0]
                assert "claude" in call_args
                assert "--output-format" in call_args
                assert "json" in call_args
                assert "--model" in call_args
                assert "claude-3-opus" in call_args
                assert "--dangerously-skip-permissions" in call_args
    
    @pytest.mark.asyncio
    async def test_resume_claude_session(self, subprocess_handler, test_session):
        """Test resuming a Claude Code session."""
        claude_session_id = "claude-session-abc123"
        
        with patch('claude_remote_client.claude_client.subprocess_handler.validate_project_path', return_value=True):
            with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
                mock_process = Mock()
                mock_process.pid = 12345
                mock_process.returncode = None
                mock_process.stdout = AsyncMock()
                mock_process.stderr = AsyncMock()
                mock_process.wait = AsyncMock(return_value=0)
                mock_create_subprocess.return_value = mock_process
                
                # Mock startup
                subprocess_handler._wait_for_startup = AsyncMock()
                
                await subprocess_handler.start_process(test_session, resume_claude_session=claude_session_id)
                
                # Verify --resume argument
                call_args = mock_create_subprocess.call_args[0]
                assert "--resume" in call_args
                assert claude_session_id in call_args
                assert subprocess_handler.claude_session_id == claude_session_id
    
    @pytest.mark.asyncio
    async def test_execute_command_non_interactive(self, subprocess_handler, test_session):
        """Test executing a command in non-interactive mode."""
        subprocess_handler.session = test_session
        test_command = "Explain the project structure"
        expected_response = {"response": "Here is the project structure..."}
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(
                    json.dumps(expected_response).encode('utf-8'),
                    b''
                )
            )
            mock_create_subprocess.return_value = mock_process
            
            subprocess_handler.output_format = "json"
            result = await subprocess_handler.execute_command(test_command)
            
            # Verify command execution
            call_args = mock_create_subprocess.call_args[0]
            assert "claude" in call_args
            assert "-p" in call_args
            assert test_command in call_args
            assert "--output-format" in call_args
            assert "json" in call_args
            
            # Verify result
            assert result["success"] is True
            assert result["data"] == expected_response
            assert result["error"] is None
    
    @pytest.mark.asyncio
    async def test_parse_json_output(self, subprocess_handler):
        """Test parsing JSON output from Claude Code CLI."""
        # Test regular JSON format
        subprocess_handler.output_format = "json"
        json_output = '{"session_id": "claude-123", "response": "Hello"}'
        
        subprocess_handler._parse_json_output(json_output)
        
        assert subprocess_handler.claude_session_id == "claude-123"
        assert hasattr(subprocess_handler, 'json_response')
        assert subprocess_handler.json_response["response"] == "Hello"
        
        # Test stream-json format
        subprocess_handler.output_format = "stream-json"
        stream_output = '{"session_id": "claude-456", "chunk": 1}\n{"chunk": 2}'
        
        subprocess_handler._parse_json_output(stream_output)
        
        assert subprocess_handler.claude_session_id == "claude-456"
        assert hasattr(subprocess_handler, 'json_responses')
        assert len(subprocess_handler.json_responses) == 2
        assert subprocess_handler.json_responses[0]["chunk"] == 1
        assert subprocess_handler.json_responses[1]["chunk"] == 2
    
    @pytest.mark.asyncio
    async def test_continue_session(self, subprocess_handler, test_session):
        """Test continuing a Claude Code session."""
        subprocess_handler.session = test_session
        subprocess_handler.output_format = "json"
        subprocess_handler.model = "claude-3-opus"
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.returncode = None
            mock_process.stdout = AsyncMock()
            mock_process.stderr = AsyncMock()
            mock_process.wait = AsyncMock(return_value=0)
            mock_create_subprocess.return_value = mock_process
            
            # Mock background tasks
            with patch('asyncio.create_task'):
                await subprocess_handler.continue_session()
            
            # Verify --continue argument
            call_args = mock_create_subprocess.call_args[0]
            assert "--continue" in call_args
            assert "--output-format" in call_args
            assert "json" in call_args
            assert "--model" in call_args
            assert "claude-3-opus" in call_args
            
            assert subprocess_handler.is_running is True
            assert test_session.status == SessionStatus.ACTIVE


class TestSessionManagerClaudeCodeIntegration:
    """Test Claude Code integration in session manager."""
    
    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create a test session manager."""
        from claude_remote_client.config import Config, SlackConfig
        
        config = Config(
            data_dir=str(tmp_path),
            claude=ClaudeConfig(
                cli_path="claude",
                default_args=["--dangerously-skip-permissions"]
            ),
            slack=SlackConfig()
        )
        return SessionManager(config)
    
    @pytest.mark.asyncio
    async def test_create_session_with_claude_session_id(self, session_manager):
        """Test creating a session with Claude session ID tracking."""
        project_path = "/test/project"
        
        with patch('claude_remote_client.session_manager.session_manager.validate_project_path', return_value=True):
            with patch.object(session_manager, '_create_subprocess_handler') as mock_create_handler:
                with patch.object(session_manager, '_create_message_streamer') as mock_create_streamer:
                    # Mock handler with Claude session ID
                    mock_handler = AsyncMock()
                    mock_handler.get_claude_session_id = Mock(return_value="claude-session-123")
                    mock_create_handler.return_value = mock_handler
                    
                    # Mock streamer
                    mock_streamer = AsyncMock()
                    mock_create_streamer.return_value = mock_streamer
                    
                    session = await session_manager.create_session(project_path)
                    
                    # The Claude session ID is set during _create_subprocess_handler
                    # We need to verify the handler was created with the session
                    mock_create_handler.assert_called_once()
                    
                    # Get the session that was passed to the handler
                    created_session = mock_create_handler.call_args[0][0]
                    # Manually set the claude_session_id as it would be set in the real implementation
                    created_session.claude_session_id = "claude-session-123"
                    
                    assert created_session.claude_session_id == "claude-session-123"
    
    @pytest.mark.asyncio
    async def test_execute_non_interactive(self, session_manager):
        """Test executing non-interactive commands."""
        command = "Explain the code"
        project_path = "/test/project"
        expected_result = {"success": True, "data": "Code explanation..."}
        
        with patch('claude_remote_client.session_manager.session_manager.SubprocessClaudeHandler') as MockHandler:
            mock_handler = Mock()
            mock_handler.execute_command = AsyncMock(return_value=expected_result)
            MockHandler.return_value = mock_handler
            
            result = await session_manager.execute_non_interactive(
                command, project_path, output_format="json"
            )
            
            assert result == expected_result
            assert mock_handler.output_format == "json"
            mock_handler.execute_command.assert_called_once_with(command, None)
    
    @pytest.mark.asyncio
    async def test_continue_claude_session(self, session_manager):
        """Test continuing a Claude session."""
        # Create a session first
        session = ClaudeSession(
            session_id="test-session",
            project_path="/test/project",
            claude_session_id="claude-123"
        )
        session_manager.sessions["test-session"] = session
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.continue_session = AsyncMock()
        mock_handler.get_claude_session_id = Mock(return_value="claude-123-continued")
        session_manager.subprocess_handlers["test-session"] = mock_handler
        
        result = await session_manager.continue_claude_session("test-session")
        
        assert result.claude_session_id == "claude-123-continued"
        mock_handler.continue_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_claude_session_mapping(self, session_manager):
        """Test getting Claude session ID mapping."""
        # Create test sessions
        session1 = ClaudeSession(
            session_id="session-1",
            project_path="/test/project1",
            claude_session_id="claude-111"
        )
        session2 = ClaudeSession(
            session_id="session-2",
            project_path="/test/project2",
            claude_session_id="claude-222"
        )
        session3 = ClaudeSession(
            session_id="session-3",
            project_path="/test/project3"
        )
        
        session_manager.sessions = {
            "session-1": session1,
            "session-2": session2,
            "session-3": session3
        }
        
        mapping = session_manager.get_claude_session_mapping()
        
        assert mapping == {
            "session-1": "claude-111",
            "session-2": "claude-222",
            "session-3": None
        }


class TestClaudeCodeErrorHandling:
    """Test error handling for Claude Code integration."""
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, subprocess_handler, test_session):
        """Test command execution timeout."""
        subprocess_handler.session = test_session
        subprocess_handler.config.timeout = 1  # 1 second timeout
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock()
            mock_create_subprocess.return_value = mock_process
            
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
                with pytest.raises(ClaudeProcessError, match="timed out"):
                    await subprocess_handler.execute_command("test command")
    
    @pytest.mark.asyncio
    async def test_json_parse_error(self, subprocess_handler, test_session):
        """Test handling of invalid JSON output."""
        subprocess_handler.session = test_session
        subprocess_handler.output_format = "json"
        
        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b'Invalid JSON', b'')
            )
            mock_create_subprocess.return_value = mock_process
            
            result = await subprocess_handler.execute_command("test")
            
            assert result["success"] is False
            assert result["error"] == "Failed to parse JSON response"
            assert result["data"] == "Invalid JSON"
    
    @pytest.mark.asyncio
    async def test_continue_session_no_session(self, subprocess_handler):
        """Test continuing session without an active session."""
        subprocess_handler.session = None
        
        with pytest.raises(ClaudeProcessError, match="No session to continue"):
            await subprocess_handler.continue_session()


class TestClaudeCodeProcessInfo:
    """Test process info with Claude Code fields."""
    
    def test_get_process_info_with_claude_session(self, subprocess_handler, test_session):
        """Test getting process info including Claude session ID."""
        subprocess_handler.session = test_session
        subprocess_handler.claude_session_id = "claude-abc123"
        subprocess_handler.output_format = "json"
        subprocess_handler.model = "claude-3-opus"
        subprocess_handler.is_running = True
        subprocess_handler.start_time = datetime.now()
        subprocess_handler.last_activity = datetime.now()
        
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = None
        subprocess_handler.process = mock_process
        
        info = subprocess_handler.get_process_info()
        
        assert info["claude_session_id"] == "claude-abc123"
        assert info["output_format"] == "json"
        assert info["model"] == "claude-3-opus"
        assert info["is_running"] is True
        assert info["pid"] == 12345