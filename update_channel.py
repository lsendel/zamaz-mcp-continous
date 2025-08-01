#!/usr/bin/env python3
"""
Helper script to update the Slack channel ID in the configuration.
"""

import yaml
from pathlib import Path

def update_channel_id():
    """Update the channel ID in the configuration."""
    config_path = Path.home() / ".claude-remote-client" / "config.yaml"
    
    print("📺 Update Slack Channel ID")
    print("=" * 25)
    print()
    
    # Load current config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    current_channel = config.get('slack', {}).get('channel_id', '')
    print(f"Current channel ID: {current_channel}")
    print()
    print("To get the correct channel ID:")
    print("1. Right-click on your Slack channel")
    print("2. Select 'Copy link'")
    print("3. Extract the ID from the URL (starts with 'C')")
    print()
    
    new_channel_id = input("Enter the correct channel ID (C...): ").strip()
    
    while not new_channel_id or not new_channel_id.startswith("C"):
        if not new_channel_id:
            print("❌ Channel ID is required")
        else:
            print("❌ Invalid channel ID. Channel IDs should start with 'C'")
        new_channel_id = input("Enter the correct channel ID (C...): ").strip()
    
    # Update config
    config['slack']['channel_id'] = new_channel_id
    
    # Save updated configuration
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print(f"✅ Channel ID updated to: {new_channel_id}")
    print()
    print("🧪 Test the connection again:")
    print("python test_slack_connection.py")

if __name__ == "__main__":
    update_channel_id()
