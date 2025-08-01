#!/usr/bin/env python3
"""
Interactive Slack-Claude bridge using a command-based approach.
This works around the history reading limitation by using commands.
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

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH")
PROJECT_PATH = os.getenv("PROJECT_PATH")


class InteractiveSlackClaude:
    """Interactive bridge that responds to commands."""
    
    def __init__(self):
        self.slack = AsyncWebClient(token=SLACK_TOKEN)
        self.running = False
        
    async def send_to_claude(self, message: str) -> str:
        """Send message to Claude and get response."""
        try:
            # Run Claude in print mode
            process = await asyncio.create_subprocess_exec(
                CLAUDE_PATH,
                '--print',
                message,
                cwd=PROJECT_PATH,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                return f"Claude error: {stderr.decode().strip()}"
                
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def process_command(self, command: str):
        """Process a command and send response to Slack."""
        # Send acknowledgment
        await self.slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🔄 Processing: {command}"
        )
        
        # Send to Claude
        response = await self.send_to_claude(command)
        
        # Send response back
        await self.slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"🤖 **Claude says:**\n{response}"
        )
    
    async def run_interactive_mode(self):
        """Run in interactive mode."""
        print("🚀 INTERACTIVE SLACK-CLAUDE BRIDGE")
        print("=" * 50)
        
        # Test authentication
        try:
            auth = await self.slack.auth_test()
            print(f"✅ Connected as {auth['user']}")
        except Exception as e:
            print(f"❌ Slack error: {e}")
            return
        
        # Send startup message
        startup_msg = """🤖 **Claude Interactive Mode Started!**

Since I can't read channel history, please use one of these methods:

**Method 1: Type commands here**
Type your questions below and press Enter to send to Claude.

**Method 2: Use Slack commands**
In Slack, mention me or use a command prefix like:
`@clbot What files are in this project?`
`!claude Explain the session manager`

Type 'quit' to exit."""
        
        await self.slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=startup_msg
        )
        
        print("\n📝 Type your messages below (or 'quit' to exit):")
        print("-" * 50)
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() == 'quit':
                    print("👋 Exiting...")
                    await self.slack.chat_postMessage(
                        channel=SLACK_CHANNEL,
                        text="👋 Claude Interactive Mode stopped."
                    )
                    break
                
                if not user_input:
                    continue
                
                # Process the command
                await self.process_command(user_input)
                print("✅ Sent to Slack")
                
            except KeyboardInterrupt:
                print("\n👋 Interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def demonstrate_flow(self):
        """Demonstrate the working flow."""
        print("\n🎯 DEMONSTRATING BIDIRECTIONAL FLOW")
        print("=" * 50)
        
        demo_messages = [
            "Hello Claude, can you see this project?",
            "List the main Python files in this project",
            "What does the session_manager.py do?"
        ]
        
        for msg in demo_messages:
            print(f"\n📤 Sending: {msg}")
            await self.process_command(msg)
            await asyncio.sleep(3)  # Pause between messages
        
        print("\n✅ Demo complete! Check Slack for the conversation.")


async def main():
    """Main entry point."""
    bridge = InteractiveSlackClaude()
    
    print("Choose mode:")
    print("1. Interactive mode (type messages here)")
    print("2. Demo mode (automatic demonstration)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "2":
        await bridge.demonstrate_flow()
    else:
        await bridge.run_interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())