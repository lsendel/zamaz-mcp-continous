"""
Slack bot client implementation with WebSocket connection.

This module provides the core Slack bot functionality including connection management,
message handling, and reconnection logic.
"""

import asyncio
import logging
from typing import Optional, Callable, AsyncIterator
from datetime import datetime
import json

from slack_sdk.socket_mode.async_client import AsyncBaseSocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.errors import SlackApiError

from ..models import SlackMessage
from ..config import SlackConfig
from ..exceptions import SlackConnectionError
from ..utils import setup_logging, format_error_for_slack


class SlackBotClient:
    """
    Async Slack bot client with WebSocket connection and reconnection logic.
    
    Handles all Slack communication including sending/receiving messages,
    connection management, and error recovery.
    """
    
    def __init__(self, config: SlackConfig):
        """
        Initialize the Slack bot client.
        
        Args:
            config: Slack configuration containing tokens and settings
        """
        self.config = config
        self.logger = setup_logging()
        
        # Initialize Slack clients
        self.web_client = AsyncWebClient(token=config.bot_token)
        self.socket_client = AsyncBaseSocketModeClient(
            app_token=config.app_token,
            web_client=self.web_client
        )
        
        # Connection state
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = 300  # Max 5 minutes
        
        # Message handlers
        self.message_handlers = []
        
        # Setup socket mode handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up Socket Mode event handlers."""
        
        @self.socket_client.socket_mode_request_listeners.append
        async def handle_socket_mode_request(client: AsyncBaseSocketModeClient, req: SocketModeRequest):
            """Handle incoming Socket Mode requests."""
            try:
                if req.type == "events_api":
                    # Handle Events API events
                    await self._handle_events_api(req)
                elif req.type == "slash_commands":
                    # Handle slash commands (if needed in future)
                    await self._handle_slash_command(req)
                
                # Acknowledge the request
                response = SocketModeResponse(envelope_id=req.envelope_id)
                await client.send_socket_mode_response(response)
                
            except Exception as e:
                self.logger.error(f"Error handling socket mode request: {e}")
                # Still acknowledge to prevent retries
                response = SocketModeResponse(envelope_id=req.envelope_id)
                await client.send_socket_mode_response(response)
    
    async def _handle_events_api(self, req: SocketModeRequest):
        """Handle Events API events."""
        event = req.payload.get("event", {})
        event_type = event.get("type")
        
        if event_type == "message":
            await self._handle_message_event(event)
        elif event_type == "app_mention":
            await self._handle_mention_event(event)
    
    async def _handle_message_event(self, event: dict):
        """Handle message events."""
        # Skip bot messages and messages without text
        if event.get("bot_id") or not event.get("text"):
            return
        
        # Skip messages not in our configured channel
        if event.get("channel") != self.config.channel_id:
            return
        
        # Create SlackMessage object
        message = SlackMessage(
            channel_id=event.get("channel", ""),
            user_id=event.get("user", ""),
            text=event.get("text", ""),
            timestamp=datetime.now(),
            thread_ts=event.get("thread_ts"),
            is_bot_message=bool(event.get("bot_id"))
        )
        
        # Notify message handlers
        for handler in self.message_handlers:
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")
    
    async def _handle_mention_event(self, event: dict):
        """Handle app mention events."""
        # Convert mention to regular message for processing
        await self._handle_message_event(event)
    
    async def _handle_slash_command(self, req: SocketModeRequest):
        """Handle slash commands (placeholder for future use)."""
        self.logger.info(f"Received slash command: {req.payload}")
    
    async def connect(self) -> None:
        """
        Connect to Slack with automatic reconnection.
        
        Raises:
            SlackConnectionError: If connection fails after all retry attempts
        """
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self.logger.info("Connecting to Slack...")
                
                # Test the connection first
                await self._test_connection()
                
                # Start the socket mode client
                await self.socket_client.connect()
                
                self.is_connected = True
                self.reconnect_attempts = 0
                self.reconnect_delay = 1  # Reset delay
                
                self.logger.info("Successfully connected to Slack")
                return
                
            except Exception as e:
                self.reconnect_attempts += 1
                self.is_connected = False
                
                self.logger.error(
                    f"Failed to connect to Slack (attempt {self.reconnect_attempts}/"
                    f"{self.max_reconnect_attempts}): {e}"
                )
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    raise SlackConnectionError(
                        "Failed to connect to Slack after maximum retry attempts",
                        str(e)
                    )
                
                # Exponential backoff with jitter
                delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 
                           self.max_reconnect_delay)
                
                self.logger.info(f"Retrying connection in {delay} seconds...")
                await asyncio.sleep(delay)
    
    async def _test_connection(self) -> None:
        """Test the Slack connection by calling auth.test."""
        try:
            response = await self.web_client.auth_test()
            if not response["ok"]:
                raise SlackConnectionError("Auth test failed", response.get("error", "Unknown error"))
            
            self.logger.info(f"Authenticated as: {response['user']}")
            
        except SlackApiError as e:
            raise SlackConnectionError("Slack API authentication failed", str(e))
    
    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        try:
            if self.socket_client and self.is_connected:
                await self.socket_client.disconnect()
            
            self.is_connected = False
            self.logger.info("Disconnected from Slack")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    async def send_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> dict:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Channel ID to send message to
            text: Message text
            thread_ts: Optional thread timestamp for threaded replies
        
        Returns:
            dict: Slack API response
        
        Raises:
            SlackConnectionError: If message sending fails
        """
        if not self.is_connected:
            raise SlackConnectionError("Not connected to Slack")
        
        try:
            response = await self.web_client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts
            )
            
            if not response["ok"]:
                raise SlackConnectionError(
                    "Failed to send message",
                    response.get("error", "Unknown error")
                )
            
            return response
            
        except SlackApiError as e:
            raise SlackConnectionError("Failed to send Slack message", str(e))
    
    async def send_typing_indicator(self, channel: str) -> None:
        """
        Send typing indicator to show bot is working.
        
        Args:
            channel: Channel ID to send typing indicator to
        """
        if not self.is_connected:
            return
        
        try:
            # Slack doesn't have a direct typing indicator for bots,
            # but we can send a temporary message and update it
            response = await self.web_client.chat_postMessage(
                channel=channel,
                text="⏳ Processing..."
            )
            
            # Return the message timestamp so caller can update/delete it
            return response.get("ts")
            
        except Exception as e:
            self.logger.error(f"Failed to send typing indicator: {e}")
    
    async def update_message(self, channel: str, ts: str, text: str) -> dict:
        """
        Update an existing message.
        
        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
        
        Returns:
            dict: Slack API response
        """
        try:
            response = await self.web_client.chat_update(
                channel=channel,
                ts=ts,
                text=text
            )
            
            if not response["ok"]:
                raise SlackConnectionError(
                    "Failed to update message",
                    response.get("error", "Unknown error")
                )
            
            return response
            
        except SlackApiError as e:
            raise SlackConnectionError("Failed to update Slack message", str(e))
    
    async def delete_message(self, channel: str, ts: str) -> dict:
        """
        Delete a message.
        
        Args:
            channel: Channel ID
            ts: Message timestamp
        
        Returns:
            dict: Slack API response
        """
        try:
            response = await self.web_client.chat_delete(
                channel=channel,
                ts=ts
            )
            
            if not response["ok"]:
                raise SlackConnectionError(
                    "Failed to delete message",
                    response.get("error", "Unknown error")
                )
            
            return response
            
        except SlackApiError as e:
            raise SlackConnectionError("Failed to delete Slack message", str(e))
    
    def add_message_handler(self, handler: Callable[[SlackMessage], None]) -> None:
        """
        Add a message handler function.
        
        Args:
            handler: Async function that takes a SlackMessage and processes it
        """
        self.message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable[[SlackMessage], None]) -> None:
        """
        Remove a message handler function.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
    
    async def listen_for_messages(self) -> AsyncIterator[SlackMessage]:
        """
        Listen for incoming messages (generator approach).
        
        This is an alternative to using message handlers.
        
        Yields:
            SlackMessage: Incoming messages
        """
        message_queue = asyncio.Queue()
        
        async def queue_handler(message: SlackMessage):
            await message_queue.put(message)
        
        self.add_message_handler(queue_handler)
        
        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(message_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    continue  # Check connection status and continue
                
        finally:
            self.remove_message_handler(queue_handler)
    
    async def get_channel_info(self, channel: str) -> dict:
        """
        Get information about a channel.
        
        Args:
            channel: Channel ID
        
        Returns:
            dict: Channel information
        """
        try:
            response = await self.web_client.conversations_info(channel=channel)
            
            if not response["ok"]:
                raise SlackConnectionError(
                    "Failed to get channel info",
                    response.get("error", "Unknown error")
                )
            
            return response["channel"]
            
        except SlackApiError as e:
            raise SlackConnectionError("Failed to get channel info", str(e))
    
    async def get_user_info(self, user: str) -> dict:
        """
        Get information about a user.
        
        Args:
            user: User ID
        
        Returns:
            dict: User information
        """
        try:
            response = await self.web_client.users_info(user=user)
            
            if not response["ok"]:
                raise SlackConnectionError(
                    "Failed to get user info",
                    response.get("error", "Unknown error")
                )
            
            return response["user"]
            
        except SlackApiError as e:
            raise SlackConnectionError("Failed to get user info", str(e))
    
    async def run_forever(self) -> None:
        """
        Run the bot forever with automatic reconnection.
        
        This method will keep the bot running and handle reconnections
        automatically if the connection is lost.
        """
        while True:
            try:
                if not self.is_connected:
                    await self.connect()
                
                # Keep the connection alive
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in main loop: {e}")
                self.is_connected = False
                await asyncio.sleep(5)  # Wait before retrying
        
        await self.disconnect()