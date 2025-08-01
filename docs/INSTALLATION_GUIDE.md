# Claude Remote Client - Installation Guide

This guide provides detailed installation instructions for Claude Remote Client across different environments and use cases.

## System Requirements

### Minimum Requirements
- **Python**: 3.9 or higher (3.11+ recommended)
- **Operating System**: Linux, macOS, or Windows
- **Memory**: 512MB RAM minimum, 1GB recommended
- **Storage**: 100MB free space for installation
- **Network**: Internet connection for Slack API access

### Dependencies
- **Claude CLI**: Must be installed and accessible in PATH
- **Slack Bot Token**: With appropriate permissions
- **Slack Channel**: Where the bot will operate

## Pre-Installation Setup

### 1. Install Claude CLI

Follow the official Claude CLI installation guide:
https://docs.anthropic.com/claude/reference/cli-quickstart

Verify installation:
```bash
claude --version
```

### 2. Create Slack Bot

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "Claude Remote Client")
4. Select your workspace
5. Configure OAuth & Permissions:
   - Add Bot Token Scopes:
     - `chat:write`
     - `channels:read`
     - `channels:history`
     - `app_mentions:read`
   - Install app to workspace
   - Copy Bot User OAuth Token (starts with `xoxb-`)

### 3. Get Channel ID

1. Open Slack in browser
2. Navigate to your target channel
3. Copy channel ID from URL (starts with `C`)

## Installation Methods

### Method 1: PyPI Installation (Recommended)

#### Basic Installation
```bash
pip install claude-remote-client
```

#### With Enhanced Features
```bash
pip install claude-remote-client[enhanced]
```

#### With All Features (Development)
```bash
pip install claude-remote-client[all]
```

### Method 2: From Source

#### Clone and Install
```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
pip install -e .
```

#### Development Installation
```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
pip install -e .[dev]
```

### Method 3: Docker Installation

#### Using Docker Hub
```bash
docker pull claude-remote-client:latest
```

#### Build from Source
```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
docker build -t claude-remote-client .
```

## Post-Installation Configuration

### 1. Run Setup Wizard

```bash
claude-remote-client --setup
```

The wizard will guide you through:
- System requirements check
- Slack configuration
- Claude CLI validation
- Project setup
- Configuration file creation

### 2. Manual Configuration

If you prefer manual setup, create `~/.claude-remote-client/config.yaml`:

```yaml
slack:
  bot_token: "xoxb-your-bot-token"
  channel_id: "C1234567890"
  signing_secret: "your-signing-secret"

claude:
  cli_path: "claude"
  default_args:
    - "--dangerously-skip-permissions"
  timeout: 300

projects:
  - name: "my-project"
    path: "~/projects/my-project"
    description: "My development project"

log_level: "INFO"
data_dir: "~/.claude-remote-client"
max_sessions: 10
task_queue_size: 100
```

### 3. Validate Installation

```bash
# Check system requirements
claude-remote-client --check

# Validate configuration
claude-remote-client --validate
```

## Environment-Specific Instructions

### Linux/Ubuntu

#### Install Python 3.9+
```bash
sudo apt update
sudo apt install python3.9 python3.9-pip python3.9-venv
```

#### Create Virtual Environment
```bash
python3.9 -m venv claude-remote-client-env
source claude-remote-client-env/bin/activate
pip install claude-remote-client
```

#### System Service Setup
```bash
# Create service file
sudo tee /etc/systemd/system/claude-remote-client.service > /dev/null <<EOF
[Unit]
Description=Claude Remote Client
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
ExecStart=$HOME/claude-remote-client-env/bin/claude-remote-client
Restart=always
RestartSec=10
Environment=PATH=$HOME/claude-remote-client-env/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable claude-remote-client
sudo systemctl start claude-remote-client
```

### macOS

#### Install Python via Homebrew
```bash
brew install python@3.11
```

#### Install Claude Remote Client
```bash
pip3.11 install claude-remote-client
```

#### Create Launch Agent
```bash
# Create plist file
cat > ~/Library/LaunchAgents/com.claude-remote-client.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude-remote-client</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/claude-remote-client</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

# Load launch agent
launchctl load ~/Library/LaunchAgents/com.claude-remote-client.plist
```

### Windows

#### Install Python
1. Download Python 3.11+ from https://python.org
2. Run installer with "Add to PATH" checked
3. Open Command Prompt as Administrator

#### Install Claude Remote Client
```cmd
pip install claude-remote-client
```

#### Create Windows Service
```cmd
# Install as Windows service (requires admin privileges)
sc create ClaudeRemoteClient binPath= "C:\Python311\Scripts\claude-remote-client.exe" start= auto
sc start ClaudeRemoteClient
```

## Docker Deployment

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  claude-remote-client:
    image: claude-remote-client:latest
    container_name: claude-bot
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_CHANNEL_ID=${SLACK_CHANNEL_ID}
      - LOG_LEVEL=INFO
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./projects:/projects:rw
      - claude-data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "claude-remote-client", "--check"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  claude-data:
```

Create `.env` file:
```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL_ID=C1234567890
```

Deploy:
```bash
docker-compose up -d
```

### Kubernetes Deployment

Create `claude-remote-client.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-remote-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: claude-remote-client
  template:
    metadata:
      labels:
        app: claude-remote-client
    spec:
      containers:
      - name: claude-remote-client
        image: claude-remote-client:latest
        env:
        - name: SLACK_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: claude-secrets
              key: slack-bot-token
        - name: SLACK_CHANNEL_ID
          value: "C1234567890"
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: projects
          mountPath: /projects
      volumes:
      - name: config
        configMap:
          name: claude-config
      - name: projects
        persistentVolumeClaim:
          claimName: claude-projects
---
apiVersion: v1
kind: Secret
metadata:
  name: claude-secrets
type: Opaque
stringData:
  slack-bot-token: "xoxb-your-token-here"
```

Deploy:
```bash
kubectl apply -f claude-remote-client.yaml
```

## Verification

### Test Installation

```bash
# Check version
claude-remote-client --version

# Verify system requirements
claude-remote-client --check

# Test configuration
claude-remote-client --validate

# Run in test mode (doesn't connect to Slack)
claude-remote-client --dry-run
```

### Test Slack Integration

1. Start the bot:
   ```bash
   claude-remote-client
   ```

2. In Slack, send a test message:
   ```
   @@help
   ```

3. Verify bot responds with command list

### Monitor Logs

```bash
# View logs
tail -f ~/.claude-remote-client/claude-remote-client.log

# Or with Docker
docker logs -f claude-bot
```

## Troubleshooting

### Common Installation Issues

**1. Python Version Error**
```bash
# Check Python version
python --version
python3 --version

# Install correct version
# Ubuntu/Debian
sudo apt install python3.11

# macOS
brew install python@3.11

# Windows: Download from python.org
```

**2. Permission Denied**
```bash
# Fix permissions
chmod 755 ~/.claude-remote-client
chmod 600 ~/.claude-remote-client/config.yaml

# Or install in user directory
pip install --user claude-remote-client
```

**3. Claude CLI Not Found**
```bash
# Check if Claude CLI is installed
which claude
claude --version

# Add to PATH if needed
export PATH=$PATH:/path/to/claude/bin

# Or specify full path in config
claude:
  cli_path: "/full/path/to/claude"
```

**4. Slack Connection Issues**
```bash
# Verify bot token
curl -H "Authorization: Bearer xoxb-your-token" \
     https://slack.com/api/auth.test

# Check bot permissions in Slack app settings
```

### Getting Help

- **Documentation**: Check [User Guide](USER_GUIDE.md)
- **Issues**: Report at [GitHub Issues](https://github.com/your-org/claude-remote-client/issues)
- **Community**: Join [GitHub Discussions](https://github.com/your-org/claude-remote-client/discussions)

## Next Steps

After successful installation:

1. **Read the [User Guide](USER_GUIDE.md)** for detailed usage instructions
2. **Configure your projects** in the config file
3. **Set up cron tasks** for automation
4. **Explore advanced features** like task queues and monitoring

---

**Installation complete! 🎉 You're ready to use Claude Remote Client.**