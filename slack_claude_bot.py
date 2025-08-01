#!/usr/bin/env python3
"""
Real-time Slack bot that integrates with Claude Code CLI.
This bot listens for messages and routes them to Claude.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.rtm.v2 import RTMClient

from claude_remote_client.config import load_config
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.utils import setup_logging


class SlackClaudeBot:
    """Real-time Slack bot integrated with Claude."""
    
    def __init__(self, config, session_manager):
        self.config = config
        self.session_manager = session_manager
        self.logger = setup_logging()
        
        # Slack clients
        self.web_client = AsyncWebClient(token=config.slack.bot_token)
        self.rtm_client = None
        
        # Active sessions
        self.active_sessions = {}  # channel_id -> session_id
        
        # Bot info
        self.bot_user_id = None
    
    async def start(self):
        """Start the bot."""
        try:
            # Test authentication
            auth_response = await self.web_client.auth_test()
            self.bot_user_id = auth_response["user_id"]
            self.logger.info(f"Authenticated as {auth_response['user']} (ID: {self.bot_user_id})")
            
            # Start RTM client
            self.rtm_client = RTMClient(token=self.config.slack.bot_token)
            
            # Register handlers
            @self.rtm_client.on("message")
            async def handle_message(client: RTMClient, event: Dict[str, Any]):
                await self._handle_message(event)
            
            # Connect
            await self.rtm_client.start()
            self.logger.info("RTM connection established")
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            raise
    
    async def _handle_message(self, event: Dict[str, Any]):
        """Handle incoming message."""
        try:
            # Skip bot's own messages
            if event.get("user") == self.bot_user_id:
                return
            
            # Get message details
            channel = event.get("channel")
            text = event.get("text", "")
            user = event.get("user")
            
            if not channel or not text:
                return
            
            self.logger.info(f"Message from {user} in {channel}: {text}")
            
            # Handle commands
            if text.startswith("@@"):
                await self._handle_command(channel, text[2:].strip(), user)
            else:
                # Route to Claude if session is active
                await self._route_to_claude(channel, text, user)
        
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
    
    async def _handle_command(self, channel: str, command: str, user: str):
        """Handle bot commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "help":
            await self._send_help(channel)
        
        elif cmd == "start":
            await self._start_session(channel, user)
        
        elif cmd == "stop":
            await self._stop_session(channel, user)
        
        elif cmd == "status":
            await self._show_status(channel)
        
        else:
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"Unknown command: {cmd}. Type `@@help` for available commands."
            )
    
    async def _send_help(self, channel: str):
        """Send help message."""
        help_text = """*Claude Bot Commands:*
• `@@help` - Show this help message
• `@@start` - Start a Claude session in this channel
• `@@stop` - Stop the Claude session in this channel
• `@@status` - Show current session status

When a session is active, all non-command messages will be sent to Claude."""
        
        await self.web_client.chat_postMessage(
            channel=channel,
            text=help_text
        )
    
    async def _start_session(self, channel: str, user: str):
        """Start a Claude session."""
        if channel in self.active_sessions:
            await self.web_client.chat_postMessage(
                channel=channel,
                text="A Claude session is already active in this channel."
            )
            return
        
        try:
            # Create session
            project_path = os.getenv("PROJECT_PATH")
            session = await self.session_manager.create_session(project_path)
            self.active_sessions[channel] = session.session_id
            
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"✅ Started Claude session. All messages will now be sent to Claude.\nSession ID: `{session.session_id}`"
            )
            
        except Exception as e:
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"❌ Failed to start Claude session: {str(e)}"
            )
    
    async def _stop_session(self, channel: str, user: str):
        """Stop a Claude session."""
        if channel not in self.active_sessions:
            await self.web_client.chat_postMessage(
                channel=channel,
                text="No active Claude session in this channel."
            )
            return
        
        try:
            session_id = self.active_sessions[channel]
            await self.session_manager.terminate_session(session_id)
            del self.active_sessions[channel]
            
            await self.web_client.chat_postMessage(
                channel=channel,
                text="✅ Claude session stopped."
            )
            
        except Exception as e:
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"❌ Failed to stop session: {str(e)}"
            )
    
    async def _show_status(self, channel: str):
        """Show session status."""
        if channel in self.active_sessions:
            session_id = self.active_sessions[channel]
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"✅ Claude session active\nSession ID: `{session_id}`"
            )
        else:
            await self.web_client.chat_postMessage(
                channel=channel,
                text="❌ No active Claude session in this channel"
            )
    
    async def _route_to_claude(self, channel: str, text: str, user: str):
        """Route message to Claude."""
        if channel not in self.active_sessions:
            # Don't respond to non-command messages without a session
            return
        
        session_id = self.active_sessions[channel]
        
        try:
            # Send typing indicator
            await self.web_client.chat_postMessage(
                channel=channel,
                text="🤔 Claude is thinking..."
            )
            
            # Send to Claude
            response = await self.session_manager.send_message(session_id, text)
            
            if response:
                # Send Claude's response
                await self.web_client.chat_postMessage(
                    channel=channel,
                    text=f"🤖 Claude: {response}"
                )
            else:
                await self.web_client.chat_postMessage(
                    channel=channel,
                    text="❌ No response from Claude"
                )
        
        except Exception as e:
            self.logger.error(f"Error routing to Claude: {e}")
            await self.web_client.chat_postMessage(
                channel=channel,
                text=f"❌ Error: {str(e)}"
            )


async def main():
    """Main entry point."""
    # Load environment
    load_dotenv()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Slack-Claude bot...")
    
    try:
        # Load config
        config_path = project_root / "config.yaml"
        config = load_config(str(config_path))
        
        # Initialize session manager
        session_manager = SessionManager(config)
        await session_manager.start()
        
        # Create and start bot
        bot = SlackClaudeBot(config, session_manager)
        await bot.start()
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    
    finally:
        if 'session_manager' in locals():
            await session_manager.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())