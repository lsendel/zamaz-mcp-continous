"""
Slack client module for the Claude Remote Client.

This module handles all Slack-related functionality including WebSocket connections,
message handling, and command processing.
"""

from .client import SlackBotClient
from .message_handler import MessageHandler
from .command_router import CommandRouter

__all__ = [
    "SlackBotClient",
    "MessageHandler", 
    "CommandRouter"
]