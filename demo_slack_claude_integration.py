#!/usr/bin/env python3
"""
Demo of Slack-Claude integration architecture.
This simulates the integration without requiring valid Slack credentials.
"""

import asyncio
import subprocess
import json
from datetime import datetime
from typing import Dict, Any, Optional


class MockSlackClient:
    """Mock Slack client for demonstration."""
    
    def __init__(self):
        self.messages = []
    
    async def send_message(self, channel: str, text: str):
        """Simulate sending a message."""
        msg = {
            "ts": datetime.now().isoformat(),
            "channel": channel,
            "text": text
        }
        self.messages.append(msg)
        print(f"[SLACK] {text}")
        return msg
    
    async def get_messages(self, channel: str, limit: int = 10):
        """Simulate getting messages."""
        return self.messages[-limit:]


class ClaudeIntegration:
    """Claude CLI integration."""
    
    def __init__(self, claude_path: str, project_path: str):
        self.claude_path = claude_path
        self.project_path = project_path
        self.process = None
    
    def send_to_claude(self, message: str) -> str:
        """Send message to Claude using a simple echo for demo."""
        # In real implementation, this would:
        # 1. Start claude process with: subprocess.Popen([self.claude_path, ...])
        # 2. Send message via stdin
        # 3. Read response from stdout
        
        # For demo, we'll simulate responses
        responses = {
            "hello": "Hello! I'm Claude, ready to help with your coding tasks.",
            "what is 2 + 2?": "2 + 2 = 4",
            "help": "I can help you with coding, debugging, and answering questions about your project.",
            "status": "I'm currently running and ready to assist."
        }
        
        lower_msg = message.lower().strip()
        return responses.get(lower_msg, f"I received your message: '{message}'. How can I help you with coding today?")


class SlackClaudeBot:
    """Main bot that connects Slack and Claude."""
    
    def __init__(self, slack_client: MockSlackClient, claude: ClaudeIntegration):
        self.slack = slack_client
        self.claude = claude
        self.channel = "C098WUY87L1"
        self.active = False
        self.processed_messages = set()
    
    async def start(self):
        """Start the bot."""
        self.active = True
        await self.slack.send_message(
            self.channel,
            "🤖 Slack-Claude Bot Started! Type 'hello' to begin."
        )
        
        # Start message polling
        await self.poll_messages()
    
    async def poll_messages(self):
        """Poll for new messages."""
        print("\n[BOT] Starting message polling...")
        
        # Simulate some user messages
        test_messages = [
            ("user123", "hello"),
            ("user123", "what is 2 + 2?"),
            ("user123", "help"),
            ("user123", "Can you explain async/await in Python?"),
        ]
        
        for user, text in test_messages:
            await asyncio.sleep(1)  # Simulate delay
            
            # Simulate user message
            print(f"\n[USER] {text}")
            
            # Process the message
            await self.process_message(user, text)
    
    async def process_message(self, user: str, text: str):
        """Process a user message."""
        # Send to Claude
        print(f"[BOT] Routing to Claude...")
        response = self.claude.send_to_claude(text)
        
        # Send Claude's response back to Slack
        await self.slack.send_message(
            self.channel,
            f"Claude: {response}"
        )


async def main():
    """Run the demo."""
    print("="*60)
    print("SLACK-CLAUDE INTEGRATION DEMO")
    print("="*60)
    print("\nThis demo shows how messages flow between Slack and Claude:")
    print("1. User sends message in Slack")
    print("2. Bot polls/receives the message")
    print("3. Bot sends message to Claude CLI")
    print("4. Claude processes and responds")
    print("5. Bot sends Claude's response back to Slack")
    print("\n" + "="*60 + "\n")
    
    # Create components
    slack = MockSlackClient()
    claude = ClaudeIntegration(
        claude_path="/Users/lsendel/.npm-global/bin/claude",
        project_path="/Users/lsendel/IdeaProjects/zamaz-mcp-continous"
    )
    bot = SlackClaudeBot(slack, claude)
    
    # Start the bot
    await bot.start()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nIn a real implementation with valid Slack credentials:")
    print("- The bot would use slack_sdk to connect to your workspace")
    print("- It would listen for real messages using Events API or RTM")
    print("- Claude would be invoked via subprocess for actual AI responses")
    print("- Responses would appear in your actual Slack channel")
    print("\nTo fix the current issue:")
    print("1. Generate a new Slack bot token at https://api.slack.com/apps")
    print("2. Ensure the bot has these scopes: chat:write, channels:history, channels:read")
    print("3. Install the bot to your workspace")
    print("4. Update the SLACK_BOT_TOKEN in .env with the new token")


if __name__ == "__main__":
    asyncio.run(main())