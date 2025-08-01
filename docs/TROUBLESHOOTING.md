# Claude Remote Client - Troubleshooting Guide

This guide helps you diagnose and resolve common issues with Claude Remote Client.

## Quick Diagnostics

### System Health Check
```bash
# Check all system requirements
claude-remote-client --check

# Validate configuration
claude-remote-client --validate

# Show version and system info
claude-remote-client --version
```

### Log Analysis
```bash
# View recent logs
tail -f ~/.claude-remote-client/claude-remote-client.log

# View logs with debug information
claude-remote-client --log-level DEBUG

# Search for specific errors
grep -i error ~/.claude-remote-client/claude-remote-client.log
```

## Common Issues

### 1. Bot Not Responding in Slack

**Symptoms:**
- No response to `@@` commands
- Bot appears offline in Slack
- Commands timeout without response

**Diagnosis:**
```bash
# Check if bot process is running
ps aux | grep claude-remote-client

# Verify Slack connection
claude-remote-client --validate

# Test bot token
curl -H "Authorization: Bearer xoxb-your-token" \
     https://slack.com/api/auth.test
```

**Solutions:**

1. **Restart the bot:**
   ```bash
   # Kill existing process
   pkill -f claude-remote-client
   
   # Start fresh
   claude-remote-client
   ```

2. **Check bot permissions:**
   - Go to https://api.slack.com/apps
   - Select your app
   - Check OAuth & Permissions
   - Ensure these scopes are granted:
     - `chat:write`
     - `channels:read`
     - `channels:history`
     - `app_mentions:read`

3. **Verify channel configuration:**
   ```bash
   # Check channel ID format (should start with 'C')
   echo $SLACK_CHANNEL_ID
   
   # Test in different channel
   claude-remote-client --config test-config.yaml
   ```

4. **Network connectivity:**
   ```bash
   # Test Slack API connectivity
   ping slack.com
   
   # Check firewall/proxy settings
   curl -I https://slack.com/api/auth.test
   ```

### 2. Claude CLI Not Found

**Symptoms:**
- "Claude CLI not found" error messages
- Commands fail with "command not found"
- Setup wizard reports Claude CLI missing

**Diagnosis:**
```bash
# Check if Claude CLI is installed
claude --version

# Check PATH
which claude
echo $PATH

# Check if Claude CLI is executable
ls -la $(which claude)
```

**Solutions:**

1. **Install Claude CLI:**
   ```bash
   # Follow official installation guide
   # https://docs.anthropic.com/claude/reference/cli-quickstart
   
   # Verify installation
   claude --version
   ```

2. **Fix PATH issues:**
   ```bash
   # Add Claude CLI to PATH
   export PATH=$PATH:/path/to/claude/bin
   
   # Make permanent (add to ~/.bashrc or ~/.zshrc)
   echo 'export PATH=$PATH:/path/to/claude/bin' >> ~/.bashrc
   ```

3. **Specify full path in configuration:**
   ```yaml
   claude:
     cli_path: "/full/path/to/claude"
     default_args:
       - "--dangerously-skip-permissions"
   ```

4. **Permission issues:**
   ```bash
   # Make Claude CLI executable
   chmod +x /path/to/claude
   
   # Check ownership
   ls -la /path/to/claude
   ```

### 3. Session Management Problems

**Symptoms:**
- Sessions not switching properly
- Stuck or unresponsive sessions
- Memory leaks or high CPU usage
- "Session not found" errors

**Diagnosis:**
```bash
# Check active sessions
@@sessions

# Check system resources
top
ps aux | grep claude

# Check session files
ls -la ~/.claude-remote-client/sessions/
```

**Solutions:**

1. **Clear stuck sessions:**
   ```bash
   # Stop bot
   pkill -f claude-remote-client
   
   # Clear session data
   rm -rf ~/.claude-remote-client/sessions/*
   
   # Restart bot
   claude-remote-client
   ```

2. **Restart specific session:**
   ```
   @@quit
   @@switch your-project
   ```

3. **Check session limits:**
   ```yaml
   # In config.yaml
   max_sessions: 5  # Reduce if experiencing issues
   session_timeout: 1800  # 30 minutes
   ```

4. **Monitor resource usage:**
   ```bash
   # Check memory usage
   free -h
   
   # Check disk space
   df -h ~/.claude-remote-client
   
   # Monitor in real-time
   watch -n 5 'ps aux | grep claude'
   ```

### 4. Configuration Issues

**Symptoms:**
- "Configuration error" messages
- Invalid YAML syntax errors
- Missing required fields
- Environment variable not recognized

**Diagnosis:**
```bash
# Validate configuration syntax
claude-remote-client --validate

# Check configuration file
cat ~/.claude-remote-client/config.yaml

# Verify environment variables
env | grep -E "(SLACK|CLAUDE)"
```

**Solutions:**

1. **Fix YAML syntax:**
   ```bash
   # Use YAML validator
   python -c "import yaml; yaml.safe_load(open('~/.claude-remote-client/config.yaml'))"
   
   # Common issues:
   # - Incorrect indentation (use spaces, not tabs)
   # - Missing quotes around special characters
   # - Inconsistent list formatting
   ```

2. **Regenerate configuration:**
   ```bash
   # Backup existing config
   cp ~/.claude-remote-client/config.yaml ~/.claude-remote-client/config.yaml.backup
   
   # Run setup wizard
   claude-remote-client --setup
   ```

3. **Environment variable issues:**
   ```bash
   # Check variable names (case sensitive)
   export SLACK_BOT_TOKEN="xoxb-your-token"  # Not slack_bot_token
   
   # Verify variables are set
   echo $SLACK_BOT_TOKEN
   echo $SLACK_CHANNEL_ID
   ```

4. **Permission problems:**
   ```bash
   # Fix file permissions
   chmod 600 ~/.claude-remote-client/config.yaml
   chmod 755 ~/.claude-remote-client
   
   # Check ownership
   ls -la ~/.claude-remote-client/
   ```

### 5. Task Queue Issues

**Symptoms:**
- Tasks not executing
- Queue processing hangs
- Tasks marked as failed without clear reason
- Cron schedules not running

**Diagnosis:**
```bash
# Check queue status
@@queue_status

# Check cron schedules
@@cron_list

# Check logs for task execution
grep -i "queue\|cron\|task" ~/.claude-remote-client/claude-remote-client.log
```

**Solutions:**

1. **Clear problematic queues:**
   ```
   @@queue_clear problematic-queue
   @@queue_add problematic-queue "test task"
   @@queue problematic-queue
   ```

2. **Restart cron scheduler:**
   ```bash
   # Restart bot to reset cron scheduler
   pkill -f claude-remote-client
   claude-remote-client
   ```

3. **Check task syntax:**
   ```
   # Ensure tasks are properly formatted
   @@queue_add myqueue "Simple task description"
   
   # Avoid special characters that might break parsing
   ```

4. **Monitor task execution:**
   ```bash
   # Enable debug logging
   claude-remote-client --log-level DEBUG
   
   # Watch logs during task execution
   tail -f ~/.claude-remote-client/claude-remote-client.log
   ```

### 6. Permission and Security Issues

**Symptoms:**
- "Permission denied" errors
- File access failures
- Authentication errors
- SSL/TLS connection issues

**Diagnosis:**
```bash
# Check file permissions
ls -la ~/.claude-remote-client/
ls -la ~/.claude-remote-client/config.yaml

# Check project directory permissions
ls -la /path/to/your/project

# Test network connectivity
curl -I https://slack.com/api/auth.test
```

**Solutions:**

1. **Fix file permissions:**
   ```bash
   # Configuration directory
   chmod 755 ~/.claude-remote-client
   
   # Configuration file (sensitive)
   chmod 600 ~/.claude-remote-client/config.yaml
   
   # Log files
   chmod 644 ~/.claude-remote-client/*.log
   ```

2. **Project directory access:**
   ```bash
   # Ensure bot can access project directories
   chmod 755 /path/to/your/project
   
   # Check if directories exist
   ls -la /path/to/your/project
   ```

3. **Network security:**
   ```bash
   # Update certificates
   sudo apt-get update && sudo apt-get install ca-certificates
   
   # Test SSL connection
   openssl s_client -connect slack.com:443
   ```

4. **Slack token security:**
   ```bash
   # Use environment variables instead of config file
   export SLACK_BOT_TOKEN="xoxb-your-token"
   unset SLACK_BOT_TOKEN  # Clear when done
   ```

## Advanced Troubleshooting

### Debug Mode

Enable comprehensive debugging:

```bash
# Start with maximum debugging
claude-remote-client --log-level DEBUG --log-file debug.log

# Monitor debug output
tail -f debug.log

# Filter specific components
grep -i "slack\|claude\|session" debug.log
```

### Network Debugging

```bash
# Test Slack API endpoints
curl -H "Authorization: Bearer xoxb-your-token" \
     https://slack.com/api/auth.test

curl -H "Authorization: Bearer xoxb-your-token" \
     https://slack.com/api/conversations.info?channel=C1234567890

# Monitor network traffic
sudo tcpdump -i any host slack.com

# Check DNS resolution
nslookup slack.com
```

### Process Debugging

```bash
# Monitor process behavior
strace -p $(pgrep -f claude-remote-client)

# Check memory usage
pmap $(pgrep -f claude-remote-client)

# Monitor file operations
lsof -p $(pgrep -f claude-remote-client)
```

### Database/State Debugging

```bash
# Check session state files
ls -la ~/.claude-remote-client/sessions/
cat ~/.claude-remote-client/sessions/session-id.json

# Check queue state
ls -la ~/.claude-remote-client/queues/
cat ~/.claude-remote-client/queues/queue-name.json

# Check cron state
cat ~/.claude-remote-client/cron-schedules.json
```

## Performance Issues

### High Memory Usage

**Diagnosis:**
```bash
# Check memory usage
ps aux | grep claude-remote-client
free -h

# Monitor memory over time
watch -n 5 'ps aux | grep claude-remote-client'
```

**Solutions:**
1. Reduce max_sessions in configuration
2. Clear old session data regularly
3. Restart bot periodically
4. Monitor for memory leaks in logs

### High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage
top -p $(pgrep -f claude-remote-client)

# Profile CPU usage
perf top -p $(pgrep -f claude-remote-client)
```

**Solutions:**
1. Check for infinite loops in logs
2. Reduce polling frequency
3. Optimize cron schedules
4. Check for stuck processes

### Slow Response Times

**Diagnosis:**
```bash
# Test response times
time curl -H "Authorization: Bearer xoxb-your-token" \
          https://slack.com/api/auth.test

# Check network latency
ping slack.com
```

**Solutions:**
1. Check network connectivity
2. Optimize Claude CLI arguments
3. Reduce session timeout
4. Use local caching where possible

## Recovery Procedures

### Complete Reset

If all else fails, perform a complete reset:

```bash
# 1. Stop all processes
pkill -f claude-remote-client

# 2. Backup configuration
cp ~/.claude-remote-client/config.yaml ~/config-backup.yaml

# 3. Clear all data
rm -rf ~/.claude-remote-client/*

# 4. Restore configuration
cp ~/config-backup.yaml ~/.claude-remote-client/config.yaml

# 5. Restart
claude-remote-client
```

### Emergency Recovery

For critical issues:

```bash
# 1. Kill all related processes
sudo pkill -9 -f claude
sudo pkill -9 -f claude-remote-client

# 2. Clear system resources
sudo sync
sudo echo 3 > /proc/sys/vm/drop_caches

# 3. Check system health
df -h
free -h
ps aux | grep claude

# 4. Restart with minimal configuration
claude-remote-client --config minimal-config.yaml
```

## Getting Help

### Self-Help Resources

```bash
# Built-in help
claude-remote-client --help

# System diagnostics
claude-remote-client --check

# Configuration validation
claude-remote-client --validate

# Version and environment info
claude-remote-client --version
```

### Community Support

- **GitHub Issues**: [Report bugs](https://github.com/your-org/claude-remote-client/issues)
- **GitHub Discussions**: [Community Q&A](https://github.com/your-org/claude-remote-client/discussions)
- **Documentation**: [Full documentation](https://github.com/your-org/claude-remote-client/blob/main/README.md)

### Creating Bug Reports

When reporting issues, include:

1. **System information:**
   ```bash
   claude-remote-client --version
   python --version
   uname -a
   ```

2. **Configuration (sanitized):**
   ```bash
   # Remove sensitive tokens before sharing
   cat ~/.claude-remote-client/config.yaml
   ```

3. **Logs:**
   ```bash
   # Last 50 lines of logs
   tail -50 ~/.claude-remote-client/claude-remote-client.log
   ```

4. **Steps to reproduce:**
   - Exact commands used
   - Expected behavior
   - Actual behavior
   - Error messages

5. **Environment details:**
   - Operating system
   - Python version
   - Claude CLI version
   - Network configuration

---

**Still having issues? Don't hesitate to reach out to the community for help! 🤝**