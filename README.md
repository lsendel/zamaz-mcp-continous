# Claude Remote Client

[![CI](https://github.com/lsendel/zamaz-mcp-continous/actions/workflows/ci.yml/badge.svg)](https://github.com/lsendel/zamaz-mcp-continous/actions/workflows/ci.yml)
[![Code Quality](https://github.com/lsendel/zamaz-mcp-continous/actions/workflows/quality.yml/badge.svg)](https://github.com/lsendel/zamaz-mcp-continous/actions/workflows/quality.yml)
[![codecov](https://codecov.io/gh/lsendel/zamaz-mcp-continous/branch/main/graph/badge.svg)](https://codecov.io/gh/lsendel/zamaz-mcp-continous)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Development Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/lsendel/zamaz-mcp-continous)

A powerful Python application that enables remote Claude AI interaction through Slack with intelligent project management, session handling, and task automation. Transform your development workflow by accessing Claude's full capabilities from anywhere through your Slack workspace.

## 🚀 Features

### Core Capabilities
- **🤖 Full Claude CLI Integration**: Complete access to Claude's interactive mode, slash commands, and file operations
- **📱 Slack-Native Interface**: Seamless interaction through Slack with real-time streaming responses
- **🗂️ Smart Project Management**: Switch between multiple projects with preserved context and session state
- **⚡ Session Management**: Concurrent Claude sessions with automatic cleanup and state preservation
- **📋 Task Queue System**: Automated task processing with smart queuing and cron scheduling
- **🔧 Interactive Setup**: User-friendly configuration wizard for quick deployment

### Advanced Features
- **🕒 Cron Automation**: Schedule recurring development tasks (code cleanup, testing, reviews)
- **🔄 Queue Processing**: Iterative task execution with context preservation
- **🛡️ Error Handling**: Robust error recovery with automatic reconnection
- **📊 Monitoring**: Built-in health checks and performance monitoring
- **🐳 Docker Support**: Containerized deployment for easy scaling
- **🔐 Security**: Slack signing secret validation and secure credential management

## 📋 Requirements

- **Python 3.9+** (3.11+ recommended)
- **[Claude CLI](https://docs.anthropic.com/claude/reference/cli-quickstart)** installed and accessible
- **Slack Bot Token** with appropriate permissions
- **Slack Channel ID** where the bot will operate

## 🔧 Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install claude-remote-client
```

### Option 2: Install with Enhanced Features

```bash
pip install claude-remote-client[enhanced]
```

### Option 3: Development Installation

```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
pip install -e .[dev]
```

## ⚡ Quick Start

### 1. Initial Setup

Run the interactive setup wizard:

```bash
claude-remote-client --setup
```

This will guide you through:
- ✅ System requirements validation
- 🔑 Slack bot token configuration
- 📁 Project directory setup
- ⚙️ Claude CLI validation
- 📝 Configuration file creation

### 2. Start the Bot

```bash
claude-remote-client
```

Or with custom configuration:

```bash
claude-remote-client --config /path/to/your/config.yaml
```

### 3. Interact via Slack

In your configured Slack channel:

```
@@projects                    # List available projects
@@switch my-web-app          # Switch to a project
@@sessions                   # Show active sessions
@@help                       # Show all commands

# Regular messages go to Claude
How can I optimize this Python function?

# Claude slash commands work too
/help
/clear
/save conversation.md
```

## 🎯 Usage Guide

### Project Management Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@projects` | List all configured projects | `@@projects` |
| `@@switch <project>` | Switch to a specific project | `@@switch my-api` |
| `@@new <project>` | Create new session for project | `@@new mobile-app` |
| `@@sessions` | Show all active sessions | `@@sessions` |
| `@@quit` | Terminate current session | `@@quit` |

### Task Queue Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@queue_add <queue> <task>` | Add task to queue | `@@queue_add features "Add user auth"` |
| `@@queue <queue>` | Process entire queue | `@@queue features` |
| `@@queue_status [queue]` | Show queue status | `@@queue_status` |
| `@@queue_clear <queue>` | Clear specific queue | `@@queue_clear features` |

### Cron Automation Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@cron "<pattern>" <tasks>` | Schedule recurring tasks | `@@cron "0 */2 * * *" clean_code,run_tests` |

#### Pre-configured Cron Tasks
- `clean_code`: Automated code formatting and cleanup
- `run_tests`: Execute test suites and report results
- `code_review`: AI-powered code quality analysis
- `update_deps`: Check and update dependencies
- `security_scan`: Run security vulnerability checks
- `performance_check`: Analyze performance metrics
- `documentation_update`: Update README and documentation

### Claude Integration

All Claude CLI features are fully supported:

```bash
# Interactive prompts work seamlessly
What's the best way to structure this React component?

# Slash commands are passed through
/help                    # Show Claude help
/clear                   # Clear conversation
/save my-session.md      # Save conversation
/exit                    # Exit current session

# File operations work with full project context
Can you review the files in src/components/?
```

## ⚙️ Configuration

### Configuration File Location

- **Default**: `~/.claude-remote-client/config.yaml`
- **Custom**: Specify with `--config` flag
- **Example**: Copy from `claude-remote-client.example.yaml`

### Sample Configuration

```yaml
# Slack configuration
slack:
  bot_token: "xoxb-your-bot-token-here"
  channel_id: "C1234567890"
  signing_secret: "your-signing-secret"  # Optional but recommended

# Claude CLI configuration  
claude:
  cli_path: "claude"
  default_args:
    - "--dangerously-skip-permissions"
  timeout: 300

# Project configurations
projects:
  - name: "web-app"
    path: "~/projects/web-app"
    description: "Main web application"
  
  - name: "api-service"
    path: "~/projects/api"
    description: "Backend API service"

# Application settings
log_level: "INFO"
data_dir: "~/.claude-remote-client"
max_sessions: 10
task_queue_size: 100
```

### Environment Variables

All configuration options can be overridden with environment variables:

```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL_ID="C1234567890"
export CLAUDE_CLI_PATH="/usr/local/bin/claude"
export LOG_LEVEL="DEBUG"
```

## 🐳 Docker Deployment

### Using Docker Compose

```yaml
version: '3.8'
services:
  claude-remote-client:
    image: claude-remote-client:latest
    environment:
      - SLACK_BOT_TOKEN=xoxb-your-token
      - SLACK_CHANNEL_ID=C1234567890
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./projects:/projects
    restart: unless-stopped
```

### Build and Run

```bash
docker build -t claude-remote-client .
docker run -d --name claude-bot \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_CHANNEL_ID=C1234567890 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  claude-remote-client
```

## 🔧 Development

### Setup Development Environment

```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
pip install -e .[dev]
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=claude_remote_client

# Run specific test categories
pytest tests/test_integration.py
pytest tests/test_slack_client.py
```

### Code Quality

```bash
# Format code
black claude_remote_client tests

# Lint code
flake8 claude_remote_client tests

# Type checking
mypy claude_remote_client
```

## 🚀 Advanced Usage

### Background Service (systemd)

Create a systemd service file:

```ini
[Unit]
Description=Claude Remote Client
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/claude-remote-client
ExecStart=/usr/local/bin/claude-remote-client
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable claude-remote-client
sudo systemctl start claude-remote-client
```

### Health Monitoring

The application includes built-in health checks:

```bash
# Check system requirements
claude-remote-client --check

# Validate configuration
claude-remote-client --validate

# Monitor logs
tail -f ~/.claude-remote-client/claude-remote-client.log
```

## 🔍 Troubleshooting

### Common Issues

**1. Claude CLI Not Found**
```bash
# Verify Claude CLI installation
claude --version

# Check PATH
which claude

# Install Claude CLI if missing
# Follow: https://docs.anthropic.com/claude/reference/cli-quickstart
```

**2. Slack Connection Issues**
```bash
# Verify bot token
claude-remote-client --validate

# Check bot permissions in Slack
# Required: chat:write, channels:read, channels:history
```

**3. Permission Errors**
```bash
# Ensure proper directory permissions
chmod 755 ~/.claude-remote-client
chmod 600 ~/.claude-remote-client/config.yaml
```

**4. Session Management Issues**
```bash
# Clear stuck sessions
rm -rf ~/.claude-remote-client/sessions/*

# Restart with clean state
claude-remote-client --config ~/.claude-remote-client/config.yaml
```

### Debug Mode

Enable detailed logging:

```bash
claude-remote-client --log-level DEBUG
```

### Getting Help

- 📖 **Documentation**: [User Guide](docs/USER_GUIDE.md)
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-org/claude-remote-client/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-org/claude-remote-client/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) for Claude AI
- [Slack](https://slack.com) for the excellent API
- The Python community for amazing libraries

---

**Made with ❤️ for developers who want to bring Claude AI into their workflow**
