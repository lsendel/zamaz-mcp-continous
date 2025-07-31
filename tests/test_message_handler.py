"""
Unit tests for message handler.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from claude_remote_client.slack_client.message_handler import MessageHandler
from claude_remote_client.slack_client.command_router import CommandRouter, CommandResult
from claude_remote_client.models import SlackMessage


@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    client = MagicMock()
    client.send_message = AsyncMock(return_value={"ts": "1234567890.123456"})
    client.update_message = AsyncMock(return_value={"ts": "1234567890.123456"})
    client.delete_message = AsyncMock()
    client.send_typing_indicator = AsyncMock(return_value="1234567890.000000")
    return client


@pytest.fixture
def mock_command_router():
    """Create a mock command router."""
    router = MagicMock(spec=CommandRouter)
    router.route_message = AsyncMock()
    return router


@pytest.fixture
def message_handler(mock_slack_client, mock_command_router):
    """Create a message handler with mocked dependencies."""
    return MessageHandler(mock_slack_client, mock_command_router)


class TestMessageHandler:
    """Test cases for MessageHandler."""
    
    def test_handler_initialization(self, mock_slack_client):
        """Test handler initialization."""
        handler = MessageHandler(mock_slack_client)
        
        assert handler.slack_client == mock_slack_client
        assert handler.command_router is not None
        assert handler.active_threads == {}
        assert handler.max_message_length == 3000
        assert handler.claude_message_callback is None
    
    def test_set_claude_callback(self, message_handler):
        """Test setting Claude callback."""
        async def mock_callback(message):
            pass
        
        message_handler.set_claude_callback(mock_callback)
        
        assert message_handler.claude_message_callback == mock_callback
    
    @pytest.mark.asyncio
    async def test_handle_message_command(self, message_handler):
        """Test handling command messages."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="@@help"
        )
        
        # Mock command router to return command result
        command_result = CommandResult(
            success=True,
            message="Help message",
            should_forward_to_claude=False
        )
        message_handler.command_router.route_message.return_value = command_result
        
        await message_handler.handle_message(message)
        
        # Verify command router was called
        message_handler.command_router.route_message.assert_called_once_with(message)
        
        # Verify response was sent
        message_handler.slack_client.send_message.assert_called_once_with(
            channel="C1234567890",
            text="Help message",
            thread_ts=None
        )
    
    @pytest.mark.asyncio
    async def test_handle_message_forward_to_claude(self, message_handler):
        """Test handling messages that should be forwarded to Claude."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello Claude!"
        )
        
        # Mock command router to indicate forwarding to Claude
        command_result = CommandResult(
            success=True,
            message="Forward to Claude",
            should_forward_to_claude=True
        )
        message_handler.command_router.route_message.return_value = command_result
        
        # Mock Claude callback
        claude_callback = AsyncMock()
        message_handler.set_claude_callback(claude_callback)
        
        await message_handler.handle_message(message)
        
        # Verify Claude callback was called
        claude_callback.assert_called_once_with(message)
        
        # Verify typing indicator was sent and deleted
        message_handler.slack_client.send_typing_indicator.assert_called_once_with("C1234567890")
        message_handler.slack_client.delete_message.assert_called_once_with("C1234567890", "1234567890.000000")
    
    @pytest.mark.asyncio
    async def test_handle_message_no_claude_callback(self, message_handler):
        """Test handling messages when Claude callback is not set."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello Claude!"
        )
        
        # Mock command router to indicate forwarding to Claude
        command_result = CommandResult(
            success=True,
            message="Forward to Claude",
            should_forward_to_claude=True
        )
        message_handler.command_router.route_message.return_value = command_result
        
        await message_handler.handle_message(message)
        
        # Verify error response was sent
        message_handler.slack_client.send_message.assert_called_once()
        call_args = message_handler.slack_client.send_message.call_args
        assert "Claude integration not configured" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_message_error(self, message_handler):
        """Test handling messages when an error occurs."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="@@help"
        )
        
        # Mock command router to raise an exception
        message_handler.command_router.route_message.side_effect = Exception("Test error")
        
        await message_handler.handle_message(message)
        
        # Verify error response was sent
        message_handler.slack_client.send_message.assert_called_once()
        call_args = message_handler.slack_client.send_message.call_args
        assert "❌" in call_args[1]["text"]  # Error emoji
    
    @pytest.mark.asyncio
    async def test_stream_response(self, message_handler):
        """Test streaming response from Claude."""
        channel = "C1234567890"
        
        # Mock response stream
        async def mock_stream():
            yield "Hello "
            yield "from "
            yield "Claude!"
        
        await message_handler.stream_response(channel, mock_stream())
        
        # Verify initial message was sent
        assert message_handler.slack_client.send_message.call_count == 1
        
        # Verify message was updated with final response
        assert message_handler.slack_client.update_message.call_count >= 1
        
        # Check final update contains complete response
        final_call = message_handler.slack_client.update_message.call_args_list[-1]
        assert "Hello from Claude!" in final_call[1]["text"]
    
    @pytest.mark.asyncio
    async def test_stream_response_error(self, message_handler):
        """Test streaming response when an error occurs."""
        channel = "C1234567890"
        
        # Mock response stream that raises an error
        async def mock_stream():
            yield "Hello "
            raise Exception("Stream error")
        
        await message_handler.stream_response(channel, mock_stream())
        
        # Verify error message was sent
        assert message_handler.slack_client.send_message.call_count >= 1
        
        # Check that an error message was sent
        calls = message_handler.slack_client.send_message.call_args_list
        error_call = next((call for call in calls if "❌" in call[1]["text"]), None)
        assert error_call is not None
    
    def test_format_code_blocks(self, message_handler):
        """Test code block formatting."""
        # Text with code-like content
        text_with_code = """Here's some code:
    def hello():
        print("Hello, world!")
        return True

And some regular text."""
        
        formatted = message_handler._format_code_blocks(text_with_code)
        
        # Should contain code block markers
        assert "```" in formatted
        assert "def hello():" in formatted
    
    def test_format_claude_response_empty(self, message_handler):
        """Test formatting empty Claude response."""
        result = message_handler._format_claude_response("")
        assert "Claude is thinking" in result
    
    def test_format_claude_response_with_content(self, message_handler):
        """Test formatting Claude response with content."""
        response = "Here's your answer: Hello, world!"
        result = message_handler._format_claude_response(response)
        assert result == response  # Should return as-is for simple text
    
    @pytest.mark.asyncio
    async def test_send_status_update(self, message_handler):
        """Test sending status update."""
        await message_handler.send_status_update("C1234567890", "Processing request")
        
        message_handler.slack_client.send_message.assert_called_once()
        call_args = message_handler.slack_client.send_message.call_args
        assert "ℹ️" in call_args[1]["text"]  # Info emoji
        assert "Processing request" in call_args[1]["text"]
    
    @pytest.mark.asyncio
    async def test_send_success_message(self, message_handler):
        """Test sending success message."""
        await message_handler.send_success_message(
            "C1234567890", 
            "Task completed", 
            "All files processed"
        )
        
        message_handler.slack_client.send_message.assert_called_once()
        call_args = message_handler.slack_client.send_message.call_args
        assert "✅" in call_args[1]["text"]  # Success emoji
        assert "Task completed" in call_args[1]["text"]
        assert "All files processed" in call_args[1]["text"]
    
    def test_threading_management(self, message_handler):
        """Test thread management for users."""
        user_id = "U1234567890"
        thread_ts = "1234567890.123456"
        
        # Enable threading
        message_handler.enable_threading_for_user(user_id, thread_ts)
        assert message_handler.active_threads[user_id] == thread_ts
        
        # Disable threading
        message_handler.disable_threading_for_user(user_id)
        assert user_id not in message_handler.active_threads
    
    def test_get_thread_ts_existing_thread(self, message_handler):
        """Test getting thread timestamp for existing thread."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello",
            thread_ts="1234567890.123456"
        )
        
        thread_ts = message_handler._get_thread_ts(message)
        assert thread_ts == "1234567890.123456"
    
    def test_get_thread_ts_no_thread(self, message_handler):
        """Test getting thread timestamp when no thread exists."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello"
        )
        
        thread_ts = message_handler._get_thread_ts(message)
        assert thread_ts is None
    
    def test_get_message_stats(self, message_handler):
        """Test getting message handler statistics."""
        # Enable threading for a user
        message_handler.enable_threading_for_user("U1234567890", "1234567890.123456")
        
        # Set Claude callback
        message_handler.set_claude_callback(lambda x: None)
        
        stats = message_handler.get_message_stats()
        
        assert stats["active_threads"] == 1
        assert stats["max_message_length"] == 3000
        assert stats["claude_callback_configured"] is True