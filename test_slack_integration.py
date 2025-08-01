#!/usr/bin/env python3
"""Test Slack integration."""

import os
import asyncio
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


async def test_slack():
    """Test basic Slack functionality."""
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    print("Testing Slack Integration")
    print("=" * 50)
    
    # Test authentication
    try:
        auth = await client.auth_test()
        print(f"✅ Authentication successful!")
        print(f"   Bot User: {auth['user']} (ID: {auth['user_id']})")
        print(f"   Team: {auth['team']}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
    
    # Test sending message
    try:
        result = await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="🧪 Test message from Claude integration test!"
        )
        print(f"\n✅ Message sent successfully!")
        print(f"   Channel: {SLACK_CHANNEL}")
        print(f"   Timestamp: {result['ts']}")
    except SlackApiError as e:
        print(f"❌ Failed to send message: {e.response['error']}")
        if e.response['error'] == 'not_in_channel':
            print("   Bot needs to be invited to the channel")
    
    # Test channel info
    try:
        info = await client.conversations_info(channel=SLACK_CHANNEL)
        print(f"\n✅ Channel info retrieved!")
        print(f"   Name: #{info['channel']['name']}")
    except SlackApiError as e:
        print(f"❌ Failed to get channel info: {e.response['error']}")
        if 'missing_scope' in e.response['error']:
            print(f"   Need scope: {e.response.get('needed', 'unknown')}")
    
    print("\n" + "=" * 50)
    print("Test complete! Check your Slack channel for the test message.")


if __name__ == "__main__":
    asyncio.run(test_slack())