#!/usr/bin/env python3
"""
Test script to verify Slack connection and configuration.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from claude_remote_client.config import load_config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


async def test_slack_connection():
    """Test the Slack connection with current configuration."""
    print("🔍 Testing Slack Connection")
    print("=" * 30)
    
    try:
        # Load configuration
        config = load_config()
        print("✅ Configuration loaded successfully")
        
        # Get Slack credentials
        slack_config = config.slack
        bot_token = slack_config.bot_token
        channel_id = slack_config.channel_id
        
        print(f"📱 Bot Token: {bot_token[:20]}...")
        print(f"📺 Channel ID: {channel_id}")
        print()
        
        # Initialize Slack client
        client = WebClient(token=bot_token)
        
        # Test 1: Auth test
        print("🔐 Testing authentication...")
        try:
            auth_response = client.auth_test()
            print(f"✅ Authentication successful!")
            print(f"   Bot User ID: {auth_response['user_id']}")
            print(f"   Bot Name: {auth_response['user']}")
            print(f"   Team: {auth_response['team']}")
        except SlackApiError as e:
            print(f"❌ Authentication failed: {e.response['error']}")
            return False
        
        print()
        
        # Test 2: Channel access
        print("📺 Testing channel access...")
        try:
            # Try to get channel info
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info['channel']['name']
            print(f"✅ Channel access successful!")
            print(f"   Channel Name: #{channel_name}")
            print(f"   Channel ID: {channel_id}")
        except SlackApiError as e:
            print(f"❌ Channel access failed: {e.response['error']}")
            if e.response['error'] == 'channel_not_found':
                print("   💡 Make sure the bot is added to the channel")
            return False
        
        print()
        
        # Test 3: Send a test message (optional)
        send_test = input("🧪 Send a test message to verify posting? (y/N): ").strip().lower()
        if send_test == 'y':
            try:
                test_message = "🤖 Claude Remote Client connection test - everything is working!"
                response = client.chat_postMessage(
                    channel=channel_id,
                    text=test_message
                )
                print("✅ Test message sent successfully!")
                print(f"   Message timestamp: {response['ts']}")
            except SlackApiError as e:
                print(f"❌ Failed to send test message: {e.response['error']}")
                return False
        
        print()
        print("🎉 All tests passed! Your Slack configuration is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_slack_connection())
    if not success:
        print()
        print("🔧 Troubleshooting tips:")
        print("1. Verify your bot token is correct (starts with 'xoxb-')")
        print("2. Make sure the bot is added to the target channel")
        print("3. Check that the channel ID is correct (starts with 'C')")
        print("4. Ensure the bot has proper permissions (chat:write, channels:read)")
        sys.exit(1)
    else:
        print()
        print("🚀 Ready to start Claude Remote Client!")
        print("Run: python -m claude_remote_client.cli")
