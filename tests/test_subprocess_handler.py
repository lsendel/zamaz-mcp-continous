"""
Unit tests for Claude subprocess handler.
"""

import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from claude_remote_client.claude_client.subprocess_handler import SubprocessClaudeHandler
from claude_remote_client.config import ClaudeConfig
from claude_remote_client.models import ClaudeSession, SessionStatus
from claude_remote_client.exceptions import ClaudeProcessError


@pytest.fixture
def claude_config():
    """Create a test Claude configuration."""
    return ClaudeConfig(
        cli_path="claude",
        default_args=["--dangerously-skip-permissions"],
        timeout=300
    )


@pytest.fixture
def claude_session():
    """Create a test Claude session."""
    with tempfile.TemporaryDirectory() as temp_dir:
        session = ClaudeSession(
            project_path=temp_dir,
            project_name="test-project"
        )
        yield session


@pytest.fixture
def subprocess_handler(claude_config):
    """Create a subprocess handler."""
    return SubprocessClaudeHandler(claude_config)


class TestSubprocessClaudeHandler:
    """Test cases for SubprocessClaudeHandler."""
    
    def test_handler_initialization(self, claude_config):
        """Test handler initialization."""
        handler = SubprocessClaudeHandler(claude_config)
        
        assert handler.config == claude_config
        assert handler.process is None
        assert handler.session is None
        assert handler.is_running is False
        assert handler.stdout_buffer == ""
        assert handler.stderr_buffer == ""
        assert handler.output_handlers == []
        assert handler.error_handlers == []
    
    @pytest.mark.asyncio
    async def test_start_process_invalid_path(self, subprocess_handler):
        """Test starting process with invalid project path."""
        session = ClaudeSession(
            project_path="/nonexistent/path",
            project_name="invalid-project"
        )
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler.start_process(session)
        
        assert "Invalid project path" in str(exc_info.value)
        assert subprocess_handler.is_running is False
    
    @pytest.mark.asyncio
    async def test_start_process_already_running(self, subprocess_handler, claude_session):
        """Test starting process when already running."""
        subprocess_handler.is_running = True
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler.start_process(claude_session)
        
        assert "already running" in str(exc_info.value)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_process_success(self, mock_create_subprocess, subprocess_handler, claude_session):
        """Test successful process start."""
        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdout.read = AsyncMock(return_value=b"Claude ready>\n")
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_create_subprocess.return_value = mock_process
        
        # Mock the startup wait
        with patch.object(subprocess_handler, '_wait_for_startup', new_callable=AsyncMock):
            await subprocess_handler.start_process(claude_session)
        
        assert subprocess_handler.is_running is True
        assert subprocess_handler.session == claude_session
        assert subprocess_handler.process == mock_process
        assert claude_session.status == SessionStatus.ACTIVE
        assert claude_session.process_id == 12345
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_process_failure(self, mock_create_subprocess, subprocess_handler, claude_session):
        """Test process start failure."""
        mock_create_subprocess.side_effect = Exception("Failed to start process")
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler.start_process(claude_session)
        
        assert "Failed to start Claude process" in str(exc_info.value)
        assert subprocess_handler.is_running is False
        assert claude_session.status == SessionStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_wait_for_startup_timeout(self, subprocess_handler):
        """Test startup timeout."""
        # Mock process that never becomes ready
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.stdout.read = AsyncMock(return_value=b"")
        subprocess_handler.process = mock_process
        subprocess_handler.startup_timeout = 0.1  # Very short timeout for testing
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler._wait_for_startup()
        
        assert "startup timeout" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_wait_for_startup_process_exit(self, subprocess_handler):
        """Test startup when process exits early."""
        # Mock process that exits during startup
        mock_process = MagicMock()
        mock_process.returncode = 1  # Process exited
        subprocess_handler.process = mock_process
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler._wait_for_startup()
        
        assert "exited during startup" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_not_running(self, subprocess_handler):
        """Test sending message when process is not running."""
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler.send_message("Hello Claude!")
        
        assert "not running" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, subprocess_handler, claude_session):
        """Test successful message sending."""
        # Mock running process
        mock_process = MagicMock()
        mock_stdin = AsyncMock()
        mock_process.stdin = mock_stdin
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.session = claude_session
        
        await subprocess_handler.send_message("Hello Claude!")
        
        # Verify message was written to stdin
        mock_stdin.write.assert_called_once_with(b"Hello Claude!\n")
        mock_stdin.drain.assert_called_once()
        
        # Verify message was added to session history
        assert len(claude_session.conversation_history) == 1
        assert claude_session.conversation_history[0]["role"] == "user"
        assert claude_session.conversation_history[0]["content"] == "Hello Claude!"
    
    @pytest.mark.asyncio
    async def test_send_message_write_error(self, subprocess_handler):
        """Test message sending with write error."""
        # Mock process with failing stdin
        mock_process = MagicMock()
        mock_stdin = AsyncMock()
        mock_stdin.drain.side_effect = Exception("Write failed")
        mock_process.stdin = mock_stdin
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await subprocess_handler.send_message("Hello Claude!")
        
        assert "Failed to send message" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_read_output_not_running(self, subprocess_handler):
        """Test reading output when process is not running."""
        with pytest.raises(ClaudeProcessError) as exc_info:
            async for _ in subprocess_handler.read_output():
                pass
        
        assert "not running" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_read_output_success(self, subprocess_handler, claude_session):
        """Test successful output reading."""
        # Mock running process
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_stdout = AsyncMock()
        
        # Mock stdout to return some data then empty
        mock_stdout.read.side_effect = [b"Hello from Claude!", b""]
        mock_process.stdout = mock_stdout
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.session = claude_session
        
        output_chunks = []
        async for chunk in subprocess_handler.read_output():
            output_chunks.append(chunk)
            if not chunk:  # Empty chunk indicates end
                break
        
        assert len(output_chunks) >= 1
        assert "Hello from Claude!" in "".join(output_chunks)
        
        # Verify output was added to session history
        assert len(claude_session.conversation_history) >= 1
    
    @pytest.mark.asyncio
    async def test_terminate_process_not_running(self, subprocess_handler):
        """Test terminating when no process is running."""
        # Should not raise an error
        await subprocess_handler.terminate_process()
        
        assert subprocess_handler.process is None
        assert subprocess_handler.is_running is False
    
    @pytest.mark.asyncio
    async def test_terminate_process_graceful(self, subprocess_handler, claude_session):
        """Test graceful process termination."""
        # Mock running process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.wait.return_value = 0  # Graceful exit
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.session = claude_session
        
        await subprocess_handler.terminate_process(timeout=1.0)
        
        # Verify termination was called
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()
        
        # Verify cleanup
        assert subprocess_handler.process is None
        assert subprocess_handler.is_running is False
        assert claude_session.status == SessionStatus.INACTIVE
    
    @pytest.mark.asyncio
    async def test_terminate_process_force_kill(self, subprocess_handler, claude_session):
        """Test force killing process when graceful termination fails."""
        # Mock process that doesn't terminate gracefully
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.wait.side_effect = [asyncio.TimeoutError(), 0]  # Timeout then success
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.session = claude_session
        
        await subprocess_handler.terminate_process(timeout=0.1)
        
        # Verify both terminate and kill were called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        
        # Verify cleanup
        assert subprocess_handler.process is None
        assert subprocess_handler.is_running is False
    
    def test_output_handler_management(self, subprocess_handler):
        """Test adding and removing output handlers."""
        async def test_handler(output):
            pass
        
        # Add handler
        subprocess_handler.add_output_handler(test_handler)
        assert test_handler in subprocess_handler.output_handlers
        
        # Remove handler
        subprocess_handler.remove_output_handler(test_handler)
        assert test_handler not in subprocess_handler.output_handlers
    
    def test_error_handler_management(self, subprocess_handler):
        """Test adding and removing error handlers."""
        async def test_handler(error):
            pass
        
        # Add handler
        subprocess_handler.add_error_handler(test_handler)
        assert test_handler in subprocess_handler.error_handlers
        
        # Remove handler
        subprocess_handler.remove_error_handler(test_handler)
        assert test_handler not in subprocess_handler.error_handlers
    
    def test_get_process_info_no_process(self, subprocess_handler):
        """Test getting process info when no process is running."""
        info = subprocess_handler.get_process_info()
        
        assert info["is_running"] is False
        assert info["pid"] is None
        assert info["return_code"] is None
        assert info["session_id"] is None
        assert info["project_path"] is None
    
    def test_get_process_info_with_process(self, subprocess_handler, claude_session):
        """Test getting process info with running process."""
        # Mock running process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.session = claude_session
        subprocess_handler.start_time = datetime.now()
        subprocess_handler.last_activity = datetime.now()
        
        info = subprocess_handler.get_process_info()
        
        assert info["is_running"] is True
        assert info["pid"] == 12345
        assert info["return_code"] is None
        assert info["session_id"] == claude_session.session_id
        assert info["project_path"] == claude_session.project_path
        assert info["start_time"] is not None
        assert info["last_activity"] is not None
    
    def test_get_recent_output(self, subprocess_handler):
        """Test getting recent output."""
        # Add some output to buffer
        subprocess_handler.stdout_buffer = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        
        # Get recent output
        recent = subprocess_handler.get_recent_output(lines=3)
        
        assert "Line 3" in recent
        assert "Line 4" in recent
        assert "Line 5" in recent
        assert "Line 1" not in recent
    
    def test_get_recent_output_empty(self, subprocess_handler):
        """Test getting recent output when buffer is empty."""
        recent = subprocess_handler.get_recent_output()
        assert recent == ""
    
    def test_get_recent_errors(self, subprocess_handler):
        """Test getting recent errors."""
        # Add some errors to buffer
        subprocess_handler.stderr_buffer = "Error 1\nError 2\nError 3"
        
        # Get recent errors
        recent = subprocess_handler.get_recent_errors(lines=2)
        
        assert "Error 2" in recent
        assert "Error 3" in recent
        assert "Error 1" not in recent
    
    @pytest.mark.asyncio
    async def test_health_check_not_running(self, subprocess_handler):
        """Test health check when process is not running."""
        result = await subprocess_handler.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_process_exited(self, subprocess_handler):
        """Test health check when process has exited."""
        mock_process = MagicMock()
        mock_process.returncode = 0  # Process exited
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        
        result = await subprocess_handler.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, subprocess_handler):
        """Test health check for healthy process."""
        mock_process = MagicMock()
        mock_process.returncode = None  # Still running
        
        subprocess_handler.process = mock_process
        subprocess_handler.is_running = True
        subprocess_handler.last_activity = datetime.now()
        
        result = await subprocess_handler.health_check()
        assert result is True