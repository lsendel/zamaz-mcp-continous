"""
Simple Slack client for bot token authentication.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from ..config import SlackConfig
from ..utils import setup_logging


class SimpleSlackClient:
    """Simple Slack client using bot token only."""
    
    def __init__(self, config: SlackConfig):
        """Initialize the client."""
        self.config = config
        self.logger = setup_logging()
        self.client = AsyncWebClient(token=config.bot_token)
        self.is_connected = False
    
    async def connect(self):
        """Test connection to Slack."""
        try:
            response = await self.client.auth_test()
            self.is_connected = True
            self.logger.info(f"Connected to Slack as {response['user']} in team {response['team']}")
            return True
        except SlackApiError as e:
            self.logger.error(f"Slack connection failed: {e}")
            self.is_connected = False
            return False
    
    async def send_message(self, channel: str, text: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Send a message to a Slack channel."""
        try:
            response = await self.client.chat_postMessage(
                channel=channel,
                text=text,
                **kwargs
            )
            return response
        except SlackApiError as e:
            self.logger.error(f"Failed to send message: {e}")
            return None
    
    async def disconnect(self):
        """Disconnect from Slack."""
        self.is_connected = False
        self.logger.info("Disconnected from Slack")