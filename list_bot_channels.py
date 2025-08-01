#!/usr/bin/env python3
"""List all channels the bot can see."""

import os
import asyncio
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")


async def list_channels():
    """List all channels bot can access."""
    client = AsyncWebClient(token=SLACK_TOKEN)
    
    print("📋 CHANNELS BOT CAN ACCESS")
    print("=" * 60)
    
    try:
        # Get all channel types
        result = await client.conversations_list(
            types="public_channel,private_channel",
            limit=200
        )
        
        channels = result['channels']
        print(f"Found {len(channels)} channels:\n")
        
        # Group by type
        public_channels = []
        private_channels = []
        
        for ch in channels:
            if ch.get('is_private', False):
                private_channels.append(ch)
            else:
                public_channels.append(ch)
        
        # Display public channels
        print("PUBLIC CHANNELS:")
        for ch in sorted(public_channels, key=lambda x: x['name']):
            member_status = "✓ Member" if ch.get('is_member', False) else "✗ Not Member"
            print(f"  #{ch['name']:<20} (ID: {ch['id']}) {member_status}")
        
        # Display private channels
        print(f"\nPRIVATE CHANNELS:")
        for ch in sorted(private_channels, key=lambda x: x['name']):
            member_status = "✓ Member" if ch.get('is_member', False) else "✗ Not Member"
            print(f"  🔒 #{ch['name']:<20} (ID: {ch['id']}) {member_status}")
        
        print(f"\n⚠️  Looking for channel: {SLACK_CHANNEL}")
        print("If this channel is not listed above, the bot needs to be invited to it!")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(list_channels())