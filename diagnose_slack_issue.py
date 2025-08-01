#!/usr/bin/env python3
"""
Diagnose Slack channel access issues.
"""

import asyncio
import os
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

# Load environment
load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


async def diagnose():
    """Run diagnostics on Slack configuration."""
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    print("🔍 SLACK DIAGNOSTICS")
    print("=" * 50)
    
    # 1. Check authentication
    try:
        auth = await client.auth_test()
        print(f"✅ Authentication successful")
        print(f"   Bot User: {auth['user']} (ID: {auth['user_id']})")
        print(f"   Team: {auth['team']}")
        bot_id = auth['user_id']
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
    
    # 2. List all channels the bot can see
    print(f"\n📋 Checking channel access...")
    try:
        # Try public channels
        public_result = await client.conversations_list(types="public_channel")
        public_channels = {ch['id']: ch['name'] for ch in public_result['channels']}
        
        # Try private channels
        private_result = await client.conversations_list(types="private_channel")
        private_channels = {ch['id']: ch['name'] for ch in private_result['channels']}
        
        print(f"\nPublic channels bot can see: {len(public_channels)}")
        print(f"Private channels bot can see: {len(private_channels)}")
        
        # Check if our channel is in either list
        if SLACK_CHANNEL in public_channels:
            print(f"\n✅ Channel {SLACK_CHANNEL} is a PUBLIC channel: #{public_channels[SLACK_CHANNEL]}")
            channel_type = "public"
        elif SLACK_CHANNEL in private_channels:
            print(f"\n✅ Channel {SLACK_CHANNEL} is a PRIVATE channel: #{private_channels[SLACK_CHANNEL]}")
            channel_type = "private"
        else:
            print(f"\n❌ Channel {SLACK_CHANNEL} not found in bot's channel list!")
            print("   The bot might not be invited to this channel.")
            channel_type = "unknown"
            
    except Exception as e:
        print(f"❌ Error listing channels: {e}")
        channel_type = "error"
    
    # 3. Try to get channel info directly
    print(f"\n🔍 Getting channel info for {SLACK_CHANNEL}...")
    try:
        info = await client.conversations_info(channel=SLACK_CHANNEL)
        channel = info['channel']
        print(f"✅ Channel found!")
        print(f"   Name: #{channel.get('name', 'N/A')}")
        print(f"   Type: {'Private' if channel.get('is_private') else 'Public'}")
        print(f"   Is Group: {channel.get('is_group', False)}")
        print(f"   Is Channel: {channel.get('is_channel', False)}")
        print(f"   Is IM: {channel.get('is_im', False)}")
        print(f"   Is MPIM: {channel.get('is_mpim', False)}")
        
        # Check if bot is member
        if channel.get('is_member') is not None:
            print(f"   Bot is member: {channel.get('is_member')}")
            
    except SlackApiError as e:
        if e.response['error'] == 'channel_not_found':
            print(f"❌ Channel not found - bot may not be invited")
        else:
            print(f"❌ Error getting channel info: {e.response['error']}")
    
    # 4. Try different history methods
    print(f"\n🔍 Testing history access methods...")
    
    # Method 1: conversations.history (standard)
    try:
        result = await client.conversations_history(channel=SLACK_CHANNEL, limit=1)
        print(f"✅ conversations.history: SUCCESS")
    except SlackApiError as e:
        print(f"❌ conversations.history: {e.response['error']}")
    
    # Method 2: conversations.view (for some channel types)
    try:
        result = await client.conversations_replies(
            channel=SLACK_CHANNEL,
            ts="1"  # Dummy timestamp
        )
        print(f"✅ conversations.replies: Can access")
    except SlackApiError as e:
        if 'thread_not_found' in str(e):
            print(f"✅ conversations.replies: Can access (no threads)")
        else:
            print(f"❌ conversations.replies: {e.response['error']}")
    
    # 5. Check bot permissions
    print(f"\n🔍 Checking bot scopes...")
    try:
        # Get the bot's token info
        scopes_result = await client.auth_test()
        # Note: auth.test doesn't return scopes directly, but we can infer from errors
        print("✅ Bot has valid authentication")
        
        # Try to send a test message
        try:
            await client.chat_postMessage(
                channel=SLACK_CHANNEL,
                text="🔍 Diagnostic test message"
            )
            print("✅ Can send messages to channel")
        except SlackApiError as e:
            print(f"❌ Cannot send messages: {e.response['error']}")
            
    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
    
    # 6. Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if channel_type == "unknown":
        print("1. Invite the bot to your channel:")
        print("   - In Slack, go to the channel")
        print("   - Type: /invite @clbot")
    elif channel_type == "private":
        print("1. Make sure bot has groups:history scope")
        print("2. Try re-inviting the bot to the channel")
    elif channel_type == "public":
        print("1. The bot should work with channels:history scope")
        print("2. Try re-inviting the bot if issues persist")
    
    print("\n✅ Diagnostics complete!")


if __name__ == "__main__":
    asyncio.run(diagnose())