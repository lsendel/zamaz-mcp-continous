#!/usr/bin/env python3
"""
Test script to verify Slack-Claude integration.
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

from claude_remote_client.config import Config, load_config
from claude_remote_client.slack_client.simple_client import SimpleSlackClient
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.utils import setup_logging

async def test_slack_connection(slack_client, logger):
    """Test Slack connection."""
    logger.info("Testing Slack connection...")
    try:
        # Test authentication
        auth_response = await slack_client.client.auth_test()
        logger.info(f"✅ Slack authentication successful!")
        logger.info(f"   Bot User: {auth_response['user']}")
        logger.info(f"   Team: {auth_response['team']}")
        
        # Test channel access
        channel_id = os.getenv("SLACK_CHANNEL")
        logger.info(f"Testing access to channel: {channel_id}")
        
        # Send test message
        response = await slack_client.send_message(
            channel=channel_id,
            text="🧪 Test message from Claude Remote Client"
        )
        if response:
            logger.info("✅ Successfully sent message to Slack channel")
        else:
            logger.error("❌ Failed to send message to Slack channel")
            
        return True
    except Exception as e:
        logger.error(f"❌ Slack connection test failed: {e}")
        return False

async def test_claude_connection(session_manager, logger):
    """Test Claude CLI connection."""
    logger.info("Testing Claude CLI connection...")
    try:
        # Get project info from env
        project_name = os.getenv("PROJECT_NAME")
        project_path = os.getenv("PROJECT_PATH")
        
        logger.info(f"Creating session for project: {project_name} at {project_path}")
        
        # Create a test session
        session = await session_manager.create_session(project_path)
        logger.info(f"✅ Created Claude session: {session.session_id}")
        
        # Send a test message
        logger.info("Sending test message to Claude...")
        response = await session_manager.send_message(
            session.session_id,
            "Hello! Please respond with 'Claude integration test successful' if you can read this."
        )
        
        if response:
            logger.info(f"✅ Received response from Claude: {response[:100]}...")
        else:
            logger.error("❌ No response from Claude")
            
        # Cleanup
        await session_manager.terminate_session(session.session_id)
        logger.info("✅ Session terminated successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Claude connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_integration(slack_client, session_manager, logger):
    """Test full Slack-Claude integration."""
    logger.info("Testing full Slack-Claude integration...")
    try:
        channel_id = os.getenv("SLACK_CHANNEL")
        project_name = os.getenv("PROJECT_NAME")
        
        # Send message via Slack
        await slack_client.send_message(
            channel=channel_id,
            text="🔄 Starting full integration test..."
        )
        
        # Create Claude session
        project_path = os.getenv("PROJECT_PATH")
        session = await session_manager.create_session(project_path)
        
        # Send a message through the integration
        test_message = "What is 2 + 2? Please answer with just the number."
        
        await slack_client.send_message(
            channel=channel_id,
            text=f"📤 Sending to Claude: {test_message}"
        )
        
        # Get Claude's response
        response = await session_manager.send_message(session.session_id, test_message)
        
        # Send response back to Slack
        await slack_client.send_message(
            channel=channel_id,
            text=f"📥 Claude's response: {response}"
        )
        
        # Cleanup
        await session_manager.terminate_session(session.session_id)
        
        await slack_client.send_message(
            channel=channel_id,
            text="✅ Full integration test completed!"
        )
        
        return True
    except Exception as e:
        logger.error(f"❌ Full integration test failed: {e}")
        await slack_client.send_message(
            channel=channel_id,
            text=f"❌ Integration test failed: {str(e)}"
        )
        return False

async def main():
    """Run all integration tests."""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
    logger.info("Starting Slack-Claude integration tests...")
    
    # Load configuration
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return
    
    config = load_config(str(config_path))
    
    # Initialize components
    slack_client = None
    session_manager = None
    
    try:
        # Test 1: Slack Connection
        logger.info("\n" + "="*50)
        logger.info("TEST 1: SLACK CONNECTION")
        logger.info("="*50)
        
        slack_client = SimpleSlackClient(config.slack)
        await slack_client.connect()
        slack_ok = await test_slack_connection(slack_client, logger)
        
        # Test 2: Claude Connection
        logger.info("\n" + "="*50)
        logger.info("TEST 2: CLAUDE CONNECTION")
        logger.info("="*50)
        
        session_manager = SessionManager(config)
        await session_manager.start()
        claude_ok = await test_claude_connection(session_manager, logger)
        
        # Test 3: Full Integration
        if slack_ok and claude_ok:
            logger.info("\n" + "="*50)
            logger.info("TEST 3: FULL INTEGRATION")
            logger.info("="*50)
            
            await test_full_integration(slack_client, session_manager, logger)
        else:
            logger.warning("Skipping full integration test due to previous failures")
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)
        logger.info(f"Slack Connection: {'✅ PASS' if slack_ok else '❌ FAIL'}")
        logger.info(f"Claude Connection: {'✅ PASS' if claude_ok else '❌ FAIL'}")
        
    except Exception as e:
        logger.error(f"Test suite error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if session_manager:
            await session_manager.stop()
        if slack_client:
            await slack_client.disconnect()
        logger.info("\nTests completed. Check logs for details.")

if __name__ == "__main__":
    asyncio.run(main())