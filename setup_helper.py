#!/usr/bin/env python3
"""
Setup helper script for Claude Remote Client.
This script helps you configure the application with proper Slack credentials.
"""

import os
import yaml
from pathlib import Path

def update_config():
    """Update the configuration file with user-provided values."""
    config_path = Path.home() / ".claude-remote-client" / "config.yaml"
    
    print("🔧 Claude Remote Client Configuration Helper")
    print("=" * 50)
    print()
    
    if not config_path.exists():
        print(f"❌ Configuration file not found at {config_path}")
        print("Please run the setup wizard first:")
        print("python -m claude_remote_client.cli --setup")
        return
    
    # Load existing config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print("📱 Slack Configuration")
    print("-" * 20)
    print("To get these values:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Create a new app or select existing one")
    print("3. Go to 'OAuth & Permissions' for the bot token")
    print("4. Right-click your Slack channel -> Copy link for channel ID")
    print()
    
    # Get Slack bot token
    current_token = config.get('slack', {}).get('bot_token', '')
    if current_token and not current_token.startswith('REPLACE_'):
        print(f"Current bot token: {current_token[:20]}...")
        use_current = input("Keep current bot token? (y/N): ").strip().lower()
        if use_current != 'y':
            current_token = ''
    else:
        current_token = ''
    
    if not current_token:
        bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
        while not bot_token or not bot_token.startswith("xoxb-"):
            if not bot_token:
                print("❌ Bot token is required")
            else:
                print("❌ Invalid bot token. Bot tokens should start with 'xoxb-'")
            bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
        config['slack']['bot_token'] = bot_token
    
    # Get Slack channel ID
    current_channel = config.get('slack', {}).get('channel_id', '')
    if current_channel and not current_channel.startswith('REPLACE_'):
        print(f"Current channel ID: {current_channel}")
        use_current = input("Keep current channel ID? (y/N): ").strip().lower()
        if use_current != 'y':
            current_channel = ''
    else:
        current_channel = ''
    
    if not current_channel:
        channel_id = input("Enter your Slack Channel ID (C...): ").strip()
        while not channel_id or not channel_id.startswith("C"):
            if not channel_id:
                print("❌ Channel ID is required")
            else:
                print("❌ Invalid channel ID. Channel IDs should start with 'C'")
            channel_id = input("Enter your Slack Channel ID (C...): ").strip()
        config['slack']['channel_id'] = channel_id
    
    # Optional signing secret
    signing_secret = input("Enter your Slack Signing Secret (optional, press Enter to skip): ").strip()
    if signing_secret:
        config['slack']['signing_secret'] = signing_secret
    
    print()
    
    # Project configuration
    print("📁 Project Configuration")
    print("-" * 25)
    print("Current projects:")
    for i, project in enumerate(config.get('projects', []), 1):
        print(f"  {i}. {project['name']} -> {project['path']}")
    
    if not config.get('projects'):
        print("  (No projects configured)")
    
    print()
    add_projects = input("Add more projects? (y/N): ").strip().lower()
    
    if add_projects == 'y':
        projects = config.get('projects', [])
        
        while True:
            project_name = input("Enter project name (or press Enter to finish): ").strip()
            if not project_name:
                break
            
            # Check for duplicate names
            if any(p['name'] == project_name for p in projects):
                print(f"❌ Project '{project_name}' already exists")
                continue
            
            project_path = input(f"Enter path for '{project_name}': ").strip()
            if not project_path:
                print("❌ Project path is required")
                continue
            
            expanded_path = os.path.expanduser(project_path)
            if not os.path.exists(expanded_path):
                print(f"⚠️  Warning: Path '{expanded_path}' does not exist")
                continue_anyway = input("Continue anyway? (y/N): ").strip().lower()
                if continue_anyway != 'y':
                    continue
            
            project_desc = input(f"Enter description for '{project_name}' (optional): ").strip()
            
            projects.append({
                'name': project_name,
                'path': project_path,
                'description': project_desc or f"Development project: {project_name}"
            })
            
            print(f"✅ Added project '{project_name}'")
            print()
        
        config['projects'] = projects
    
    # Save updated configuration
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        print(f"✅ Configuration updated successfully!")
        print(f"📁 Config file: {config_path}")
        print()
        print("🚀 Next steps:")
        print("1. Test your configuration:")
        print("   python -m claude_remote_client.cli --validate")
        print()
        print("2. Start the bot:")
        print("   python -m claude_remote_client.cli")
        print()
        
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")

if __name__ == "__main__":
    update_config()
