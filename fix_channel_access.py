#!/usr/bin/env python3
"""Help fix channel access issues."""

import os
import asyncio
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


async def fix_channel_access():
    """Guide user to fix channel access."""
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    print("🔧 FIXING CHANNEL ACCESS")
    print("=" * 60)
    
    # Get bot info
    try:
        auth = await client.auth_test()
        bot_name = auth['user']
        bot_id = auth['user_id']
        print(f"Bot: @{bot_name} (ID: {bot_id})")
    except Exception as e:
        print(f"Error: {e}")
        return
    
    print(f"\n❌ Bot cannot access channel: {SLACK_CHANNEL}")
    print("\n📋 SOLUTIONS:\n")
    
    print("1. INVITE BOT TO EXISTING CHANNEL:")
    print(f"   In Slack, go to any channel and type:")
    print(f"   /invite @{bot_name}")
    print(f"   Or mention the bot in the channel: @{bot_name}")
    
    print("\n2. USE A DIFFERENT CHANNEL:")
    print("   Update SLACK_CHANNEL in your .env to one of these:")
    
    # List available channels
    try:
        result = await client.conversations_list(
            types="public_channel,private_channel",
            limit=200
        )
        
        member_channels = [ch for ch in result['channels'] if ch.get('is_member', False)]
        
        if member_channels:
            print("\n   Channels where bot is already a member:")
            for ch in member_channels:
                print(f"   - {ch['id']} (#{ch['name']})")
        else:
            print("   Bot is not a member of any channels yet!")
    except:
        pass
    
    print("\n3. CREATE A NEW CHANNEL:")
    print("   Create a new channel in Slack and invite the bot")
    
    print("\n4. TEST A PUBLIC CHANNEL:")
    print("   Try joining #general:")
    
    try:
        result = await client.conversations_join(channel="C02TCD1SN")  # general channel
        print("   ✅ Bot joined #general successfully!")
        print("   Update your .env: SLACK_CHANNEL=C02TCD1SN")
    except Exception as e:
        print(f"   ❌ Could not join #general: {e}")
    
    print("\n" + "=" * 60)
    print("After fixing, run: python3 test_full_integration.py")


if __name__ == "__main__":
    asyncio.run(fix_channel_access())