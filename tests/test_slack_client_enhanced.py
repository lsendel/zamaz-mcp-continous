"""
Enhanced unit tests for Slack client components.

These tests provide comprehensive coverage of the Slack integration
including connection handling, message processing, and error scenarios.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.slack_client.message_handler import MessageHandler
from claude_remote_client.slack_client.command_router import CommandRouter
from claude_remote_client.config import Config, SlackConfig
from claude_remote_client.models import SlackMessage
from claude_remote_client.exceptions import SlackError
from tests.test_utilities import MockFactory, AssertionHelpers


@pytest.fixture
def slack_config():
    """Create test Slack configuration."""
    return SlackConfig(
        bot_token="xoxb-test-token",
        app_token="xapp-test-token",
        channel_id="C1234567890",
        signing_secret="test-secret"
    )


@pytest.fixture
def test_config(slack_config):
    """Create test configuration with Slack settings."""
    return Config(slack=slack_config)


class TestSlackBotClient:
    """Enhanced tests for SlackBotClient."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, test_config):
        """Test client initialization with configuration."""
        client = SlackBotClient(test_config)
        
        assert client.config == test_config
        assert not client.is_connected
        assert client.reconnect_attempts == 0
        assert client.max_reconnect_attempts == 5
    
    @pytest.mark.asyncio
    async def test_successful_connection(self, test_config):
        """Test successful Slack connection."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_client:
            mock_socket_client = AsyncMock()
            mock_client.return_value = mock_socket_client
            mock_socket_client.connect = AsyncMock()
            
            client = SlackBotClient(test_config)
            await client.connect()
            
            assert client.is_connected
            mock_socket_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_failure_retry(self, test_config):
        """Test connection failure and retry logic."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_client:
            mock_socket_client = AsyncMock()
            mock_client.return_value = mock_socket_client
            
            # First attempt fails, second succeeds
            mock_socket_client.connect = AsyncMock(side_effect=[
                Exception("Connection failed"),
                None
            ])
            
            client = SlackBotClient(test_config)
            client.max_reconnect_attempts = 2
            
            await client.connect()
            
            assert client.is_connected
            assert client.reconnect_attempts == 1
            assert mock_socket_client.connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_connection_max_retries_exceeded(self, test_config):
        """Test connection failure when max retries exceeded."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_client:
            mock_socket_client = AsyncMock()
            mock_client.return_value = mock_socket_client
            mock_socket_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
            
            client = SlackBotClient(test_config)
            client.max_reconnect_attempts = 2
            
            with pytest.raises(SlackError, match="Failed to connect after"):
                await client.connect()
            
            assert not client.is_connected
            assert client.reconnect_attempts == 2
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, test_config):
        """Test successful message sending."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={
                "ok": True,
                "ts": "1234567890.123456"
            })
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            
            result = await client.send_message("C1234567890", "Test message")
            
            assert result["ok"] is True
            assert "ts" in result
            mock_client.chat_postMessage.assert_called_once_with(
                channel="C1234567890",
                text="Test message"
            )
    
    @pytest.mark.asyncio
    async def test_send_message_with_thread(self, test_config):
        """Test sending message in thread."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            
            await client.send_message("C1234567890", "Reply", thread_ts="1234567890.123456")
            
            mock_client.chat_postMessage.assert_called_once_with(
                channel="C1234567890",
                text="Reply",
                thread_ts="1234567890.123456"
            )
    
    @pytest.mark.asyncio
    async def test_send_message_failure(self, test_config):
        """Test message sending failure."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(side_effect=Exception("API Error"))
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            
            with pytest.raises(SlackError, match="Failed to send message"):
                await client.send_message("C1234567890", "Test message")
    
    @pytest.mark.asyncio
    async def test_update_message(self, test_config):
        """Test message updating."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_update = AsyncMock(return_value={"ok": True})
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            
            await client.update_message("C1234567890", "1234567890.123456", "Updated message")
            
            mock_client.chat_update.assert_called_once_with(
                channel="C1234567890",
                ts="1234567890.123456",
                text="Updated message"
            )
    
    @pytest.mark.asyncio
    async def test_typing_indicator(self, test_config):
        """Test typing indicator."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.conversations_typing = AsyncMock(return_value={"ok": True})
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            
            await client.send_typing_indicator("C1234567890")
            
            mock_client.conversations_typing.assert_called_once_with(channel="C1234567890")
    
    @pytest.mark.asyncio
    async def test_disconnect(self, test_config):
        """Test client disconnection."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_client:
            mock_socket_client = AsyncMock()
            mock_client.return_value = mock_socket_client
            mock_socket_client.disconnect = AsyncMock()
            
            client = SlackBotClient(test_config)
            client.is_connected = True
            client.socket_client = mock_socket_client
            
            await client.disconnect()
            
            assert not client.is_connected
            mock_socket_client.disconnect.assert_called_once()


class TestMessageHandler:
    """Enhanced tests for MessageHandler."""
    
    @pytest.fixture
    def message_handler(self, test_config):
        """Create message handler with test configuration."""
        return MessageHandler(test_config)
    
    @pytest.fixture
    def mock_slack_client(self):
        """Create mock Slack client."""
        return MockFactory.create_mock_slack_client()
    
    @pytest.mark.asyncio
    async def test_handle_regular_message(self, message_handler, mock_slack_client):
        """Test handling regular (non-command) messages."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello, how are you?"
        )
        
        with patch.object(message_handler, 'forward_to_claude') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            await message_handler.handle_message(message, mock_slack_client)
            
            mock_forward.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_handle_command_message(self, message_handler, mock_slack_client):
        """Test handling command messages."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="@@projects"
        )
        
        with patch.object(message_handler, 'route_command') as mock_route:
            mock_route.return_value = AsyncMock(return_value="Command result")
            
            await message_handler.handle_message(message, mock_slack_client)
            
            mock_route.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_stream_response_chunks(self, message_handler, mock_slack_client):
        """Test streaming response in chunks."""
        channel_id = "C1234567890"
        response_chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
        
        # Mock the async generator
        async def mock_response_stream():
            for chunk in response_chunks:
                yield chunk
        
        await message_handler.stream_response(channel_id, mock_response_stream(), mock_slack_client)
        
        # Should send initial message and then update it
        assert mock_slack_client.send_message.call_count >= 1
        assert mock_slack_client.update_message.call_count >= len(response_chunks) - 1
    
    @pytest.mark.asyncio
    async def test_format_code_response(self, message_handler):
        """Test code response formatting."""
        code = "def hello():\n    print('Hello, World!')"
        
        formatted = message_handler.format_code_block(code, "python")
        
        assert formatted.startswith("```python\n")
        assert formatted.endswith("\n```")
        assert code in formatted
    
    @pytest.mark.asyncio
    async def test_handle_message_error(self, message_handler, mock_slack_client):
        """Test error handling in message processing."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="@@invalid_command"
        )
        
        with patch.object(message_handler, 'route_command') as mock_route:
            mock_route.side_effect = Exception("Command failed")
            
            # Should not raise exception, but handle gracefully
            await message_handler.handle_message(message, mock_slack_client)
            
            # Should send error message to user
            mock_slack_client.send_message.assert_called()
            call_args = mock_slack_client.send_message.call_args
            assert "error" in call_args[0][1].lower()


class TestCommandRouter:
    """Enhanced tests for CommandRouter."""
    
    @pytest.fixture
    def command_router(self, test_config):
        """Create command router with test configuration."""
        return CommandRouter(test_config)
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager."""
        return MockFactory.create_mock_session_manager()
    
    @pytest.fixture
    def mock_queue_manager(self):
        """Create mock queue manager."""
        return MockFactory.create_mock_queue_manager()
    
    @pytest.mark.asyncio
    async def test_route_projects_command(self, command_router, mock_session_manager):
        """Test routing projects command."""
        message = SlackMessage(text="@@projects")
        
        with patch.object(command_router, 'session_manager', mock_session_manager):
            result = await command_router.route_command(message)
            
            assert "projects" in result.lower()
    
    @pytest.mark.asyncio
    async def test_route_switch_command(self, command_router, mock_session_manager):
        """Test routing switch command."""
        message = SlackMessage(text="@@switch test-project")
        
        with patch.object(command_router, 'session_manager', mock_session_manager):
            mock_session_manager.switch_session.return_value = AsyncMock()
            
            result = await command_router.route_command(message)
            
            mock_session_manager.switch_session.assert_called()
    
    @pytest.mark.asyncio
    async def test_route_sessions_command(self, command_router, mock_session_manager):
        """Test routing sessions command."""
        message = SlackMessage(text="@@sessions")
        
        with patch.object(command_router, 'session_manager', mock_session_manager):
            mock_session_manager.list_sessions.return_value = []
            
            result = await command_router.route_command(message)
            
            mock_session_manager.list_sessions.assert_called_once()
            assert "sessions" in result.lower()
    
    @pytest.mark.asyncio
    async def test_route_queue_add_command(self, command_router, mock_queue_manager):
        """Test routing queue add command."""
        message = SlackMessage(text="@@queue_add test-queue 'Fix bug in auth'")
        
        with patch.object(command_router, 'queue_manager', mock_queue_manager):
            result = await command_router.route_command(message)
            
            mock_queue_manager.add_task.assert_called()
    
    @pytest.mark.asyncio
    async def test_route_help_command(self, command_router):
        """Test routing help command."""
        message = SlackMessage(text="@@help")
        
        result = await command_router.route_command(message)
        
        assert "commands" in result.lower()
        assert "@@projects" in result
        assert "@@switch" in result
    
    @pytest.mark.asyncio
    async def test_route_unknown_command(self, command_router):
        """Test routing unknown command."""
        message = SlackMessage(text="@@unknown_command")
        
        result = await command_router.route_command(message)
        
        assert "unknown" in result.lower() or "not found" in result.lower()
    
    @pytest.mark.asyncio
    async def test_command_validation(self, command_router):
        """Test command validation."""
        # Valid command
        assert command_router.is_valid_command("projects")
        assert command_router.is_valid_command("switch")
        assert command_router.is_valid_command("help")
        
        # Invalid command
        assert not command_router.is_valid_command("invalid_command")
        assert not command_router.is_valid_command("")
    
    @pytest.mark.asyncio
    async def test_command_argument_parsing(self, command_router):
        """Test command argument parsing."""
        message = SlackMessage(text="@@switch project-name --force")
        
        command = message.get_command()
        args = message.get_command_args()
        
        assert command == "switch"
        assert "project-name" in args
        assert "--force" in args
    
    @pytest.mark.asyncio
    async def test_concurrent_command_processing(self, command_router, mock_session_manager):
        """Test concurrent command processing."""
        messages = [
            SlackMessage(text="@@projects"),
            SlackMessage(text="@@sessions"),
            SlackMessage(text="@@help")
        ]
        
        with patch.object(command_router, 'session_manager', mock_session_manager):
            # Process commands concurrently
            tasks = [command_router.route_command(msg) for msg in messages]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 3
            for result in results:
                assert isinstance(result, str)
                assert len(result) > 0


class TestSlackIntegrationScenarios:
    """Test complete Slack integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_message_flow(self, test_config):
        """Test complete message processing flow."""
        with patch('slack_sdk.socket_mode.SocketModeClient'), \
             patch('slack_sdk.WebClient') as mock_web_client:
            
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123"})
            
            # Create components
            slack_client = SlackBotClient(test_config)
            message_handler = MessageHandler(test_config)
            
            # Simulate message flow
            message = SlackMessage(
                channel_id="C1234567890",
                user_id="U1234567890",
                text="@@help"
            )
            
            await message_handler.handle_message(message, slack_client)
            
            # Should have sent response
            mock_client.chat_postMessage.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self, test_config):
        """Test error recovery in Slack integration."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_socket, \
             patch('slack_sdk.WebClient') as mock_web_client:
            
            mock_socket_client = AsyncMock()
            mock_socket.return_value = mock_socket_client
            
            # Simulate connection failure and recovery
            mock_socket_client.connect = AsyncMock(side_effect=[
                Exception("Network error"),
                None  # Success on retry
            ])
            
            slack_client = SlackBotClient(test_config)
            slack_client.max_reconnect_attempts = 2
            
            await slack_client.connect()
            
            assert slack_client.is_connected
            assert slack_client.reconnect_attempts == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, test_config):
        """Test rate limiting handling."""
        with patch('slack_sdk.WebClient') as mock_web_client:
            from slack_sdk.errors import SlackApiError
            
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            
            # Simulate rate limiting
            mock_client.chat_postMessage = AsyncMock(side_effect=SlackApiError(
                message="Rate limited",
                response={"error": "rate_limited", "headers": {"Retry-After": "1"}}
            ))
            
            slack_client = SlackBotClient(test_config)
            slack_client.is_connected = True
            
            # Should handle rate limiting gracefully
            with pytest.raises(SlackError):
                await slack_client.send_message("C1234567890", "Test message")