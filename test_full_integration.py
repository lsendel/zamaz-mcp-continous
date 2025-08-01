#!/usr/bin/env python3
"""Test full Slack-Claude integration."""

import os
import asyncio
import subprocess
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
PROJECT_PATH = os.getenv("PROJECT_PATH", ".")


async def test_full_integration():
    """Test the complete Slack-Claude integration."""
    slack = AsyncWebClient(token=SLACK_TOKEN)
    
    print("Testing Full Slack-Claude Integration")
    print("=" * 50)
    
    # Step 1: Send test query to Slack
    test_message = "What is the main purpose of this project?"
    print(f"\n1. Sending test query to Slack: '{test_message}'")
    
    try:
        await slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🧪 **Test Query:** {test_message}"
        )
        print("   ✅ Query sent to Slack")
    except Exception as e:
        print(f"   ❌ Failed to send: {e}")
        return
    
    # Step 2: Process with Claude
    print("\n2. Processing with Claude...")
    try:
        result = subprocess.run(
            [CLAUDE_PATH, '--print', test_message],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            response = result.stdout.strip()
            print("   ✅ Claude responded")
            print(f"   Response preview: {response[:150]}...")
        else:
            print(f"   ❌ Claude error: {result.stderr}")
            return
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return
    
    # Step 3: Send Claude's response back to Slack
    print("\n3. Sending Claude's response to Slack...")
    try:
        await slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🤖 **Claude's Response:**\n\n{response}"
        )
        print("   ✅ Response sent to Slack")
    except Exception as e:
        print(f"   ❌ Failed to send response: {e}")
        return
    
    # Step 4: Test another query
    print("\n4. Testing another query...")
    query2 = "List the main components of the claude_remote_client module"
    
    try:
        # Send query
        await slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🧪 **Test Query 2:** {query2}"
        )
        
        # Get Claude's response
        result = subprocess.run(
            [CLAUDE_PATH, '--print', query2],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Send response
            await slack.chat_postMessage(
                channel=SLACK_CHANNEL,
                text=f"🤖 **Claude's Response:**\n\n{result.stdout.strip()}"
            )
            print("   ✅ Second test completed")
    except Exception as e:
        print(f"   ❌ Second test failed: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Integration test complete!")
    print("Check your Slack channel for the full conversation.")


if __name__ == "__main__":
    asyncio.run(test_full_integration())