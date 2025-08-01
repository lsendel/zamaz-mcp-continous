# Valid Slack OAuth Scopes for Bot

## ⚠️ Important: Only use Bot Token Scopes

For a bot application, you should **only** configure Bot Token Scopes, not User Token Scopes.

## Valid Bot Token Scopes for Your Use Case:

### Essential Scopes:
```
channels:history     - View messages in public channels
channels:read        - View basic information about public channels
chat:write          - Send messages as @clbot
groups:history      - View messages in private channels
groups:read         - View basic information about private channels
im:history          - View messages in direct messages
im:read             - View basic information about direct messages
```

### Optional but Useful:
```
reactions:write     - Add emoji reactions to messages
users:read          - View people in a workspace
files:read          - View files shared in channels
```

## How to Configure in Slack App:

1. Go to https://api.slack.com/apps
2. Select your app (cl_bot)
3. Click "OAuth & Permissions" in the sidebar
4. Scroll to "Scopes" section
5. Under "Bot Token Scopes", add ONLY these scopes:
   - channels:history
   - channels:read
   - chat:write
   - groups:history
   - groups:read
   - im:history
   - im:read

6. Remove any User Token Scopes (leave that section empty)
7. Click "Reinstall to Workspace"

## Common Invalid Scopes to Avoid:

These are deprecated or invalid:
- `read` (too generic, deprecated)
- `post` (deprecated, use chat:write)
- `client` (not a valid scope)
- Any scope starting with `admin.` (requires Enterprise Grid)

## Testing Your Channel Type:

To determine if your channel is public or private:
- Channel IDs starting with `C` are usually channels (can be public or private)
- Channel IDs starting with `G` are private channels/groups
- Channel IDs starting with `D` are direct messages

Your channel `C098WUY87L1` appears to be a private channel based on the errors, so you need both:
- `groups:read`
- `groups:history`