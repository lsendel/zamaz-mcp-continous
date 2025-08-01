#!/usr/bin/env python3
"""
Helper script to update the Slack bot token in the configuration.
"""

import yaml
from pathlib import Path

def update_bot_token():
    """Update the bot token in the configuration."""
    config_path = Path.home() / ".claude-remote-client" / "config.yaml"
    
    print("🔐 Update Slack Bot Token")
    print("=" * 22)
    print()
    
    # Load current config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    current_token = config.get('slack', {}).get('bot_token', '')
    print(f"Current token: {current_token[:20]}...")
    print()
    print("After adding permissions and reinstalling your Slack app:")
    print("1. Go to OAuth & Permissions in your Slack app settings")
    print("2. Copy the 'Bot User OAuth Token'")
    print("3. Paste it below")
    print()
    
    new_token = input("Enter the new bot token (xoxb-...): ").strip()
    
    while not new_token or not new_token.startswith("xoxb-"):
        if not new_token:
            print("❌ Bot token is required")
        else:
            print("❌ Invalid bot token. Bot tokens should start with 'xoxb-'")
        new_token = input("Enter the new bot token (xoxb-...): ").strip()
    
    # Update config
    config['slack']['bot_token'] = new_token
    
    # Save updated configuration
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print(f"✅ Bot token updated!")
    print()
    print("🧪 Test the connection again:")
    print("python test_slack_connection.py")

if __name__ == "__main__":
    update_bot_token()
