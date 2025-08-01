# Claude Remote Client User Guide

This comprehensive guide provides detailed instructions for using Claude Remote Client to interact with Claude AI through Slack with intelligent project management, session handling, and task automation.

## Overview

Claude Remote Client is a powerful Python application that bridges Slack and Claude CLI, enabling remote development workflows with:

- **🤖 Full Claude CLI Integration**: Complete access to Claude's interactive mode and file operations
- **📱 Slack-Native Interface**: Seamless interaction through Slack with real-time responses
- **🗂️ Smart Project Management**: Switch between multiple projects with preserved context
- **⚡ Session Management**: Concurrent Claude sessions with automatic cleanup
- **📋 Task Queue System**: Automated task processing with smart queuing
- **🕒 Cron Automation**: Schedule recurring development tasks

## Getting Started

### Prerequisites

Before using Claude Remote Client, ensure you have:

1. **Claude CLI installed and configured** - [Installation Guide](https://docs.anthropic.com/claude/reference/cli-quickstart)
2. **Slack Bot Token** with appropriate permissions (`chat:write`, `channels:read`, `channels:history`)
3. **Python 3.9+** installed
4. **Claude Remote Client** installed (`pip install claude-remote-client`)

### Quick Setup

1. **Install Claude Remote Client**:
   ```bash
   pip install claude-remote-client
   ```

2. **Run the setup wizard**:
   ```bash
   claude-remote-client --setup
   ```

3. **Start the bot**:
   ```bash
   claude-remote-client
   ```

4. **Test in Slack**:
   ```
   @@help
   ```

## Command Reference

### Project Management Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@projects` | List all configured projects | `@@projects` |
| `@@switch <project>` | Switch to a specific project | `@@switch web-app` |
| `@@new <project>` | Create new session for project | `@@new api-service` |
| `@@sessions` | Show all active sessions | `@@sessions` |
| `@@status` | Show current session status | `@@status` |
| `@@quit` or `@@q` | Terminate current session | `@@quit` |

### Task Queue Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@queue_add <queue> <task>` | Add task to named queue | `@@queue_add features "Add user auth"` |
| `@@queue <queue>` | Process entire queue iteratively | `@@queue features` |
| `@@queue_status [queue]` | Show queue status and progress | `@@queue_status features` |
| `@@queue_clear <queue>` | Clear specific queue | `@@queue_clear features` |
| `@@queue_list` | List all available queues | `@@queue_list` |

### Cron Automation Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@cron "<pattern>" <tasks>` | Schedule recurring tasks | `@@cron "0 */2 * * *" clean_code,run_tests` |
| `@@cron_list` | Show active cron schedules | `@@cron_list` |
| `@@cron_stop <id>` | Stop a cron schedule | `@@cron_stop 1` |

#### Cron Pattern Examples
- `"0 */2 * * *"` - Every 2 hours
- `"0 9 * * 1-5"` - 9 AM on weekdays  
- `"0 0 * * 0"` - Every Sunday at midnight
- `"*/15 * * * *"` - Every 15 minutes

#### Pre-configured Cron Tasks
- `clean_code` - Automated code formatting and cleanup
- `run_tests` - Execute test suites and report results
- `code_review` - AI-powered code quality analysis
- `update_deps` - Check and update dependencies
- `security_scan` - Run security vulnerability checks
- `performance_check` - Analyze performance metrics
- `documentation_update` - Update README and documentation

### System Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@@help` | Show available commands | `@@help` |
| `@@version` | Show bot version | `@@version` |
| `@@ping` | Test bot responsiveness | `@@ping` |
| `@@restart` | Restart current Claude session | `@@restart` |
| `@@stop` | Stop current Claude session | `@@stop` |

## Core Workflows

### Multi-Project Development

Claude Remote Client excels at managing multiple projects simultaneously:

```
# List your configured projects
@@projects
📁 Available projects:
  • web-app (/home/user/projects/web-app) - Main web application
  • api-service (/home/user/projects/api) - Backend API service
  • mobile-app (/home/user/projects/mobile) - Mobile application

# Switch between projects seamlessly
@@switch web-app
✅ Switched to project: web-app
🗂️ Working directory: /home/user/projects/web-app

How can I improve the React component structure in src/components/?

@@switch api-service
✅ Switched to project: api-service  
🗂️ Working directory: /home/user/projects/api

Can you review the authentication middleware in auth.py?

# Check all active sessions
@@sessions
🔄 Active sessions:
  • web-app (Session ID: web-app-1) - Active since 10:30 AM
  • api-service (Session ID: api-service-1) - Active since 10:45 AM
```

### Task Queue Workflows

Use task queues for systematic development work:

```
# Create a feature development queue
@@queue_add feature_auth "Implement user registration endpoint"
@@queue_add feature_auth "Add password validation with strength requirements"
@@queue_add feature_auth "Create comprehensive login tests"
@@queue_add feature_auth "Update API documentation with auth examples"
@@queue_add feature_auth "Add rate limiting to auth endpoints"

✅ Added 5 tasks to queue: feature_auth

# Check queue status
@@queue_status feature_auth
📋 Queue: feature_auth
  Status: Ready (5 tasks pending)
  Tasks:
    1. [ ] Implement user registration endpoint
    2. [ ] Add password validation with strength requirements  
    3. [ ] Create comprehensive login tests
    4. [ ] Update API documentation with auth examples
    5. [ ] Add rate limiting to auth endpoints

# Process the entire queue iteratively
@@queue feature_auth
🚀 Processing queue: feature_auth

📝 Task 1/5: Implement user registration endpoint
[Claude processes the task with full context...]

✅ Task 1 completed successfully
📝 Task 2/5: Add password validation with strength requirements
[Claude continues with next task...]
```

### Automated Maintenance

Set up recurring maintenance tasks:

```
# Daily code cleanup at 2 AM
@@cron "0 2 * * *" clean_code
✅ Scheduled daily code cleanup at 2:00 AM

# Run tests every 4 hours on weekdays
@@cron "0 */4 * * 1-5" run_tests  
✅ Scheduled test runs every 4 hours (weekdays only)

# Weekly security scan on Sundays
@@cron "0 0 * * 0" security_scan
✅ Scheduled weekly security scan (Sundays at midnight)

# Check active schedules
@@cron_list
🕒 Active cron schedules:
  1. Daily cleanup: "0 2 * * *" → clean_code (Next: Today 2:00 AM)
  2. Test runs: "0 */4 * * 1-5" → run_tests (Next: Today 4:00 PM)
  3. Security scan: "0 0 * * 0" → security_scan (Next: Sunday 12:00 AM)
```

## Claude Integration Features

### Interactive Conversations

Claude Remote Client provides full access to Claude's capabilities:

```
# Regular conversation with full context
Can you help me debug this Python function that's causing memory leaks?

# Follow-up questions maintain conversation context
What about error handling for edge cases when the database is unavailable?

# Code review requests with project awareness
Please review all the files in src/components/ and suggest improvements

# Architecture discussions
What's the best way to structure this microservices architecture?
```

### Claude Slash Commands

All Claude CLI slash commands work seamlessly:

```
/help                    # Show Claude help and available commands
/clear                   # Clear conversation history
/save my-session.md      # Save conversation to file
/files                   # List and explore project files
/exit                    # Exit current Claude session
/reset                   # Reset Claude's context
```

### File Operations

Claude can perform full file system operations within your projects:

```
# Create new files
Can you create a new React component for user profiles with TypeScript?

# Modify existing files  
Please refactor the database connection code in db.py to use connection pooling

# Review and analyze code
Analyze the performance bottlenecks in the API endpoints

# Generate documentation
Create comprehensive API documentation for all the endpoints in routes/
```

## Configuration

### Configuration File Structure

The main configuration file is located at `~/.claude-remote-client/config.yaml`:

```yaml
# Slack configuration
slack:
  bot_token: "xoxb-your-bot-token-here"
  channel_id: "C1234567890"
  signing_secret: "your-signing-secret"  # Optional but recommended
  
# Claude CLI configuration
claude:
  cli_path: "claude"                     # Path to Claude CLI executable
  default_args:
    - "--dangerously-skip-permissions"   # Enable full file system access
  timeout: 300                          # Command timeout in seconds

# Project configurations
projects:
  - name: "web-app"
    path: "~/projects/web-app"
    description: "Main web application with React frontend"
    
  - name: "api-service"
    path: "~/projects/api"
    description: "Backend API service with FastAPI"
    
  - name: "mobile-app"
    path: "~/projects/mobile"
    description: "React Native mobile application"
    
  - name: "data-pipeline"
    path: "~/projects/etl"
    description: "Data processing and ETL pipeline"

# Application settings
log_level: "INFO"                       # DEBUG, INFO, WARNING, ERROR
data_dir: "~/.claude-remote-client"     # Data storage directory
max_sessions: 10                        # Maximum concurrent sessions
task_queue_size: 100                    # Maximum tasks per queue

# Advanced settings
reconnect_attempts: 5                   # Slack reconnection attempts
reconnect_delay: 10                     # Delay between reconnection attempts
session_timeout: 3600                   # Session timeout in seconds
```

### Environment Variables

Override any configuration setting with environment variables:

```bash
# Slack configuration
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL_ID="C1234567890"
export SLACK_SIGNING_SECRET="your-signing-secret"

# Claude configuration
export CLAUDE_CLI_PATH="/usr/local/bin/claude"
export CLAUDE_TIMEOUT="600"

# Application settings
export LOG_LEVEL="DEBUG"
export MAX_SESSIONS="5"
export DATA_DIR="/custom/data/path"
```

### Adding New Projects

#### Method 1: Configuration File

Edit `~/.claude-remote-client/config.yaml`:

```yaml
projects:
  - name: "new-project"
    path: "/path/to/new-project"
    description: "Description of the new project"
```

#### Method 2: Setup Wizard

Run the setup wizard to add projects interactively:

```bash
claude-remote-client --setup
```

#### Method 3: Environment Variables

Add projects via environment variables:

```bash
export PROJECT_NEW_NAME="new-project"
export PROJECT_NEW_PATH="/path/to/new-project"
export PROJECT_NEW_DESC="New project description"
```

## Best Practices

### Project Organization

1. **Use descriptive project names**: 
   - ✅ `web-frontend`, `api-backend`, `mobile-ios`
   - ❌ `proj1`, `test`, `stuff`

2. **Organize by purpose or team**:
   ```yaml
   projects:
     # Frontend projects
     - name: "web-app"
     - name: "admin-dashboard"
     
     # Backend projects  
     - name: "api-service"
     - name: "auth-service"
     
     # Mobile projects
     - name: "mobile-ios"
     - name: "mobile-android"
   ```

3. **Use absolute paths**: Avoid relative paths that might cause confusion
4. **Add meaningful descriptions**: Help team members understand project purposes

### Session Management

1. **Switch contexts cleanly**: Always use `@@switch` when changing projects
2. **Monitor active sessions**: Regular `@@sessions` checks prevent resource waste
3. **Clean up when done**: Use `@@quit` to properly terminate sessions
4. **Restart if needed**: Use `@@restart` for fresh starts or when sessions become unresponsive

### Task Queue Usage

1. **Break down large tasks**: Create specific, actionable items
   - ✅ "Implement user registration with email validation"
   - ❌ "Build user system"

2. **Use descriptive task names**: Make purposes and scope clear
3. **Group related tasks**: Use meaningful queue names (`features`, `bugfixes`, `maintenance`)
4. **Monitor progress**: Regular `@@queue_status` checks ensure smooth execution

### Automation Guidelines

1. **Start simple**: Begin with basic cron tasks before complex workflows
2. **Test thoroughly**: Verify tasks work correctly before scheduling
3. **Monitor results**: Check automation outcomes and adjust as needed
4. **Use appropriate timing**: Consider team schedules and system load

## Troubleshooting

### Common Issues and Solutions

#### Bot Not Responding

**Symptoms**: No response to `@@` commands in Slack

**Solutions**:
1. Check if bot is running:
   ```bash
   ps aux | grep claude-remote-client
   ```

2. Verify Slack connection:
   ```bash
   claude-remote-client --validate
   ```

3. Check logs for errors:
   ```bash
   tail -f ~/.claude-remote-client/claude-remote-client.log
   ```

4. Restart the bot:
   ```bash
   claude-remote-client
   ```

#### Claude CLI Issues

**Symptoms**: "Claude CLI not found" or command failures

**Solutions**:
1. Verify Claude CLI installation:
   ```bash
   claude --version
   ```

2. Check PATH configuration:
   ```bash
   which claude
   echo $PATH
   ```

3. Test Claude CLI directly:
   ```bash
   claude --help
   ```

4. Update configuration with full path:
   ```yaml
   claude:
     cli_path: "/full/path/to/claude"
   ```

#### Session Problems

**Symptoms**: Sessions not switching, stuck processes, or memory issues

**Solutions**:
1. Check active sessions:
   ```
   @@sessions
   ```

2. Clear stuck sessions:
   ```bash
   rm -rf ~/.claude-remote-client/sessions/*
   ```

3. Restart bot with clean state:
   ```bash
   claude-remote-client --config ~/.claude-remote-client/config.yaml
   ```

4. Check system resources:
   ```bash
   top
   df -h
   ```

#### Permission Errors

**Symptoms**: "Permission denied" errors or file access issues

**Solutions**:
1. Check file permissions:
   ```bash
   ls -la ~/.claude-remote-client/
   ```

2. Fix permissions:
   ```bash
   chmod 755 ~/.claude-remote-client
   chmod 600 ~/.claude-remote-client/config.yaml
   ```

3. Verify project directory access:
   ```bash
   ls -la /path/to/your/project
   ```

#### Slack Connection Issues

**Symptoms**: Connection timeouts, authentication failures

**Solutions**:
1. Verify bot token:
   ```bash
   curl -H "Authorization: Bearer xoxb-your-token" \
        https://slack.com/api/auth.test
   ```

2. Check bot permissions in Slack app settings
3. Verify channel ID is correct
4. Test with signing secret disabled temporarily

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
claude-remote-client --log-level DEBUG --log-file debug.log
```

Monitor debug output:
```bash
tail -f debug.log
```

### System Health Checks

Regular maintenance commands:

```bash
# Check system requirements
claude-remote-client --check

# Validate configuration
claude-remote-client --validate

# Test without connecting to Slack
claude-remote-client --dry-run
```

## Tips and Productivity Hacks

### Workflow Optimization

1. **Use project aliases**: Create short, memorable project names
2. **Batch similar tasks**: Group related work in queues for efficiency
3. **Leverage automation**: Set up recurring tasks for routine maintenance
4. **Save important conversations**: Use `/save` to preserve valuable interactions

### Advanced Workflows

1. **Feature development pipeline**:
   ```
   @@queue_add feature_x "Design API endpoints"
   @@queue_add feature_x "Implement backend logic"
   @@queue_add feature_x "Create frontend components"
   @@queue_add feature_x "Write comprehensive tests"
   @@queue_add feature_x "Update documentation"
   @@queue feature_x
   ```

2. **Code review automation**:
   ```
   @@cron "0 17 * * 1-5" code_review
   ```

3. **Multi-project coordination**:
   ```
   @@switch api-service
   Update the user endpoint to return additional fields
   
   @@switch web-app
   Update the frontend to display the new user fields
   
   @@switch mobile-app
   Sync mobile app with the updated user data structure
   ```

### Integration Ideas

1. **CI/CD integration**: Trigger builds and deployments from Slack
2. **Monitoring integration**: Get alerts and status updates via Claude
3. **Team collaboration**: Share Claude sessions and insights
4. **Knowledge management**: Save and organize useful conversations

## Security Best Practices

### Slack Security

1. **Use signing secrets**: Enable request verification for security
2. **Limit bot permissions**: Grant only necessary OAuth scopes
3. **Secure token storage**: Use environment variables, not config files
4. **Regular token rotation**: Update tokens periodically
5. **Monitor bot activity**: Review logs for unusual behavior

### File System Security

1. **Validate project paths**: Ensure paths are within expected directories
2. **Use appropriate permissions**: Limit file system access appropriately
3. **Monitor file operations**: Log and review file system changes
4. **Backup important data**: Protect against accidental data loss
5. **Sandbox environments**: Use containers or VMs for isolation

### Network Security

1. **Use HTTPS**: Ensure all connections are encrypted
2. **Validate certificates**: Check SSL/TLS certificate validity
3. **Monitor network traffic**: Watch for unusual connection patterns
4. **Use VPN when needed**: Secure connections for remote access
5. **Firewall configuration**: Limit network access appropriately

## Getting Help

### Documentation Resources

- **Installation Guide**: [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- **Package Documentation**: [PACKAGE_README.md](PACKAGE_README.md)
- **API Reference**: Generated from code documentation

### Community Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/your-org/claude-remote-client/issues)
- **GitHub Discussions**: [Community Q&A and discussions](https://github.com/your-org/claude-remote-client/discussions)
- **Documentation**: [Online documentation](https://github.com/your-org/claude-remote-client/blob/main/README.md)

### Self-Help Tools

```bash
# Built-in help
claude-remote-client --help

# System diagnostics
claude-remote-client --check

# Configuration validation
claude-remote-client --validate

# Version information
claude-remote-client --version
```

---

**You're now ready to maximize your productivity with Claude Remote Client! 🚀**

This user guide covers all the essential features and workflows. For additional help or advanced use cases, consult the community resources or create an issue on GitHub.