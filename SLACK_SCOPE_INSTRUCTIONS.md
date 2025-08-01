# Instructions to Add groups:history Scope to Your Slack App

## Step-by-Step Guide

### 1. Go to Slack API Apps Page
Navigate to: **https://api.slack.com/apps**

### 2. Find Your App
Look for your app in the list. It should be the one with your bot token that starts with `xoxb-2930443898-...`

### 3. Click on Your App Name
This will take you to your app's configuration page

### 4. Navigate to OAuth & Permissions
In the left sidebar, click on **"OAuth & Permissions"**

### 5. Scroll to "Scopes" Section
Scroll down to find the **"Scopes"** section

### 6. Find "Bot Token Scopes"
Under the Scopes section, look for **"Bot Token Scopes"**

### 7. Current Scopes
You should see your current scopes:
- ✅ channels:history
- ✅ channels:read  
- ✅ chat:write
- ✅ reactions:write

### 8. Add New Scope
Click the **"Add an OAuth Scope"** button

### 9. Search and Add
Type `groups:history` in the search box and select it

### 10. Reinstall App
After adding the scope:
1. Scroll to the top of the page
2. You'll see a yellow banner saying "You've changed the scopes..."
3. Click **"reinstall your app"**
4. Review the permissions
5. Click **"Allow"**

### 11. Update Token (if changed)
If the token changed after reinstall:
1. Copy the new Bot User OAuth Token
2. Update it in your `.env` file
3. Restart the bot

## Alternative: Use Public Channel

If you prefer not to add the scope, you can:

1. Create a new PUBLIC channel in Slack
2. Get its channel ID (starts with 'C')
3. Update `SLACK_CHANNEL` in your `.env` file
4. The bot will work without needing `groups:history`

## Test After Changes

Run this command to verify everything works:
```bash
python slack_claude_bridge.py
```

The bot should now be able to read messages from your channel!