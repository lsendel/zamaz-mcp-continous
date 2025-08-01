#!/bin/bash
# Quick start script for Slack-Claude integration

echo "🤖 Slack-Claude Integration Launcher"
echo "===================================="
echo ""
echo "Choose an option:"
echo "1) Test connections"
echo "2) Run demo (automated)"
echo "3) Interactive mode (type messages)"
echo "4) Diagnose issues"
echo "5) Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "🧪 Testing connections..."
        python simple_slack_claude_test.py
        ;;
    2)
        echo "🎭 Running demo..."
        python test_bidirectional_communication.py
        ;;
    3)
        echo "💬 Starting interactive mode..."
        echo "1" | python slack_claude_interactive.py
        ;;
    4)
        echo "🔍 Running diagnostics..."
        python diagnose_slack_issue.py
        ;;
    5)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run again."
        exit 1
        ;;
esac