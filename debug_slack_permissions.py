#!/usr/bin/env python3
"""Debug Slack permissions and channel access."""

import os
import asyncio
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


async def debug_permissions():
    """Debug bot permissions and channel access."""
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    print("🔍 SLACK PERMISSIONS DEBUGGER")
    print("=" * 60)
    
    # 1. Get auth info
    try:
        auth = await client.auth_test()
        print(f"✅ Authenticated as: {auth['user']} (ID: {auth['user_id']})")
        print(f"   Team: {auth['team']} (ID: {auth['team_id']})")
        print(f"   Bot ID: {auth.get('bot_id', 'N/A')}")
    except Exception as e:
        print(f"❌ Auth test failed: {e}")
        return
    
    # 2. Get bot info with scopes
    print("\n📋 Bot OAuth Scopes:")
    try:
        # Try to get bot info
        bot_info = await client.bots_info(bot=auth.get('bot_id', auth['user_id']))
        print(f"   Bot name: {bot_info['bot']['name']}")
    except Exception as e:
        print(f"   Could not get bot info: {e}")
    
    # 3. Test channel access methods
    print(f"\n🔍 Testing channel access for: {SLACK_CHANNEL}")
    
    # Method 1: conversations.info
    print("\n1. Testing conversations.info...")
    try:
        info = await client.conversations_info(channel=SLACK_CHANNEL)
        channel_name = info['channel']['name']
        is_member = info['channel']['is_member']
        print(f"   ✅ Channel name: #{channel_name}")
        print(f"   Is bot member: {is_member}")
        
        # Check if it's a private channel
        is_private = info['channel'].get('is_private', False)
        is_group = info['channel'].get('is_group', False)
        print(f"   Is private: {is_private}")
        print(f"   Is group: {is_group}")
    except SlackApiError as e:
        print(f"   ❌ Error: {e.response['error']}")
        if 'needed' in e.response:
            print(f"   Needed scope: {e.response['needed']}")
            print(f"   Provided scopes: {e.response.get('provided', 'unknown')}")
    
    # Method 2: conversations.list
    print("\n2. Testing conversations.list...")
    try:
        # List all channels bot can see
        result = await client.conversations_list(
            types="public_channel,private_channel",
            limit=100
        )
        
        channels = result['channels']
        print(f"   ✅ Bot can see {len(channels)} channels")
        
        # Find our channel
        our_channel = None
        for ch in channels:
            if ch['id'] == SLACK_CHANNEL:
                our_channel = ch
                break
        
        if our_channel:
            print(f"   ✅ Found channel: #{our_channel['name']}")
            print(f"      Is member: {our_channel.get('is_member', False)}")
        else:
            print(f"   ❌ Channel {SLACK_CHANNEL} not in list")
    except SlackApiError as e:
        print(f"   ❌ Error: {e.response['error']}")
    
    # Method 3: conversations.members
    print("\n3. Testing conversations.members...")
    try:
        members = await client.conversations_members(channel=SLACK_CHANNEL)
        print(f"   ✅ Got {len(members['members'])} members")
        if auth['user_id'] in members['members']:
            print(f"   ✅ Bot is a member")
        else:
            print(f"   ❌ Bot is NOT a member")
    except SlackApiError as e:
        print(f"   ❌ Error: {e.response['error']}")
    
    # Method 4: Test history access
    print("\n4. Testing conversations.history...")
    try:
        history = await client.conversations_history(
            channel=SLACK_CHANNEL,
            limit=1
        )
        print(f"   ✅ Can read history! Got {len(history['messages'])} messages")
    except SlackApiError as e:
        print(f"   ❌ Error: {e.response['error']}")
        if 'needed' in e.response:
            print(f"   Needed scope: {e.response['needed']}")
    
    # Method 5: Test joining channel
    print("\n5. Testing conversations.join...")
    try:
        result = await client.conversations_join(channel=SLACK_CHANNEL)
        print(f"   ✅ Successfully joined/already in channel")
    except SlackApiError as e:
        print(f"   ❌ Error: {e.response['error']}")
    
    # 6. List bot's actual permissions
    print("\n📋 Testing specific permissions:")
    test_permissions = {
        'channels:read': 'List public channels',
        'groups:read': 'List private channels',
        'channels:history': 'Read public channel history',
        'groups:history': 'Read private channel history',
        'chat:write': 'Send messages',
        'im:read': 'List DMs',
        'im:history': 'Read DM history'
    }
    
    # We'll test by trying operations that require specific scopes
    print("\n   Testing by operation:")
    
    # Test public channels
    try:
        await client.conversations_list(types="public_channel", limit=1)
        print("   ✅ Can list public channels (channels:read)")
    except:
        print("   ❌ Cannot list public channels")
    
    # Test private channels
    try:
        await client.conversations_list(types="private_channel", limit=1)
        print("   ✅ Can list private channels (groups:read)")
    except:
        print("   ❌ Cannot list private channels")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(debug_permissions())