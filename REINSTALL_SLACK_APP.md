# Reinstall Slack App After Adding Scopes

After adding new OAuth scopes to your Slack app, you must reinstall it to apply the changes.

## Steps to Reinstall:

1. **Go to your Slack app settings**
   - Visit: https://api.slack.com/apps
   - Click on your app (clbot)

2. **Navigate to OAuth & Permissions**
   - In the left sidebar, click "OAuth & Permissions"

3. **Reinstall the app**
   - At the top of the page, click "Reinstall to Workspace"
   - Review the new permissions
   - Click "Allow"

4. **Copy the new Bot Token**
   - After reinstalling, you'll get a new Bot User OAuth Token
   - It should start with `xoxb-`
   - Copy this token

5. **Update your .env file**
   ```bash
   SLACK_BOT_TOKEN=xoxb-[your-new-token-here]
   ```

## Required Scopes for Private Channels:

Make sure these scopes are added before reinstalling:

**Bot Token Scopes:**
- `channels:history` - Read public channel messages
- `channels:read` - List public channels
- `groups:history` - Read private channel messages
- `groups:read` - List private channels
- `chat:write` - Send messages
- `users:read` - Get user info (optional but useful)
- `reactions:write` - Add reactions (optional)

**User Token Scopes (if needed):**
- Similar scopes but for user-level access

## Test After Reinstalling:

Run this command to verify the new scopes:
```bash
python3 debug_slack_permissions.py
```

You should see that the bot can now access private channels!