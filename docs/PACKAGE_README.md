# Claude Remote Client

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![PyPI Version](https://img.shields.io/pypi/v/claude-remote-client.svg)](https://pypi.org/project/claude-remote-client/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Remote Claude AI interaction through Slack with intelligent project management and task automation.**

Transform your development workflow by accessing Claude's full capabilities from anywhere through your Slack workspace. Claude Remote Client bridges Slack and Claude CLI, enabling seamless remote development with smart project switching, session management, and automated task processing.

## 🚀 Quick Start

### Installation

```bash
pip install claude-remote-client
```

### Setup

```bash
claude-remote-client --setup
```

### Start

```bash
claude-remote-client
```

### Use in Slack

```
@@projects                    # List your projects
@@switch my-web-app          # Switch to a project
How can I optimize this code? # Chat with Claude
```

## ✨ Key Features

- **🤖 Full Claude CLI Integration** - Complete access to Claude's interactive mode, slash commands, and file operations
- **📱 Slack-Native Interface** - Seamless interaction through Slack with real-time streaming responses
- **🗂️ Smart Project Management** - Switch between multiple projects with preserved context and session state
- **⚡ Concurrent Sessions** - Multiple Claude sessions running simultaneously with automatic cleanup
- **📋 Task Queue System** - Automated task processing with smart queuing and iterative execution
- **🕒 Cron Automation** - Schedule recurring development tasks (code cleanup, testing, reviews)
- **🔧 Interactive Setup** - User-friendly configuration wizard for quick deployment
- **🛡️ Robust Error Handling** - Automatic reconnection, error recovery, and comprehensive logging

## 🎯 Use Cases

### Development Workflows
- **Multi-project development** with instant context switching
- **Code review automation** with scheduled quality checks
- **Feature development pipelines** using task queues
- **Maintenance automation** with cron scheduling

### Team Collaboration
- **Shared Claude access** through Slack channels
- **Project-aware conversations** with preserved context
- **Automated reporting** of task completion and results
- **Knowledge sharing** through saved conversations

### DevOps Integration
- **CI/CD trigger integration** from Slack
- **Monitoring and alerting** via Claude analysis
- **Infrastructure management** with Claude assistance
- **Documentation automation** with scheduled updates

## 📋 Requirements

- **Python 3.9+** (3.11+ recommended)
- **[Claude CLI](https://docs.anthropic.com/claude/reference/cli-quickstart)** installed and accessible
- **Slack Bot Token** with appropriate permissions
- **Slack Channel ID** where the bot will operate

## 🔧 Installation Options

### Basic Installation
```bash
pip install claude-remote-client
```

### With Enhanced Features
```bash
pip install claude-remote-client[enhanced]
```

### Development Installation
```bash
pip install claude-remote-client[dev]
```

### All Features
```bash
pip install claude-remote-client[all]
```

## ⚡ Quick Configuration

### Interactive Setup (Recommended)
```bash
claude-remote-client --setup
```

### Manual Configuration
Create `~/.claude-remote-client/config.yaml`:

```yaml
slack:
  bot_token: "xoxb-your-bot-token"
  channel_id: "C1234567890"

claude:
  cli_path: "claude"
  default_args:
    - "--dangerously-skip-permissions"

projects:
  - name: "web-app"
    path: "~/projects/web-app"
    description: "Main web application"
```

### Environment Variables
```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL_ID="C1234567890"
```

## 🎮 Command Reference

### Project Management
| Command | Description |
|---------|-------------|
| `@@projects` | List all configured projects |
| `@@switch <project>` | Switch to a specific project |
| `@@sessions` | Show all active sessions |
| `@@quit` | Terminate current session |

### Task Automation
| Command | Description |
|---------|-------------|
| `@@queue_add <queue> <task>` | Add task to named queue |
| `@@queue <queue>` | Process entire queue |
| `@@cron "pattern" tasks` | Schedule recurring tasks |

### System Commands
| Command | Description |
|---------|-------------|
| `@@help` | Show available commands |
| `@@status` | Show current session status |
| `@@restart` | Restart current Claude session |

## 🔄 Workflow Examples

### Multi-Project Development
```
@@switch web-frontend
How can I improve the React component structure?

@@switch api-backend
Can you review the authentication middleware?

@@sessions  # Check all active sessions
```

### Task Queue Processing
```
@@queue_add features "Implement user authentication"
@@queue_add features "Add password validation"
@@queue_add features "Create login tests"
@@queue features  # Process all tasks
```

### Automated Maintenance
```
@@cron "0 2 * * *" clean_code        # Daily cleanup at 2 AM
@@cron "0 */4 * * 1-5" run_tests     # Tests every 4 hours (weekdays)
@@cron "0 0 * * 0" security_scan     # Weekly security scan
```

## 🐳 Docker Support

### Docker Compose
```yaml
version: '3.8'
services:
  claude-remote-client:
    image: claude-remote-client:latest
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_CHANNEL_ID=${SLACK_CHANNEL_ID}
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./projects:/projects
    restart: unless-stopped
```

### Run with Docker
```bash
docker run -d \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_CHANNEL_ID=C1234567890 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  claude-remote-client
```

## 🔍 System Commands

### Health Checks
```bash
claude-remote-client --check      # Check system requirements
claude-remote-client --validate   # Validate configuration
claude-remote-client --version    # Show version information
```

### Debugging
```bash
claude-remote-client --log-level DEBUG  # Enable debug logging
claude-remote-client --dry-run          # Test without connecting
```

### Service Management
```bash
claude-remote-client --daemon     # Run as background service
claude-remote-client --config /path/to/config.yaml  # Custom config
```

## 📚 Documentation

- **[Installation Guide](https://github.com/your-org/claude-remote-client/blob/main/docs/INSTALLATION_GUIDE.md)** - Detailed installation instructions
- **[User Guide](https://github.com/your-org/claude-remote-client/blob/main/docs/USER_GUIDE.md)** - Comprehensive usage documentation
- **[GitHub Repository](https://github.com/your-org/claude-remote-client)** - Source code and issues

## 🔧 Advanced Configuration

### Slack Bot Setup
1. Create Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `channels:read`, `channels:history`
3. Install app to workspace
4. Copy Bot User OAuth Token

### Claude CLI Setup
```bash
# Install Claude CLI (follow official guide)
claude --version

# Verify installation
claude-remote-client --check
```

### Project Configuration
```yaml
projects:
  - name: "frontend"
    path: "~/projects/web-app"
    description: "React frontend application"
    
  - name: "backend"
    path: "~/projects/api"
    description: "FastAPI backend service"
    
  - name: "mobile"
    path: "~/projects/mobile-app"
    description: "React Native mobile app"
```

## 🛠️ Development

### Local Development
```bash
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client
pip install -e .[dev]
```

### Run Tests
```bash
pytest                    # Run all tests
pytest --cov             # Run with coverage
pytest tests/integration # Run integration tests
```

### Code Quality
```bash
black claude_remote_client tests    # Format code
flake8 claude_remote_client tests   # Lint code
mypy claude_remote_client           # Type checking
```

## 🔐 Security

### Best Practices
- Use Slack signing secrets for request verification
- Store tokens in environment variables, not config files
- Limit bot permissions to necessary scopes only
- Monitor logs for unusual activity
- Use HTTPS for all connections

### File System Security
- Validate project paths to prevent directory traversal
- Use appropriate file permissions
- Monitor file operations and changes
- Backup important data regularly

## 🐛 Troubleshooting

### Common Issues

**Bot not responding in Slack**
```bash
claude-remote-client --validate  # Check configuration
tail -f ~/.claude-remote-client/claude-remote-client.log  # Check logs
```

**Claude CLI not found**
```bash
which claude              # Check if Claude CLI is in PATH
claude --version          # Verify Claude CLI works
```

**Permission errors**
```bash
chmod 755 ~/.claude-remote-client
chmod 600 ~/.claude-remote-client/config.yaml
```

### Getting Help
- **GitHub Issues**: [Report bugs](https://github.com/your-org/claude-remote-client/issues)
- **Discussions**: [Community support](https://github.com/your-org/claude-remote-client/discussions)
- **Documentation**: [Full documentation](https://github.com/your-org/claude-remote-client/blob/main/README.md)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/your-org/claude-remote-client/blob/main/LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](https://github.com/your-org/claude-remote-client/blob/main/CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) for Claude AI
- [Slack](https://slack.com) for the excellent API
- The Python community for amazing libraries

---

**Transform your development workflow with Claude Remote Client! 🚀**

*Made with ❤️ for developers who want to bring Claude AI into their daily workflow*