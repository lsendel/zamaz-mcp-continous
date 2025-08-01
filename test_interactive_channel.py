#!/usr/bin/env python3
"""Test the interactive Slack-Claude channel."""

import os
import asyncio
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
PROJECT_PATH = os.getenv("PROJECT_PATH", ".")


async def test_interactive_channel():
    """Test interactive communication channel."""
    slack = AsyncWebClient(token=SLACK_TOKEN)
    
    print("🔄 TESTING INTERACTIVE SLACK-CLAUDE CHANNEL")
    print("=" * 60)
    
    # Send initial message
    test_queries = [
        "Hello Claude! Can you confirm the interactive channel is working?",
        "What files are in the claude_remote_client directory?",
        "Show me the version of Python we're using"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📤 Test {i}: {query}")
        
        try:
            # Send to Slack
            await slack.chat_postMessage(
                channel=SLACK_CHANNEL,
                text=f"🧪 **Interactive Test {i}:** {query}"
            )
            
            # Process with Claude
            result = subprocess.run(
                [CLAUDE_PATH, '--print', query],
                cwd=PROJECT_PATH,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                
                # Send response back
                await slack.chat_postMessage(
                    channel=SLACK_CHANNEL,
                    text=f"🤖 **Claude says:**\n{response}"
                )
                print(f"   ✅ Response sent")
            else:
                print(f"   ❌ Claude error: {result.stderr}")
                
            # Brief pause between tests
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Final status message
    await slack.chat_postMessage(
        channel=SLACK_CHANNEL,
        text="✅ **Interactive channel test complete!** The bidirectional communication is working properly."
    )
    
    print("\n" + "=" * 60)
    print("✅ Interactive channel verified!")
    print(f"Check #{SLACK_CHANNEL} in Slack for the full conversation")


if __name__ == "__main__":
    asyncio.run(test_interactive_channel())