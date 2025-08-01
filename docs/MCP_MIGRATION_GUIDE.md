# Claude Remote Client MCP Migration Guide

## Overview

This guide provides step-by-step instructions for migrating from subprocess-based Claude communication to Model Context Protocol (MCP) integration. The migration is designed to be seamless, with zero downtime and automatic fallback capabilities.

## Migration Architecture

The Claude Remote Client uses a plugin architecture that supports three handler types:

1. **Subprocess Handler**: Traditional Claude CLI subprocess communication
2. **MCP Handler**: Native Model Context Protocol integration
3. **Hybrid Handler**: Automatic switching between subprocess and MCP

## Prerequisites

### System Requirements

- Python 3.9 or higher
- Claude CLI installed and accessible
- Network access for MCP communication (when using MCP mode)
- Sufficient disk space for configuration backups

### Configuration Backup

Before starting migration, backup your current configuration:

```bash
# Create backup directory
mkdir -p ~/.claude-remote-client/backups/$(date +%Y%m%d_%H%M%S)

# Backup configuration
cp ~/.claude-remote-client/config.yaml ~/.claude-remote-client/backups/$(date +%Y%m%d_%H%M%S)/

# Backup session data
cp -r ~/.claude-remote-client/sessions ~/.claude-remote-client/backups/$(date +%Y%m%d_%H%M%S)/

# Backup logs
cp -r ~/.claude-remote-client/logs ~/.claude-remote-client/backups/$(date +%Y%m%d_%H%M%S)/
```

## Migration Strategies

### Strategy 1: Conservative Migration (Recommended)

This approach maintains maximum compatibility while preparing for MCP:

#### Phase 1: Enable Hybrid Mode with Subprocess Preference

```yaml
# ~/.claude-remote-client/config.yaml
claude:
  handler_type: hybrid
  
  # Subprocess settings (primary)
  cli_path: claude
  default_args: ["--dangerously-skip-permissions"]
  timeout: 300
  
  # MCP settings (prepared for future)
  mcp_server_uri: mcp://localhost:8000
  mcp_protocol_version: "1.0"
  mcp_timeout: 30
  
  # Hybrid behavior (prefer subprocess initially)
  prefer_mcp: false
  fallback_to_subprocess: true
```

#### Phase 2: Test and Monitor

```bash
# Restart the service
sudo systemctl restart claude-remote-client

# Verify hybrid mode is active
claude-remote-client handler status

# Monitor for any issues
tail -f ~/.claude-remote-client/logs/claude-remote-client.log
```

#### Phase 3: Enable MCP Preference (When Ready)

```yaml
# Update configuration to prefer MCP
claude:
  handler_type: hybrid
  prefer_mcp: true  # Switch to MCP preference
  fallback_to_subprocess: true  # Keep fallback enabled
```

### Strategy 2: Aggressive Migration

For environments where MCP is already available and tested:

#### Direct Migration to MCP-First Hybrid

```yaml
claude:
  handler_type: hybrid
  
  # MCP settings (primary)
  mcp_server_uri: mcp://your-mcp-server:8000
  mcp_protocol_version: "1.0"
  mcp_timeout: 30
  prefer_mcp: true
  
  # Subprocess settings (fallback)
  cli_path: claude
  default_args: ["--dangerously-skip-permissions"]
  fallback_to_subprocess: true
```

### Strategy 3: MCP-Only Migration

For maximum performance when MCP is fully stable:

```yaml
claude:
  handler_type: mcp
  mcp_server_uri: mcp://your-mcp-server:8000
  mcp_protocol_version: "1.0"
  mcp_timeout: 30
```

**⚠️ Warning**: This strategy provides no fallback. Only use when MCP is fully tested and stable.

## Configuration Reference

### Handler Types

| Handler Type | Description | Use Case |
|--------------|-------------|----------|
| `subprocess` | Traditional Claude CLI | Stable, proven, limited features |
| `mcp` | Native MCP protocol | Enhanced features, better performance |
| `hybrid` | Automatic switching | Best reliability, gradual migration |

### Configuration Parameters

#### Subprocess Configuration

```yaml
claude:
  handler_type: subprocess
  cli_path: claude                    # Path to Claude CLI
  default_args:                       # Default CLI arguments
    - --dangerously-skip-permissions
  timeout: 300                        # Command timeout in seconds
```

#### MCP Configuration

```yaml
claude:
  handler_type: mcp
  mcp_server_uri: mcp://localhost:8000  # MCP server URI
  mcp_protocol_version: "1.0"           # Protocol version
  mcp_timeout: 30                       # Connection timeout
```

#### Hybrid Configuration

```yaml
claude:
  handler_type: hybrid
  
  # Subprocess settings
  cli_path: claude
  default_args: ["--dangerously-skip-permissions"]
  timeout: 300
  
  # MCP settings
  mcp_server_uri: mcp://localhost:8000
  mcp_protocol_version: "1.0"
  mcp_timeout: 30
  
  # Hybrid behavior
  prefer_mcp: true                      # Prefer MCP over subprocess
  fallback_to_subprocess: true          # Enable fallback to subprocess
```

### Environment Variables

Override configuration with environment variables:

```bash
# Handler selection
export CLAUDE_HANDLER_TYPE=hybrid

# MCP configuration
export MCP_SERVER_URI=mcp://production-server:8000
export MCP_TIMEOUT=60

# Subprocess configuration
export CLAUDE_CLI_PATH=/usr/local/bin/claude
export CLAUDE_TIMEOUT=600
```

## Testing and Validation

### Pre-Migration Testing

```bash
# Test current configuration
claude-remote-client config validate

# Test handler availability
claude-remote-client handler test --all

# Check system requirements
claude-remote-client system check
```

### Post-Migration Testing

```bash
# Verify new handler is active
claude-remote-client handler status

# Test basic functionality
echo "Hello Claude" | claude-remote-client chat

# Test session management
claude-remote-client session create test-project
claude-remote-client session list
claude-remote-client session switch test-project

# Test error handling and fallback
claude-remote-client test fallback
```

### Performance Testing

```bash
# Benchmark handler performance
claude-remote-client benchmark --handler subprocess
claude-remote-client benchmark --handler mcp
claude-remote-client benchmark --handler hybrid

# Monitor resource usage
claude-remote-client monitor --duration 300

# Test concurrent sessions
claude-remote-client test concurrent --sessions 5
```

## Monitoring and Observability

### Health Checks

```bash
# Check overall system health
claude-remote-client health

# Check specific handler health
claude-remote-client handler health --type hybrid

# Monitor handler switching
claude-remote-client monitor handlers --real-time
```

### Metrics Collection

```bash
# View handler metrics
claude-remote-client metrics handlers

# Export metrics for analysis
claude-remote-client metrics export --format json > handler_metrics.json

# Set up continuous monitoring
claude-remote-client monitor setup --interval 60
```

### Log Analysis

```bash
# View recent logs
claude-remote-client logs --tail 100

# Filter handler-related logs
claude-remote-client logs --filter handler

# Analyze error patterns
claude-remote-client logs --errors --since "1 hour ago"
```

## Troubleshooting

### Common Issues

#### Handler Initialization Failures

**Symptoms**: Service fails to start, handler not available

**Diagnosis**:
```bash
claude-remote-client handler test --verbose
claude-remote-client logs --filter initialization
```

**Solutions**:
1. Check Claude CLI installation: `which claude`
2. Verify MCP server connectivity: `telnet mcp-server 8000`
3. Review configuration: `claude-remote-client config validate`

#### Performance Degradation

**Symptoms**: Slow response times, high resource usage

**Diagnosis**:
```bash
claude-remote-client benchmark --compare
claude-remote-client monitor --resources
```

**Solutions**:
1. Adjust timeout settings
2. Enable connection pooling
3. Optimize handler switching frequency

#### Fallback Issues

**Symptoms**: Fallback not working, stuck on failed handler

**Diagnosis**:
```bash
claude-remote-client handler status --detailed
claude-remote-client logs --filter fallback
```

**Solutions**:
1. Check fallback configuration
2. Verify backup handler availability
3. Adjust fallback cooldown period

### Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| H001 | Handler initialization failed | Check configuration and dependencies |
| H002 | Handler communication timeout | Increase timeout or check connectivity |
| H003 | Fallback handler unavailable | Verify backup handler configuration |
| H004 | Handler switching too frequent | Adjust cooldown period |

## Rollback Procedures

### Emergency Rollback

If critical issues occur:

```bash
# Stop the service
sudo systemctl stop claude-remote-client

# Restore backup configuration
cp ~/.claude-remote-client/backups/YYYYMMDD_HHMMSS/config.yaml ~/.claude-remote-client/config.yaml

# Start the service
sudo systemctl start claude-remote-client

# Verify rollback
claude-remote-client status
```

### Planned Rollback

For planned reversion to subprocess-only:

```yaml
# Update configuration
claude:
  handler_type: subprocess
  cli_path: claude
  default_args: ["--dangerously-skip-permissions"]
  timeout: 300
```

```bash
# Apply configuration
sudo systemctl reload claude-remote-client

# Verify rollback
claude-remote-client handler status
```

### Partial Rollback

Keep hybrid mode but change preferences:

```yaml
claude:
  handler_type: hybrid
  prefer_mcp: false  # Revert to subprocess preference
  fallback_to_subprocess: true
```

## Best Practices

### Configuration Management

1. **Version Control**: Store configuration in version control
2. **Environment Separation**: Use different configurations for dev/staging/prod
3. **Secrets Management**: Use environment variables for sensitive data
4. **Validation**: Always validate configuration before deployment

### Monitoring

1. **Health Checks**: Implement regular health checks
2. **Alerting**: Set up alerts for handler failures
3. **Metrics**: Collect and analyze performance metrics
4. **Logging**: Maintain detailed logs for troubleshooting

### Security

1. **Network Security**: Secure MCP server connections
2. **Authentication**: Implement proper authentication for MCP
3. **Permissions**: Use least-privilege principles
4. **Audit Trail**: Maintain audit logs for handler operations

## Advanced Configuration

### Custom Handler Development

For specialized requirements, you can develop custom handlers:

```python
from claude_remote_client.claude_client.handler_interface import ClaudeHandlerInterface

class CustomHandler(ClaudeHandlerInterface):
    async def initialize(self) -> None:
        # Custom initialization logic
        pass
    
    # Implement other required methods...

# Register custom handler
from claude_remote_client.claude_client.handler_interface import HandlerFactory
HandlerFactory.register_handler(HandlerType.CUSTOM, CustomHandler)
```

### Load Balancing

For high-availability deployments:

```yaml
claude:
  handler_type: hybrid
  
  # Multiple MCP servers for load balancing
  mcp_servers:
    - uri: mcp://server1:8000
      weight: 1
    - uri: mcp://server2:8000
      weight: 1
  
  # Load balancing strategy
  load_balancing: round_robin  # Options: round_robin, least_connections, random
```

### Connection Pooling

For improved performance:

```yaml
claude:
  handler_type: mcp
  
  # Connection pool settings
  connection_pool:
    min_connections: 2
    max_connections: 10
    idle_timeout: 300
    connection_timeout: 30
```

## Support and Resources

### Documentation

- [Configuration Reference](CONFIGURATION.md)
- [API Documentation](API_REFERENCE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Performance Tuning](PERFORMANCE_GUIDE.md)

### Community

- GitHub Issues: Report bugs and feature requests
- Discussions: Community support and questions
- Wiki: Community-maintained documentation

### Professional Support

For enterprise deployments, professional support is available including:

- Migration planning and execution
- Custom handler development
- Performance optimization
- 24/7 monitoring and support

## Conclusion

The MCP migration provides significant benefits including enhanced performance, better reliability, and future-proof architecture. The hybrid approach ensures a smooth transition with minimal risk and maximum flexibility.

Key takeaways:

1. **Start Conservative**: Begin with hybrid mode and subprocess preference
2. **Test Thoroughly**: Validate each step before proceeding
3. **Monitor Continuously**: Keep close watch on performance and errors
4. **Plan Rollback**: Always have a rollback plan ready
5. **Document Changes**: Maintain clear documentation of all changes

For additional support or questions, please refer to the documentation or contact the support team.