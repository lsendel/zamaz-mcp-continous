#!/usr/bin/env python3
"""
Helper script to add the Slack signing secret to the configuration.
"""

import yaml
from pathlib import Path

def update_signing_secret():
    """Add the signing secret to the configuration."""
    config_path = Path.home() / ".claude-remote-client" / "config.yaml"
    
    print("🔐 Add Slack Signing Secret")
    print("=" * 25)
    print()
    
    # Load current config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    current_secret = config.get('slack', {}).get('signing_secret', '')
    if current_secret:
        print(f"Current signing secret: {current_secret[:10]}...")
        print()
        update = input("Update the existing signing secret? (y/N): ").strip().lower()
        if update != 'y':
            print("No changes made.")
            return
    
    print("To get your signing secret:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your app")
    print("3. Go to 'Basic Information'")
    print("4. Scroll to 'App Credentials'")
    print("5. Click 'Show' next to 'Signing Secret'")
    print()
    
    signing_secret = input("Enter your Slack Signing Secret: ").strip()
    
    while not signing_secret:
        print("❌ Signing secret is required")
        signing_secret = input("Enter your Slack Signing Secret: ").strip()
    
    # Update config
    if 'slack' not in config:
        config['slack'] = {}
    config['slack']['signing_secret'] = signing_secret
    
    # Save updated configuration
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print(f"✅ Signing secret added!")
    print()
    print("🧪 Test the connection:")
    print("python test_slack_connection.py")

if __name__ == "__main__":
    update_signing_secret()
