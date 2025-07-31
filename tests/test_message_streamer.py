"""
Unit tests for message streamer.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from claude_remote_client.claude_client.message_streamer import MessageStreamer
from claude_remote_client.claude_client.subprocess_handler import SubprocessClaudeHandler
from claude_remote_client.models import SlackMessage, ClaudeSession
from claude_remote_client.exceptions import ClaudeProcessError


@pytest.fixture
def mock_subprocess_handler():
    """Create a mock subprocess handler."""
    handler = MagicMock(spec=SubprocessClaudeHandler)
    handler.send_message = AsyncMock()
    handler.add_output_handler = MagicMock()
    handler.remove_output_handler = MagicMock()
    handler.add_error_handler = MagicMock()
    handler.remove_error_handler = MagicMock()
    handler.get_process_info = MagicMock(return_value={
        "is_running": True,
        "pid": 12345,
        "start_time": "2023-01-01T00:00:00",
        "last_activity": "2023-01-01T00:01:00"
    })
    return handler


@pytest.fixture
def claude_session():
    """Create a test Claude session."""
    return ClaudeSession(
        session_id="test-session-123",
        project_path="/test/path",
        project_name="test-project"
    )


@pytest.fixture
def message_streamer(mock_subprocess_handler):
    """Create a message streamer."""
    return MessageStreamer(mock_subprocess_handler)


@pytest.fixture
def slack_message():
    """Create a test Slack message."""
    return SlackMessage(
        channel_id="C1234567890",
        user_id="U1234567890",
        text="Hello Claude!"
    )


class TestMessageStreamer:
    """Test cases for MessageStreamer."""
    
    def test_streamer_initialization(self, mock_subprocess_handler):
        """Test streamer initialization."""
        streamer = MessageStreamer(mock_subprocess_handler)
        
        assert streamer.subprocess_handler == mock_subprocess_handler
        assert streamer.is_streaming is False
        assert streamer.current_session is None
        assert streamer.pending_prompts == {}
        assert streamer.prompt_responses == {}
        assert len(streamer.slash_commands) > 0
    
    def test_set_slack_callbacks(self, message_streamer):
        """Test setting Slack callbacks."""
        message_callback = AsyncMock()
        update_callback = AsyncMock()
        
        message_streamer.set_slack_callbacks(message_callback, update_callback)
        
        assert message_streamer.slack_message_callback == message_callback
        assert message_streamer.slack_update_callback == update_callback
    
    @pytest.mark.asyncio
    async def test_start_streaming(self, message_streamer, claude_session):
        """Test starting streaming."""
        await message_streamer.start_streaming(claude_session)
        
        assert message_streamer.is_streaming is True
        assert message_streamer.current_session == claude_session
        
        # Verify handlers were added
        message_streamer.subprocess_handler.add_output_handler.assert_called_once()
        message_streamer.subprocess_handler.add_error_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_streaming_already_streaming(self, message_streamer, claude_session):
        """Test starting streaming when already streaming."""
        message_streamer.is_streaming = True
        
        with pytest.raises(ClaudeProcessError) as exc_info:
            await message_streamer.start_streaming(claude_session)
        
        assert "Already streaming" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_stop_streaming(self, message_streamer, claude_session):
        """Test stopping streaming."""
        # Start streaming first
        await message_streamer.start_streaming(claude_session)
        
        # Stop streaming
        await message_streamer.stop_streaming()
        
        assert message_streamer.is_streaming is False
        assert message_streamer.current_session is None
        assert message_streamer.response_buffer == ""
        assert message_streamer.pending_prompts == {}
        
        # Verify handlers were removed
        message_streamer.subprocess_handler.remove_output_handler.assert_called_once()
        message_streamer.subprocess_handler.remove_error_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_to_claude_not_streaming(self, message_streamer, slack_message):
        """Test sending message when not streaming."""
        with pytest.raises(ClaudeProcessError) as exc_info:
            await message_streamer.send_message_to_claude(slack_message)
        
        assert "Not currently streaming" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_to_claude_regular_message(self, message_streamer, claude_session, slack_message):
        """Test sending regular message to Claude."""
        await message_streamer.start_streaming(claude_session)
        
        await message_streamer.send_message_to_claude(slack_message)
        
        message_streamer.subprocess_handler.send_message.assert_called_once_with("Hello Claude!")
    
    @pytest.mark.asyncio
    async def test_send_message_to_claude_slash_command(self, message_streamer, claude_session):
        """Test sending slash command."""
        await message_streamer.start_streaming(claude_session)
        
        slash_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="/help"
        )
        
        # Mock Slack callback
        message_streamer.slack_message_callback = AsyncMock()
        
        await message_streamer.send_message_to_claude(slash_message)
        
        # Should not send to subprocess (handled as slash command)
        message_streamer.subprocess_handler.send_message.assert_not_called()
        
        # Should send help response to Slack
        message_streamer.slack_message_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_to_claude_prompt_response(self, message_streamer, claude_session):
        """Test sending response to pending prompt."""
        await message_streamer.start_streaming(claude_session)
        
        # Add a pending prompt
        message_streamer.pending_prompts["prompt_123"] = "Continue? [y/n]"
        
        response_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="y"
        )
        
        await message_streamer.send_message_to_claude(response_message)
        
        # Should send response to subprocess
        message_streamer.subprocess_handler.send_message.assert_called_once_with("y")
        
        # Should clear the prompt
        assert "prompt_123" not in message_streamer.pending_prompts
    
    def test_detect_interactive_prompt_yes_no(self, message_streamer):
        """Test detecting yes/no prompts."""
        prompts = [
            "Continue? [y/n]",
            "Delete file? [Y/n]",
            "Proceed with operation? [y/N]",
            "Press Enter to continue",
            "Enter your choice:",
            "Please confirm: (y/n)"
        ]
        
        for prompt in prompts:
            assert message_streamer._detect_interactive_prompt(prompt) is True
    
    def test_detect_interactive_prompt_false_positives(self, message_streamer):
        """Test that regular text doesn't trigger prompt detection."""
        non_prompts = [
            "This is regular text",
            "Here's some code: if x == y:",
            "The function returns [1, 2, 3]",
            "Use brackets like [this] for arrays"
        ]
        
        for text in non_prompts:
            assert message_streamer._detect_interactive_prompt(text) is False
    
    @pytest.mark.asyncio
    async def test_handle_claude_output_regular(self, message_streamer, claude_session):
        """Test handling regular Claude output."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        # Simulate Claude output
        await message_streamer._handle_claude_output("Hello from Claude!")
        
        # Should accumulate in buffer
        assert "Hello from Claude!" in message_streamer.response_buffer
    
    @pytest.mark.asyncio
    async def test_handle_claude_output_interactive_prompt(self, message_streamer, claude_session):
        """Test handling interactive prompt from Claude."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        # Simulate interactive prompt
        prompt_output = "Continue with operation? [y/n]"
        await message_streamer._handle_claude_output(prompt_output)
        
        # Should create pending prompt
        assert len(message_streamer.pending_prompts) == 1
        
        # Should send prompt to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Claude is asking for input" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_claude_error(self, message_streamer, claude_session):
        """Test handling Claude error output."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        # Simulate error output
        await message_streamer._handle_claude_error("Error: File not found")
        
        # Should send error to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Claude Error" in call_args[1]["text"]
        assert "File not found" in call_args[1]["text"]
    
    def test_should_send_response_large_buffer(self, message_streamer):
        """Test response sending trigger for large buffer."""
        message_streamer.response_buffer = "x" * 2500  # Larger than max_chunk_size
        
        assert message_streamer._should_send_response() is True
    
    def test_should_send_response_pause_in_output(self, message_streamer):
        """Test response sending trigger for pause in output."""
        message_streamer.response_buffer = "Some response"
        message_streamer.last_response_time = datetime.now()
        
        # Mock time to simulate pause
        with patch('claude_remote_client.claude_client.message_streamer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now()
            mock_datetime.now.return_value = datetime.fromtimestamp(
                message_streamer.last_response_time.timestamp() + 3.0
            )
            
            assert message_streamer._should_send_response() is True
    
    def test_should_send_response_complete_response(self, message_streamer):
        """Test response sending trigger for complete response."""
        complete_responses = [
            "Here's your answer.",
            "Command completed>",
            "Ready for input$",
            "Please choose:"
        ]
        
        for response in complete_responses:
            message_streamer.response_buffer = response
            assert message_streamer._should_send_response() is True
    
    @pytest.mark.asyncio
    async def test_send_accumulated_response(self, message_streamer, claude_session):
        """Test sending accumulated response."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        message_streamer.response_buffer = "Here's the response from Claude."
        
        await message_streamer._send_accumulated_response()
        
        # Should send to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Here's the response from Claude." in call_args[1]["text"]
        
        # Should clear buffer
        assert message_streamer.response_buffer == ""
    
    def test_contains_code(self, message_streamer):
        """Test code detection in text."""
        code_texts = [
            "def hello():\n    print('world')",
            "class MyClass:",
            "import os",
            "from datetime import datetime",
            "x = 5",
            "if x == y:",
            "function myFunc() {",
            "SELECT * FROM users"
        ]
        
        for text in code_texts:
            assert message_streamer._contains_code(text) is True
        
        non_code_texts = [
            "This is regular text",
            "Here's a simple explanation",
            "No code here at all"
        ]
        
        for text in non_code_texts:
            assert message_streamer._contains_code(text) is False
    
    def test_format_code_in_response(self, message_streamer):
        """Test code formatting in response."""
        text_with_code = """Here's some code:
    def hello():
        print("Hello, world!")
        return True

And some regular text."""
        
        formatted = message_streamer._format_code_in_response(text_with_code)
        
        # Should contain code block markers
        assert "```" in formatted
        assert "def hello():" in formatted
    
    def test_format_response(self, message_streamer):
        """Test response formatting."""
        # Regular text
        response = "This is a regular response."
        formatted = message_streamer._format_response(response)
        assert formatted == "This is a regular response."
        
        # Text with code
        code_response = "    def hello():\n        print('world')"
        formatted = message_streamer._format_response(code_response)
        assert "```" in formatted
        
        # Very long text
        long_response = "x" * 3000
        formatted = message_streamer._format_response(long_response)
        assert len(formatted) < 3000
        assert "truncated" in formatted
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_help(self, message_streamer, claude_session):
        """Test handling /help slash command."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        help_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="/help"
        )
        
        await message_streamer._handle_slash_command(help_message)
        
        # Should send help text to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Available Slash Commands" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_exit(self, message_streamer, claude_session):
        """Test handling /exit slash command."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        exit_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="/exit"
        )
        
        await message_streamer._handle_slash_command(exit_message)
        
        # Should send exit command to Claude
        message_streamer.subprocess_handler.send_message.assert_called_once_with("/exit")
        
        # Should send confirmation to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Exiting Claude session" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_status(self, message_streamer, claude_session):
        """Test handling /status slash command."""
        await message_streamer.start_streaming(claude_session)
        message_streamer.slack_message_callback = AsyncMock()
        
        status_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="/status"
        )
        
        await message_streamer._handle_slash_command(status_message)
        
        # Should send status to Slack
        message_streamer.slack_message_callback.assert_called_once()
        call_args = message_streamer.slack_message_callback.call_args
        assert "Session Status" in call_args[1]["text"]
        assert "test-session-123" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_unknown(self, message_streamer, claude_session):
        """Test handling unknown slash command."""
        await message_streamer.start_streaming(claude_session)
        
        unknown_message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="/unknown_command"
        )
        
        await message_streamer._handle_slash_command(unknown_message)
        
        # Should send to Claude anyway
        message_streamer.subprocess_handler.send_message.assert_called_once_with("/unknown_command")
    
    def test_get_streaming_stats(self, message_streamer, claude_session):
        """Test getting streaming statistics."""
        # Not streaming
        stats = message_streamer.get_streaming_stats()
        assert stats["is_streaming"] is False
        assert stats["current_session_id"] is None
        
        # Streaming
        message_streamer.is_streaming = True
        message_streamer.current_session = claude_session
        message_streamer.pending_prompts["prompt_1"] = "Test prompt"
        message_streamer.response_buffer = "Some response"
        
        stats = message_streamer.get_streaming_stats()
        assert stats["is_streaming"] is True
        assert stats["current_session_id"] == "test-session-123"
        assert stats["pending_prompts"] == 1
        assert stats["response_buffer_size"] > 0
        assert len(stats["available_slash_commands"]) > 0