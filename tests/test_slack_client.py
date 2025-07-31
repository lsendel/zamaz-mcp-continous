"""
Unit tests for Slack bot client.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.config import SlackConfig
from claude_remote_client.models import SlackMessage
from claude_remote_client.exceptions import SlackConnectionError


@pytest.fixture
def slack_config():
    """Create a test Slack configuration."""
    return SlackConfig(
        bot_token="xoxb-test-token",
        app_token="xapp-test-token",
        channel_id="C1234567890",
        signing_secret="test-secret"
    )


@pytest.fixture
def slack_client(slack_config):
    """Create a test Slack client."""
    with patch('slack_sdk.socket_mode.async_client.AsyncBaseSocketModeClient'), \
         patch('slack_sdk.web.async_client.AsyncWebClient'):
        client = SlackBotClient(slack_config)
        return client


class TestSlackBotClient:
    """Test cases for SlackBotClient."""
    
    def test_client_initialization(self, slack_config):
        """Test client initialization."""
        with patch('slack_sdk.socket_mode.async_client.AsyncBaseSocketModeClient'), \
             patch('slack_sdk.web.async_client.AsyncWebClient'):
            
            client = SlackBotClient(slack_config)
            
            assert client.config == slack_config
            assert client.is_connected is False
            assert client.reconnect_attempts == 0
            assert client.max_reconnect_attempts == 10
            assert client.message_handlers == []
    
    @pytest.mark.asyncio
    async def test_connect_success(self, slack_client):
        """Test successful connection."""
        # Mock the auth test
        slack_client.web_client.auth_test = AsyncMock(return_value={
            "ok": True,
            "user": "test_bot"
        })
        
        # Mock socket client connect
        slack_client.socket_client.connect = AsyncMock()
        
        await slack_client.connect()
        
        assert slack_client.is_connected is True
        assert slack_client.reconnect_attempts == 0
        slack_client.web_client.auth_test.assert_called_once()
        slack_client.socket_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, slack_client):
        """Test connection failure due to auth error."""
        # Mock failed auth test
        slack_client.web_client.auth_test = AsyncMock(return_value={
            "ok": False,
            "error": "invalid_auth"
        })
        
        with pytest.raises(SlackConnectionError) as exc_info:
            await slack_client.connect()
        
        assert "Auth test failed" in str(exc_info.value)
        assert slack_client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connect_with_retries(self, slack_client):
        """Test connection with retries."""
        # Mock auth test to fail first time, succeed second time
        slack_client.web_client.auth_test = AsyncMock(side_effect=[
            Exception("Network error"),
            {"ok": True, "user": "test_bot"}
        ])
        
        slack_client.socket_client.connect = AsyncMock()
        slack_client.max_reconnect_attempts = 3
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await slack_client.connect()
        
        assert slack_client.is_connected is True
        assert slack_client.web_client.auth_test.call_count == 2
    
    @pytest.mark.asyncio
    async def test_connect_max_retries_exceeded(self, slack_client):
        """Test connection failure after max retries."""
        # Mock auth test to always fail
        slack_client.web_client.auth_test = AsyncMock(side_effect=Exception("Network error"))
        slack_client.max_reconnect_attempts = 2
        
        # Mock sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(SlackConnectionError) as exc_info:
                await slack_client.connect()
        
        assert "Failed to connect to Slack after maximum retry attempts" in str(exc_info.value)
        assert slack_client.is_connected is False
        assert slack_client.reconnect_attempts == 2
    
    @pytest.mark.asyncio
    async def test_disconnect(self, slack_client):
        """Test disconnection."""
        slack_client.is_connected = True
        slack_client.socket_client.disconnect = AsyncMock()
        
        await slack_client.disconnect()
        
        assert slack_client.is_connected is False
        slack_client.socket_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_client):
        """Test successful message sending."""
        slack_client.is_connected = True
        slack_client.web_client.chat_postMessage = AsyncMock(return_value={
            "ok": True,
            "ts": "1234567890.123456"
        })
        
        response = await slack_client.send_message("C1234567890", "Hello, world!")
        
        assert response["ok"] is True
        assert "ts" in response
        slack_client.web_client.chat_postMessage.assert_called_once_with(
            channel="C1234567890",
            text="Hello, world!",
            thread_ts=None
        )
    
    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, slack_client):
        """Test sending message when not connected."""
        slack_client.is_connected = False
        
        with pytest.raises(SlackConnectionError) as exc_info:
            await slack_client.send_message("C1234567890", "Hello, world!")
        
        assert "Not connected to Slack" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_api_error(self, slack_client):
        """Test message sending with API error."""
        slack_client.is_connected = True
        slack_client.web_client.chat_postMessage = AsyncMock(return_value={
            "ok": False,
            "error": "channel_not_found"
        })
        
        with pytest.raises(SlackConnectionError) as exc_info:
            await slack_client.send_message("C1234567890", "Hello, world!")
        
        assert "Failed to send message" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_send_message_with_thread(self, slack_client):
        """Test sending threaded message."""
        slack_client.is_connected = True
        slack_client.web_client.chat_postMessage = AsyncMock(return_value={
            "ok": True,
            "ts": "1234567890.123456"
        })
        
        await slack_client.send_message("C1234567890", "Reply", thread_ts="1234567890.000000")
        
        slack_client.web_client.chat_postMessage.assert_called_once_with(
            channel="C1234567890",
            text="Reply",
            thread_ts="1234567890.000000"
        )
    
    @pytest.mark.asyncio
    async def test_update_message(self, slack_client):
        """Test message updating."""
        slack_client.web_client.chat_update = AsyncMock(return_value={
            "ok": True,
            "ts": "1234567890.123456"
        })
        
        response = await slack_client.update_message("C1234567890", "1234567890.123456", "Updated text")
        
        assert response["ok"] is True
        slack_client.web_client.chat_update.assert_called_once_with(
            channel="C1234567890",
            ts="1234567890.123456",
            text="Updated text"
        )
    
    @pytest.mark.asyncio
    async def test_delete_message(self, slack_client):
        """Test message deletion."""
        slack_client.web_client.chat_delete = AsyncMock(return_value={
            "ok": True,
            "ts": "1234567890.123456"
        })
        
        response = await slack_client.delete_message("C1234567890", "1234567890.123456")
        
        assert response["ok"] is True
        slack_client.web_client.chat_delete.assert_called_once_with(
            channel="C1234567890",
            ts="1234567890.123456"
        )
    
    def test_add_message_handler(self, slack_client):
        """Test adding message handler."""
        async def test_handler(message):
            pass
        
        slack_client.add_message_handler(test_handler)
        
        assert test_handler in slack_client.message_handlers
        assert len(slack_client.message_handlers) == 1
    
    def test_remove_message_handler(self, slack_client):
        """Test removing message handler."""
        async def test_handler(message):
            pass
        
        slack_client.add_message_handler(test_handler)
        slack_client.remove_message_handler(test_handler)
        
        assert test_handler not in slack_client.message_handlers
        assert len(slack_client.message_handlers) == 0
    
    @pytest.mark.asyncio
    async def test_handle_message_event(self, slack_client):
        """Test handling message events."""
        handler_called = False
        received_message = None
        
        async def test_handler(message):
            nonlocal handler_called, received_message
            handler_called = True
            received_message = message
        
        slack_client.add_message_handler(test_handler)
        
        # Simulate message event
        event = {
            "type": "message",
            "channel": "C1234567890",
            "user": "U1234567890",
            "text": "Hello, bot!",
            "ts": "1234567890.123456"
        }
        
        await slack_client._handle_message_event(event)
        
        assert handler_called is True
        assert isinstance(received_message, SlackMessage)
        assert received_message.text == "Hello, bot!"
        assert received_message.channel_id == "C1234567890"
        assert received_message.user_id == "U1234567890"
    
    @pytest.mark.asyncio
    async def test_handle_message_event_wrong_channel(self, slack_client):
        """Test ignoring messages from wrong channel."""
        handler_called = False
        
        async def test_handler(message):
            nonlocal handler_called
            handler_called = True
        
        slack_client.add_message_handler(test_handler)
        
        # Simulate message event from different channel
        event = {
            "type": "message",
            "channel": "C9999999999",  # Different channel
            "user": "U1234567890",
            "text": "Hello, bot!",
            "ts": "1234567890.123456"
        }
        
        await slack_client._handle_message_event(event)
        
        assert handler_called is False
    
    @pytest.mark.asyncio
    async def test_handle_message_event_bot_message(self, slack_client):
        """Test ignoring bot messages."""
        handler_called = False
        
        async def test_handler(message):
            nonlocal handler_called
            handler_called = True
        
        slack_client.add_message_handler(test_handler)
        
        # Simulate bot message event
        event = {
            "type": "message",
            "channel": "C1234567890",
            "user": "U1234567890",
            "text": "Hello, bot!",
            "ts": "1234567890.123456",
            "bot_id": "B1234567890"  # Bot message
        }
        
        await slack_client._handle_message_event(event)
        
        assert handler_called is False
    
    @pytest.mark.asyncio
    async def test_get_channel_info(self, slack_client):
        """Test getting channel information."""
        slack_client.web_client.conversations_info = AsyncMock(return_value={
            "ok": True,
            "channel": {
                "id": "C1234567890",
                "name": "general",
                "is_channel": True
            }
        })
        
        channel_info = await slack_client.get_channel_info("C1234567890")
        
        assert channel_info["id"] == "C1234567890"
        assert channel_info["name"] == "general"
        slack_client.web_client.conversations_info.assert_called_once_with(channel="C1234567890")
    
    @pytest.mark.asyncio
    async def test_get_user_info(self, slack_client):
        """Test getting user information."""
        slack_client.web_client.users_info = AsyncMock(return_value={
            "ok": True,
            "user": {
                "id": "U1234567890",
                "name": "testuser",
                "real_name": "Test User"
            }
        })
        
        user_info = await slack_client.get_user_info("U1234567890")
        
        assert user_info["id"] == "U1234567890"
        assert user_info["name"] == "testuser"
        slack_client.web_client.users_info.assert_called_once_with(user="U1234567890")