#!/usr/bin/env python3
"""
Start the Claude Remote Client with Slack integration.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from claude_remote_client.config import load_config
from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.slack_client.command_router import CommandRouter
from claude_remote_client.slack_client.message_handler import MessageHandler
from claude_remote_client.utils import setup_logging

async def main():
    """Main entry point for the Slack bot."""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
    logger.info("Starting Claude Remote Client with Slack integration...")
    
    try:
        # Load configuration
        config_path = project_root / "config.yaml"
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return
        
        config = load_config(str(config_path))
        logger.info(f"Loaded configuration from {config_path}")
        
        # Initialize components
        session_manager = SessionManager(config)
        await session_manager.start()
        logger.info("Session manager started")
        
        # Create Slack client
        slack_client = SlackBotClient(config.slack)
        
        # Create command router and message handler
        command_router = CommandRouter(session_manager, slack_client)
        message_handler = MessageHandler(
            slack_client=slack_client,
            session_manager=session_manager,
            command_router=command_router
        )
        
        # Connect to Slack
        await slack_client.connect()
        logger.info("Connected to Slack successfully!")
        logger.info(f"Bot is listening in channel: {config.slack.default_channel}")
        
        # Send startup message
        await slack_client.send_message(
            channel=config.slack.default_channel,
            text="🤖 Claude Remote Client is now online! Use `@@help` to see available commands."
        )
        
        # Keep the bot running
        logger.info("Bot is running. Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
    finally:
        # Cleanup
        if 'session_manager' in locals():
            await session_manager.stop()
        if 'slack_client' in locals():
            await slack_client.disconnect()
        logger.info("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())