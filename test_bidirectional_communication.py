#!/usr/bin/env python3
"""
Test bidirectional communication between Slack and Claude.
This sends messages to Slack and invokes Claude directly to demonstrate the flow.
"""

import asyncio
import os
import subprocess
from datetime import datetime
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


async def send_to_slack(client: AsyncWebClient, message: str) -> bool:
    """Send a message to Slack."""
    try:
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
        return True
    except SlackApiError as e:
        print(f"Error sending to Slack: {e}")
        return False


def send_to_claude(message: str) -> str:
    """Send message to Claude and get response."""
    try:
        # Run Claude in print mode
        result = subprocess.run(
            [CLAUDE_PATH, '--print', message],
            cwd=PROJECT_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Claude error: {result.stderr.strip()}"
            
    except subprocess.TimeoutExpired:
        return "Claude timed out"
    except Exception as e:
        return f"Error: {str(e)}"


async def demonstrate_bidirectional_flow():
    """Demonstrate the bidirectional communication flow."""
    print("=== SLACK-CLAUDE BIDIRECTIONAL COMMUNICATION TEST ===\n")
    
    # Initialize Slack client
    slack = AsyncWebClient(token=SLACK_TOKEN)
    
    # Test Slack connection
    try:
        auth = await slack.auth_test()
        print(f"✅ Connected to Slack as {auth['user']}")
    except Exception as e:
        print(f"❌ Slack connection failed: {e}")
        return
    
    # Test scenarios
    test_conversations = [
        {
            "user": "Hello Claude, are you there?",
            "expected": "greeting"
        },
        {
            "user": "What files are in this project?",
            "expected": "file listing"
        },
        {
            "user": "Can you explain what the zamaz-mcp project does?",
            "expected": "project explanation"
        }
    ]
    
    print("\n--- Starting Bidirectional Communication Test ---\n")
    
    # Send initial message
    await send_to_slack(slack, "🚀 **Bidirectional Communication Test Starting**")
    
    for i, convo in enumerate(test_conversations, 1):
        print(f"\n📝 Test {i}: {convo['expected']}")
        user_msg = convo["user"]
        
        # 1. User -> Slack
        print(f"1️⃣ User message: {user_msg}")
        await send_to_slack(slack, f"👤 **User**: {user_msg}")
        
        # 2. Slack -> Claude (simulated by direct call)
        print(f"2️⃣ Routing to Claude...")
        claude_response = send_to_claude(user_msg)
        
        # 3. Claude -> Slack
        print(f"3️⃣ Claude response: {claude_response[:100]}...")
        await send_to_slack(slack, f"🤖 **Claude**: {claude_response}")
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Final summary
    summary = f"""
✅ **Bidirectional Communication Test Complete!**

**Flow Demonstrated:**
1. User sends message in Slack
2. Bot reads message and routes to Claude
3. Claude processes in project context ({PROJECT_PATH})
4. Claude's response is sent back to Slack

**Next Steps:**
- Add `groups:history` scope to read private channel messages
- Or use a public channel (starts with 'C' but not private)
- Or implement Slack Events API for real-time messages
"""
    
    await send_to_slack(slack, summary)
    print("\n✅ Test complete! Check your Slack channel for the conversation.")


async def main():
    """Run the demonstration."""
    await demonstrate_bidirectional_flow()


if __name__ == "__main__":
    asyncio.run(main())