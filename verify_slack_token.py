#!/usr/bin/env python3
"""Verify Slack token and show what's configured."""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Get token
token = os.getenv("SLACK_BOT_TOKEN")
channel = os.getenv("SLACK_CHANNEL")

print("Current Slack Configuration:")
print(f"Token: {token[:20]}..." if token else "Token: Not set")
print(f"Token length: {len(token) if token else 0}")
print(f"Channel: {channel}")

# Show token structure
if token:
    parts = token.split("-")
    print(f"Token parts: {len(parts)}")
    print(f"Token format: {'-'.join([p[:4] + '...' for p in parts])}")

print("\nNote: The token was provided in an image. You may need to re-enter it manually.")
print("A valid Slack bot token should start with 'xoxb-' and have 4 parts separated by dashes.")