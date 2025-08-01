#!/usr/bin/env python3
"""
Slack-Claude Bridge: Direct integration between Slack and Claude Code CLI.
This implementation bypasses complex session management for direct communication.
"""

import asyncio
import os
import sys
import logging
import subprocess
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, Optional, Set
from collections import deque

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError


class ClaudeDirectInterface:
    """Direct interface to Claude Code CLI."""
    
    def __init__(self, claude_path: str, project_path: str, logger: logging.Logger):
        self.claude_path = claude_path
        self.project_path = project_path
        self.logger = logger
        self.process = None
        self.session_id = None
        
    async def start_session(self) -> bool:
        """Start a Claude session (test Claude availability)."""
        try:
            self.session_id = str(uuid.uuid4())[:8]
            self.logger.info(f"Testing Claude CLI availability...")
            
            # Test Claude CLI with a simple command
            cmd = [self.claude_path, '--version']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                version = stdout.decode().strip()
                self.logger.info(f"Claude CLI available: {version}")
                return True
            else:
                self.logger.error(f"Claude CLI error: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Claude: {e}")
            return False
    
    async def send_message(self, message: str) -> str:
        """Send a message to Claude and get response."""
        try:
            # Create a new Claude process for each message in print mode
            # Change to project directory first
            cmd = [
                self.claude_path,
                '--print',  # Print mode for single response
                message  # The prompt
            ]
            
            self.logger.info(f"Sending to Claude: {message}")
            
            # Run Claude from the project directory
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_path  # Run from project directory
            )
            
            # Get the response
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"Claude error: {error_msg}")
                return f"Error from Claude: {error_msg}"
            
            response = stdout.decode().strip()
            
            if not response:
                return "Claude returned an empty response"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error sending to Claude: {e}")
            return f"Error communicating with Claude: {str(e)}"
    
    async def stop_session(self):
        """Stop the Claude session."""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
                self.logger.info("Claude session stopped")
            except Exception as e:
                self.logger.error(f"Error stopping Claude: {e}")


class SlackClaudeBridge:
    """Bridges Slack and Claude for bidirectional communication."""
    
    def __init__(self, slack_token: str, channel_id: str, claude_interface: ClaudeDirectInterface, logger: logging.Logger):
        self.slack = AsyncWebClient(token=slack_token)
        self.channel_id = channel_id
        self.claude = claude_interface
        self.logger = logger
        
        # State management
        self.bot_user_id = None
        self.is_active = False
        self.processed_messages = deque(maxlen=1000)  # Keep last 1000 message IDs
        self.last_poll_time = None
        
    async def start(self):
        """Start the bridge."""
        try:
            # Verify Slack connection
            auth = await self.slack.auth_test()
            self.bot_user_id = auth["user_id"]
            self.logger.info(f"Connected to Slack as {auth['user']} (ID: {self.bot_user_id})")
            
            # Start Claude session
            if not await self.claude.start_session():
                raise Exception("Failed to start Claude session")
            
            # Send startup message
            await self.slack.chat_postMessage(
                channel=self.channel_id,
                text="🚀 Slack-Claude Bridge is online!\n\nCommands:\n• `@claude <message>` - Send message to Claude\n• `@@status` - Check bridge status\n• `@@stop` - Stop the bridge\n\nOr just type normally and I'll route to Claude!"
            )
            
            self.is_active = True
            self.logger.info("Bridge started successfully")
            
            # Start message polling
            await self._poll_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            raise
    
    async def _poll_loop(self):
        """Main polling loop."""
        self.logger.info("Starting message polling loop")
        
        while self.is_active:
            try:
                await self._poll_messages()
                await asyncio.sleep(1)  # Poll every second
                
            except Exception as e:
                self.logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _poll_messages(self):
        """Poll for new messages."""
        try:
            # Get recent messages
            result = await self.slack.conversations_history(
                channel=self.channel_id,
                limit=10
            )
            
            if not result["ok"]:
                return
            
            # Process messages in chronological order
            messages = reversed(result.get("messages", []))
            
            for msg in messages:
                await self._process_message(msg)
                
        except Exception as e:
            self.logger.error(f"Error polling messages: {e}")
    
    def _get_message_id(self, message: Dict[str, Any]) -> str:
        """Get unique message ID."""
        return f"{message.get('ts', '')}_{message.get('client_msg_id', '')}"
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process a single message."""
        # Get message ID
        msg_id = self._get_message_id(message)
        
        # Skip if already processed
        if msg_id in self.processed_messages:
            return
            
        # Mark as processed
        self.processed_messages.append(msg_id)
        
        # Skip bot messages
        if message.get("user") == self.bot_user_id:
            return
        
        # Get message text
        text = message.get("text", "").strip()
        if not text:
            return
        
        # Get user
        user = message.get("user")
        if not user:
            return
        
        self.logger.info(f"New message from {user}: {text}")
        
        # Handle commands
        if text.startswith("@@"):
            await self._handle_command(text[2:].strip())
        elif text.lower().startswith("@claude"):
            # Direct Claude mention
            claude_msg = text[7:].strip()
            if claude_msg:
                await self._route_to_claude(claude_msg)
        else:
            # Route all messages to Claude when active
            await self._route_to_claude(text)
    
    async def _handle_command(self, command: str):
        """Handle bridge commands."""
        cmd = command.lower()
        
        if cmd == "status":
            status = "✅ Active" if self.is_active else "❌ Inactive"
            await self.slack.chat_postMessage(
                channel=self.channel_id,
                text=f"**Bridge Status:**\n• Slack: ✅ Connected\n• Claude: {status}\n• Session: {self.claude.session_id or 'None'}"
            )
        
        elif cmd == "stop":
            await self.stop()
        
        else:
            await self.slack.chat_postMessage(
                channel=self.channel_id,
                text=f"Unknown command: {command}"
            )
    
    async def _route_to_claude(self, message: str):
        """Route message to Claude."""
        try:
            # Send typing indicator
            self.logger.info(f"Routing to Claude: {message}")
            
            # Get Claude's response
            response = await self.claude.send_message(message)
            
            # Send response back to Slack
            await self.slack.chat_postMessage(
                channel=self.channel_id,
                text=f"🤖 **Claude:**\n{response}"
            )
            
        except Exception as e:
            self.logger.error(f"Error routing to Claude: {e}")
            await self.slack.chat_postMessage(
                channel=self.channel_id,
                text=f"❌ Error communicating with Claude: {str(e)}"
            )
    
    async def stop(self):
        """Stop the bridge."""
        self.is_active = False
        
        await self.slack.chat_postMessage(
            channel=self.channel_id,
            text="👋 Slack-Claude Bridge shutting down..."
        )
        
        await self.claude.stop_session()
        self.logger.info("Bridge stopped")


def setup_logging() -> logging.Logger:
    """Set up logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('slack-claude-bridge')


async def main():
    """Main entry point."""
    # Load environment
    load_dotenv()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Slack-Claude Bridge...")
    
    # Get configuration
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL")
    claude_path = os.getenv("CLAUDE_CLI_PATH")
    project_path = os.getenv("PROJECT_PATH")
    
    if not all([slack_token, channel_id, claude_path, project_path]):
        logger.error("Missing required environment variables")
        return
    
    try:
        # Create components
        claude = ClaudeDirectInterface(claude_path, project_path, logger)
        bridge = SlackClaudeBridge(slack_token, channel_id, claude, logger)
        
        # Start the bridge
        await bridge.start()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Bridge error: {e}", exc_info=True)
    finally:
        if 'bridge' in locals():
            await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())