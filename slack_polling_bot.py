#!/usr/bin/env python3
"""
Slack bot that polls for messages and integrates with Claude.
Uses conversations.history to poll for new messages.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from claude_remote_client.config import load_config
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.utils import setup_logging


class SlackPollingBot:
    """Slack bot that polls for messages and routes to Claude."""
    
    def __init__(self, config, session_manager):
        self.config = config
        self.session_manager = session_manager
        self.logger = setup_logging()
        
        # Slack client
        self.client = AsyncWebClient(token=config.slack.bot_token)
        
        # State
        self.bot_user_id = None
        self.active_sessions = {}  # channel_id -> session_id
        self.last_message_ts = {}  # channel_id -> timestamp
        self.processed_messages = set()  # Set of processed message IDs
        
        # Polling settings
        self.poll_interval = 2  # seconds
        self.channel_id = config.slack.channel_id
    
    async def start(self):
        """Start the bot."""
        try:
            # Test authentication
            auth_response = await self.client.auth_test()
            self.bot_user_id = auth_response["user_id"]
            self.logger.info(f"Authenticated as {auth_response['user']} (ID: {self.bot_user_id})")
            
            # Send startup message
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="🤖 Claude Bot is online! Type `@@help` for commands."
            )
            
            # Start polling
            await self._poll_messages()
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            raise
    
    async def _poll_messages(self):
        """Poll for new messages."""
        self.logger.info(f"Starting message polling for channel {self.channel_id}")
        
        while True:
            try:
                # Get conversation history
                result = await self.client.conversations_history(
                    channel=self.channel_id,
                    limit=10
                )
                
                if result["ok"]:
                    messages = result["messages"]
                    
                    # Process messages in chronological order
                    for message in reversed(messages):
                        await self._process_message(message)
                
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def _get_message_id(self, message: Dict[str, Any]) -> str:
        """Get unique message ID."""
        return f"{message.get('ts', '')}_{message.get('user', '')}"
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process a single message."""
        # Get message ID
        msg_id = self._get_message_id(message)
        
        # Skip if already processed
        if msg_id in self.processed_messages:
            return
        
        # Mark as processed
        self.processed_messages.add(msg_id)
        
        # Keep only recent message IDs to prevent memory growth
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])
        
        # Skip bot's own messages
        if message.get("user") == self.bot_user_id:
            return
        
        # Skip messages without text
        text = message.get("text", "").strip()
        if not text:
            return
        
        # Get user
        user = message.get("user")
        if not user:
            return
        
        self.logger.info(f"Processing message from {user}: {text}")
        
        # Handle commands
        if text.startswith("@@"):
            await self._handle_command(text[2:].strip(), user)
        else:
            # Route to Claude if session is active
            await self._route_to_claude(text, user)
    
    async def _handle_command(self, command: str, user: str):
        """Handle bot commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "help":
            await self._send_help()
        
        elif cmd == "start":
            await self._start_session(user)
        
        elif cmd == "stop":
            await self._stop_session(user)
        
        elif cmd == "status":
            await self._show_status()
        
        else:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"Unknown command: {cmd}. Type `@@help` for available commands."
            )
    
    async def _send_help(self):
        """Send help message."""
        help_text = """*Claude Bot Commands:*
• `@@help` - Show this help message
• `@@start` - Start a Claude session
• `@@stop` - Stop the Claude session
• `@@status` - Show current session status

When a session is active, all non-command messages will be sent to Claude."""
        
        await self.client.chat_postMessage(
            channel=self.channel_id,
            text=help_text
        )
    
    async def _start_session(self, user: str):
        """Start a Claude session."""
        if self.channel_id in self.active_sessions:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="A Claude session is already active."
            )
            return
        
        try:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="🔄 Starting Claude session..."
            )
            
            # Create session
            project_path = os.getenv("PROJECT_PATH")
            session = await self.session_manager.create_session(project_path)
            self.active_sessions[self.channel_id] = session.session_id
            
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"✅ Claude session started!\nYou can now chat with Claude. Type `@@stop` to end the session."
            )
            
        except Exception as e:
            self.logger.error(f"Failed to start session: {e}")
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"❌ Failed to start Claude session: {str(e)}"
            )
    
    async def _stop_session(self, user: str):
        """Stop a Claude session."""
        if self.channel_id not in self.active_sessions:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="No active Claude session."
            )
            return
        
        try:
            session_id = self.active_sessions[self.channel_id]
            await self.session_manager.terminate_session(session_id)
            del self.active_sessions[self.channel_id]
            
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="✅ Claude session stopped."
            )
            
        except Exception as e:
            self.logger.error(f"Failed to stop session: {e}")
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"❌ Failed to stop session: {str(e)}"
            )
    
    async def _show_status(self):
        """Show session status."""
        if self.channel_id in self.active_sessions:
            session_id = self.active_sessions[self.channel_id]
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"✅ Claude session active\nSession ID: `{session_id}`"
            )
        else:
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text="❌ No active Claude session"
            )
    
    async def _route_to_claude(self, text: str, user: str):
        """Route message to Claude."""
        if self.channel_id not in self.active_sessions:
            # Don't respond to non-command messages without a session
            return
        
        session_id = self.active_sessions[self.channel_id]
        
        try:
            # Send to Claude
            self.logger.info(f"Sending to Claude: {text}")
            response = await self.session_manager.send_message(session_id, text)
            
            if response:
                # Send Claude's response
                self.logger.info(f"Claude response: {response[:100]}...")
                await self.client.chat_postMessage(
                    channel=self.channel_id,
                    text=response
                )
            else:
                await self.client.chat_postMessage(
                    channel=self.channel_id,
                    text="❌ No response from Claude"
                )
        
        except Exception as e:
            self.logger.error(f"Error routing to Claude: {e}")
            await self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"❌ Error: {str(e)}"
            )


async def main():
    """Main entry point."""
    # Load environment
    load_dotenv()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Slack polling bot...")
    
    try:
        # Load config
        config_path = project_root / "config.yaml"
        config = load_config(str(config_path))
        
        # Initialize session manager
        session_manager = SessionManager(config)
        await session_manager.start()
        logger.info("Session manager started")
        
        # Create and start bot
        bot = SlackPollingBot(config, session_manager)
        await bot.start()
        
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    
    finally:
        if 'session_manager' in locals():
            await session_manager.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())