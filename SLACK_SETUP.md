# Slack Bot Setup Guide

## Quick Start

Your Slack bot is now configured and ready to use!

### 1. Start the Bot

Run the following command from the project directory:

```bash
python start_slack_bot.py
```

### 2. Verify Bot is Running

You should see messages like:
```
Starting Claude Remote Client with Slack integration...
Connected to Slack successfully!
Bot is listening in channel: C098WUY87L1
```

### 3. Use the Bot in Slack

In your Slack channel (C098WUY87L1), you can:

- Type `@@help` to see available commands
- Type `@@projects` to list available projects
- Type `@@switch zamaz-mcp` to start a Claude session
- Then just type normally to chat with Claude!

### Available Commands

- `@@help` - Show help message
- `@@projects` - List available projects
- `@@switch <project>` - Switch to a project
- `@@sessions` - List active sessions
- `@@quit` - End current session
- `@@queue_add <task>` - Add task to queue
- `@@queue` - View task queue

### Configuration

Your credentials and project settings are stored in `.env`:
- `SLACK_BOT_TOKEN` - Your bot token
- `SLACK_SIGNING_SECRET` - Your signing secret
- `SLACK_CHANNEL` - Your channel ID
- `PROJECT_NAME` - Your project name (zamaz-mcp)
- `PROJECT_PATH` - Your project path (/Users/lsendel/IdeaProjects/zamaz-mcp-continous)

The main configuration is in `config.yaml` which references these environment variables.

### Troubleshooting

If the bot doesn't respond:
1. Check that the bot is invited to your channel
2. Verify the channel ID is correct
3. Check the logs for any errors
4. Ensure Claude CLI is installed and working

### Security Note

Keep your `.env` file secure and never commit it to version control!