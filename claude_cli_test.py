#!/usr/bin/env python3
"""
Direct test of Claude CLI integration.
This tests if we can successfully communicate with Claude Code CLI.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from claude_remote_client.config import load_config
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.utils import setup_logging


async def test_claude_cli():
    """Test Claude CLI directly."""
    # Load environment
    load_dotenv()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Testing Claude CLI integration...")
    
    try:
        # Load config
        config_path = project_root / "config.yaml"
        config = load_config(str(config_path))
        
        # Check Claude CLI path
        claude_path = config.claude.cli_path
        logger.info(f"Claude CLI path: {claude_path}")
        
        # Check if path exists
        if not os.path.exists(claude_path):
            logger.error(f"Claude CLI not found at: {claude_path}")
            return
        
        # Initialize session manager
        session_manager = SessionManager(config)
        await session_manager.start()
        logger.info("Session manager started")
        
        # Get project path
        project_path = os.getenv("PROJECT_PATH")
        logger.info(f"Project path: {project_path}")
        
        # Create a session
        logger.info("Creating Claude session...")
        session = await session_manager.create_session(project_path)
        logger.info(f"✅ Session created: {session.session_id}")
        
        # Send test messages
        test_messages = [
            "Hello Claude! Please respond with 'Test successful!'",
            "What is 2 + 2?",
            "Can you see the project files?"
        ]
        
        for msg in test_messages:
            logger.info(f"\n📤 Sending: {msg}")
            response = await session_manager.send_message(session.session_id, msg)
            logger.info(f"📥 Response: {response}")
        
        # Cleanup
        logger.info("\nTerminating session...")
        await session_manager.terminate_session(session.session_id)
        logger.info("✅ Session terminated")
        
        await session_manager.stop()
        logger.info("✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_claude_cli())