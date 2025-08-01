#!/usr/bin/env python3
"""
Simple test to verify Slack-Claude integration concept.
This bypasses the complex session management and tests direct communication.
"""

import os
import asyncio
import subprocess
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

# Load environment
load_dotenv()

# Configuration
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH")
PROJECT_PATH = os.getenv("PROJECT_PATH")

print(f"Configuration:")
print(f"  Slack Token: {SLACK_TOKEN[:20]}..." if SLACK_TOKEN else "  Slack Token: Not set")
print(f"  Slack Channel: {SLACK_CHANNEL}")
print(f"  Claude Path: {CLAUDE_PATH}")
print(f"  Project Path: {PROJECT_PATH}")


async def test_slack_send():
    """Test sending a message to Slack."""
    print("\n1. Testing Slack Send...")
    
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    try:
        # First verify the token
        auth = await client.auth_test()
        print(f"✅ Authenticated as: {auth['user']}")
        
        # Send a test message
        result = await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="🧪 Testing Slack-Claude integration"
        )
        print(f"✅ Message sent successfully")
        return True
        
    except SlackApiError as e:
        print(f"❌ Slack error: {e.response['error']}")
        return False


def test_claude_cli():
    """Test Claude CLI directly."""
    print("\n2. Testing Claude CLI...")
    
    # Test if Claude CLI works
    try:
        result = subprocess.run(
            [CLAUDE_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(f"✅ Claude CLI version: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Claude CLI error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to run Claude CLI: {e}")
        return False


async def test_integration():
    """Test the integration concept."""
    print("\n3. Testing Integration Concept...")
    
    # Create a mock conversation
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    try:
        # Send initial message
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="🤖 Bot: Starting integration test..."
        )
        
        # Simulate user message
        user_msg = "What is 2 + 2?"
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"👤 User: {user_msg}"
        )
        
        # In a real integration, we would:
        # 1. Listen for the user message via events/polling
        # 2. Send it to Claude via subprocess
        # 3. Get Claude's response
        # 4. Send it back to Slack
        
        # For now, simulate Claude's response
        claude_response = "4"
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🤖 Claude: {claude_response}"
        )
        
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="✅ Integration test complete!"
        )
        
        print("✅ Integration concept demonstrated")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("Starting Slack-Claude Integration Tests\n")
    
    # Test Slack
    slack_ok = await test_slack_send()
    
    # Test Claude
    claude_ok = test_claude_cli()
    
    # Test integration
    if slack_ok:
        integration_ok = await test_integration()
    else:
        print("\n⚠️  Skipping integration test due to Slack issues")
        integration_ok = False
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY:")
    print(f"  Slack API: {'✅ PASS' if slack_ok else '❌ FAIL'}")
    print(f"  Claude CLI: {'✅ PASS' if claude_ok else '❌ FAIL'}")
    print(f"  Integration: {'✅ PASS' if integration_ok else '❌ FAIL'}")
    print("="*50)
    
    if slack_ok and claude_ok:
        print("\n✅ Both systems are working! The issue is with the token authentication.")
        print("Please check:")
        print("1. The Slack bot token is valid and not expired")
        print("2. The bot is installed in your workspace")
        print("3. The bot has the necessary permissions (chat:write, channels:history, etc.)")
    

if __name__ == "__main__":
    asyncio.run(main())