# Claude Remote Client - Operations Guide

This guide provides comprehensive operational procedures for managing Claude Remote Client in production environments.

## Table of Contents

1. [Service Management](#service-management)
2. [Health Monitoring](#health-monitoring)
3. [Log Management](#log-management)
4. [Performance Monitoring](#performance-monitoring)
5. [Troubleshooting](#troubleshooting)
6. [Backup and Recovery](#backup-and-recovery)
7. [Security Operations](#security-operations)
8. [Maintenance Procedures](#maintenance-procedures)
9. [Scaling Operations](#scaling-operations)
10. [Emergency Procedures](#emergency-procedures)

## Service Management

### Systemd Service Operations

```bash
# Check service status
sudo systemctl status claude-remote-client

# Start service
sudo systemctl start claude-remote-client

# Stop service
sudo systemctl stop claude-remote-client

# Restart service
sudo systemctl restart claude-remote-client

# Reload configuration (if supported)
sudo systemctl reload claude-remote-client

# Enable auto-start on boot
sudo systemctl enable claude-remote-client

# Disable auto-start
sudo systemctl disable claude-remote-client

# View service configuration
sudo systemctl cat claude-remote-client
```

### Docker Container Operations

```bash
# Check container status
docker ps -f name=claude-remote-client

# View container logs
docker logs claude-remote-client

# Follow logs in real-time
docker logs -f claude-remote-client

# Restart container
docker restart claude-remote-client

# Stop container gracefully
docker stop claude-remote-client

# Force stop container
docker kill claude-remote-client

# Update container
docker pull claude-remote-client:latest
docker stop claude-remote-client
docker rm claude-remote-client
# Run new container with same configuration

# Execute commands in container
docker exec -it claude-remote-client /bin/bash
```

### Docker Compose Operations

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart claude-remote-client

# View logs for all services
docker-compose logs

# Follow logs for specific service
docker-compose logs -f claude-remote-client

# Scale service (if configured for scaling)
docker-compose up -d --scale claude-remote-client=2

# Update services
docker-compose pull
docker-compose up -d
```

### Kubernetes Operations

```bash
# Check deployment status
kubectl get deployments -n claude-remote-client

# Check pod status
kubectl get pods -n claude-remote-client

# View pod logs
kubectl logs -f deployment/claude-remote-client -n claude-remote-client

# Scale deployment
kubectl scale deployment claude-remote-client --replicas=2 -n claude-remote-client

# Rolling update
kubectl set image deployment/claude-remote-client claude-remote-client=claude-remote-client:v1.1.0 -n claude-remote-client

# Check rollout status
kubectl rollout status deployment/claude-remote-client -n claude-remote-client

# Rollback deployment
kubectl rollout undo deployment/claude-remote-client -n claude-remote-client

# Execute commands in pod
kubectl exec -it deployment/claude-remote-client -n claude-remote-client -- /bin/bash
```

## Health Monitoring

### Health Check Endpoints

The application provides several health check endpoints for monitoring:

#### Basic Health Check
```bash
# Check overall health
curl -f http://localhost:8080/health

# Expected response (healthy):
{
  "overall_health": "healthy",
  "system": {
    "cpu_percent": {"value": 15.2, "threshold": 80.0, "healthy": true},
    "memory_percent": {"value": 45.8, "threshold": 85.0, "healthy": true},
    "disk_usage": {"value": 25.3, "threshold": 90.0, "healthy": true}
  },
  "timestamp": "2024-01-31T10:30:00Z"
}
```

#### Liveness Probe
```bash
# Kubernetes/Docker liveness check
curl -f http://localhost:8080/health/live

# Expected response:
{
  "status": "alive",
  "timestamp": "2024-01-31T10:30:00Z"
}
```

#### Readiness Probe
```bash
# Load balancer readiness check
curl -f http://localhost:8080/health/ready

# Expected response:
{
  "status": "ready",
  "checks": {
    "config_readable": {"healthy": true, "details": "Config file readable: /app/config/config.yaml"},
    "data_directory_writable": {"healthy": true, "details": "Data directory writable: /app/data"},
    "claude_cli_available": {"healthy": true, "details": "Claude CLI found at /usr/local/bin/claude"}
  },
  "timestamp": "2024-01-31T10:30:00Z"
}
```

#### Detailed Health Information
```bash
# Comprehensive health status
curl http://localhost:8080/health/detailed

# Includes application metrics, recent errors, service checks, and uptime
```

### Monitoring Integration

#### Prometheus Metrics

```bash
# Get metrics in Prometheus format
curl http://localhost:8080/metrics?format=prometheus

# Example metrics:
# claude_remote_client_info{version="1.0.0"} 1
# claude_system_cpu_percent 15.2
# claude_system_memory_percent 45.8
# claude_messages_processed_total 1250
# claude_messages_processed_rate 5.2
# claude_errors_encountered_total 3
# claude_active_sessions 2
```

#### Custom Monitoring Scripts

Create monitoring scripts for your environment:

```bash
#!/bin/bash
# health-check.sh - Custom health monitoring script

HEALTH_URL="http://localhost:8080/health"
ALERT_EMAIL="ops@yourcompany.com"

# Check health endpoint
if ! curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "CRITICAL: Claude Remote Client health check failed" | \
        mail -s "Claude Remote Client Alert" "$ALERT_EMAIL"
    exit 1
fi

# Check specific metrics
METRICS=$(curl -s "$HEALTH_URL")
CPU_USAGE=$(echo "$METRICS" | jq -r '.system.cpu_percent.value')

if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "WARNING: High CPU usage: ${CPU_USAGE}%" | \
        mail -s "Claude Remote Client CPU Alert" "$ALERT_EMAIL"
fi

echo "Health check passed - CPU: ${CPU_USAGE}%"
```

## Log Management

### Log Locations

#### Systemd Service
```bash
# View service logs
sudo journalctl -u claude-remote-client

# Follow logs in real-time
sudo journalctl -u claude-remote-client -f

# View logs from last hour
sudo journalctl -u claude-remote-client --since "1 hour ago"

# View logs with specific priority
sudo journalctl -u claude-remote-client -p err

# Export logs to file
sudo journalctl -u claude-remote-client --since "2024-01-01" > claude-logs.txt
```

#### File-based Logs
```bash
# Default log location
tail -f ~/.claude-remote-client/claude-remote-client.log

# Custom log location (if configured)
tail -f /var/log/claude-remote-client/app.log

# Rotate logs manually
logrotate -f /etc/logrotate.d/claude-remote-client
```

#### Docker Logs
```bash
# View container logs
docker logs claude-remote-client

# Follow logs with timestamps
docker logs -f -t claude-remote-client

# View last 100 lines
docker logs --tail 100 claude-remote-client

# View logs from specific time
docker logs --since "2024-01-31T10:00:00" claude-remote-client
```

### Log Analysis

#### Common Log Patterns

```bash
# Find error messages
grep -i "error\|exception\|failed" ~/.claude-remote-client/claude-remote-client.log

# Find Slack connection issues
grep -i "slack.*error\|connection.*failed" ~/.claude-remote-client/claude-remote-client.log

# Find Claude CLI issues
grep -i "claude.*error\|subprocess.*failed" ~/.claude-remote-client/claude-remote-client.log

# Find memory issues
grep -i "memory\|oom" ~/.claude-remote-client/claude-remote-client.log

# Count messages processed
grep -c "Message processed" ~/.claude-remote-client/claude-remote-client.log
```

#### Log Aggregation

For centralized logging, configure log forwarding:

```bash
# Rsyslog configuration
echo "*.* @@logserver:514" >> /etc/rsyslog.conf

# Fluentd configuration for Docker
docker run -d \
  --name fluentd \
  -p 24224:24224 \
  -v /var/log:/fluentd/log \
  fluent/fluentd:latest

# Update Docker logging driver
docker run --log-driver=fluentd --log-opt fluentd-address=localhost:24224 \
  claude-remote-client
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

Monitor these metrics for optimal performance:

1. **Response Time**: Average time to process messages
2. **Throughput**: Messages processed per minute
3. **Error Rate**: Percentage of failed operations
4. **Resource Usage**: CPU, memory, and disk utilization
5. **Session Count**: Number of active Claude sessions
6. **Queue Length**: Pending tasks in queue

### Performance Monitoring Commands

```bash
# Check system resources
htop
iostat -x 1
free -h
df -h

# Monitor network connections
netstat -tulpn | grep :8080
ss -tulpn | grep :8080

# Check process performance
ps aux | grep claude-remote-client
pstree -p $(pgrep -f claude-remote-client)

# Monitor file descriptors
lsof -p $(pgrep -f claude-remote-client)

# Check memory usage over time
while true; do
    ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem -C python
    sleep 5
done
```

### Performance Tuning

#### Memory Optimization
```yaml
# config.yaml - Reduce memory usage
max_sessions: 3          # Reduce concurrent sessions
task_queue_size: 25      # Smaller queue size
session_timeout: 900     # 15 minutes (shorter timeout)
```

#### CPU Optimization
```yaml
# config.yaml - Reduce CPU usage
claude:
  timeout: 120           # Shorter Claude timeout
  max_retries: 2         # Fewer retry attempts

monitoring:
  check_interval: 120    # Less frequent health checks
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Service Won't Start

```bash
# Check service status
sudo systemctl status claude-remote-client

# Check configuration
claude-remote-client --validate

# Check system requirements
claude-remote-client --check

# Check logs for errors
sudo journalctl -u claude-remote-client -n 50
```

#### 2. High Memory Usage

```bash
# Check memory usage
ps aux | grep claude-remote-client
free -h

# Restart service to clear memory
sudo systemctl restart claude-remote-client

# Reduce max_sessions in config
# Monitor for memory leaks
```

#### 3. Slack Connection Issues

```bash
# Test network connectivity
curl -I https://slack.com/api/auth.test

# Verify bot token
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     https://slack.com/api/auth.test

# Check firewall rules
sudo iptables -L
sudo ufw status
```

#### 4. Claude CLI Issues

```bash
# Test Claude CLI directly
claude --version
claude --help

# Check PATH
which claude
echo $PATH

# Verify permissions
ls -la $(which claude)
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Systemd service
sudo systemctl edit claude-remote-client
# Add:
# [Service]
# Environment=LOG_LEVEL=DEBUG

# Docker
docker run -e LOG_LEVEL=DEBUG claude-remote-client

# Direct execution
claude-remote-client --log-level DEBUG
```

## Backup and Recovery

### Data Backup

#### Configuration Backup
```bash
# Backup configuration
cp ~/.claude-remote-client/config.yaml config-backup-$(date +%Y%m%d).yaml

# Backup entire config directory
tar -czf claude-config-backup-$(date +%Y%m%d).tar.gz ~/.claude-remote-client/
```

#### Session Data Backup
```bash
# Backup session data
tar -czf claude-data-backup-$(date +%Y%m%d).tar.gz ~/.claude-remote-client/sessions.json

# Docker volume backup
docker run --rm -v claude-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/claude-data-backup-$(date +%Y%m%d).tar.gz -C /data .
```

#### Automated Backup Script
```bash
#!/bin/bash
# backup-claude.sh - Automated backup script

BACKUP_DIR="/opt/backups/claude-remote-client"
DATE=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration and data
tar -czf "$BACKUP_DIR/claude-backup-$DATE.tar.gz" \
    ~/.claude-remote-client/

# Clean old backups
find "$BACKUP_DIR" -name "claude-backup-*.tar.gz" \
    -mtime +$RETENTION_DAYS -delete

echo "Backup completed: claude-backup-$DATE.tar.gz"
```

### Recovery Procedures

#### Configuration Recovery
```bash
# Restore configuration
tar -xzf claude-config-backup-20240131.tar.gz -C ~/

# Verify configuration
claude-remote-client --validate

# Restart service
sudo systemctl restart claude-remote-client
```

#### Service Recovery
```bash
# Stop service
sudo systemctl stop claude-remote-client

# Restore data
tar -xzf claude-data-backup-20240131.tar.gz -C ~/.claude-remote-client/

# Fix permissions
chown -R claude-bot:claude-bot ~/.claude-remote-client/

# Start service
sudo systemctl start claude-remote-client

# Verify health
claude-remote-client --health-check
```

## Security Operations

### Security Monitoring

```bash
# Monitor failed authentication attempts
grep -i "authentication.*failed\|unauthorized" ~/.claude-remote-client/claude-remote-client.log

# Check for suspicious activity
grep -i "suspicious\|attack\|intrusion" ~/.claude-remote-client/claude-remote-client.log

# Monitor file access
auditctl -w ~/.claude-remote-client/ -p rwxa -k claude-access
ausearch -k claude-access
```

### Security Hardening

#### File Permissions
```bash
# Secure configuration files
chmod 600 ~/.claude-remote-client/config.yaml
chown claude-bot:claude-bot ~/.claude-remote-client/config.yaml

# Secure data directory
chmod 750 ~/.claude-remote-client/
chown -R claude-bot:claude-bot ~/.claude-remote-client/
```

#### Network Security
```bash
# Restrict health server access (if needed)
sudo iptables -A INPUT -p tcp --dport 8080 -s 10.0.0.0/8 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j DROP

# Monitor network connections
netstat -tulpn | grep claude
```

### Token Rotation

```bash
# Update Slack bot token
# 1. Generate new token in Slack app settings
# 2. Update configuration
sed -i 's/xoxb-old-token/xoxb-new-token/' ~/.claude-remote-client/config.yaml

# 3. Restart service
sudo systemctl restart claude-remote-client

# 4. Verify connection
curl -H "Authorization: Bearer xoxb-new-token" \
     https://slack.com/api/auth.test
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### Daily Tasks
```bash
# Check service health
claude-remote-client --health-check

# Review error logs
grep -i error ~/.claude-remote-client/claude-remote-client.log | tail -20

# Check disk space
df -h ~/.claude-remote-client/

# Monitor resource usage
ps aux | grep claude-remote-client
```

#### Weekly Tasks
```bash
# Rotate logs
logrotate -f /etc/logrotate.d/claude-remote-client

# Clean old session data
find ~/.claude-remote-client/ -name "*.tmp" -mtime +7 -delete

# Update system packages
sudo apt update && sudo apt upgrade

# Backup configuration
tar -czf claude-backup-$(date +%Y%m%d).tar.gz ~/.claude-remote-client/
```

#### Monthly Tasks
```bash
# Update Claude Remote Client
pip install --upgrade claude-remote-client

# Review and update configuration
claude-remote-client --validate

# Performance review
# - Analyze response times
# - Review error rates
# - Check resource utilization trends

# Security review
# - Rotate tokens if needed
# - Review access logs
# - Update security policies
```

### Maintenance Windows

Plan maintenance windows for:

1. **Software Updates**: Monthly updates during low-usage periods
2. **Configuration Changes**: Test in staging first
3. **Hardware Maintenance**: Coordinate with infrastructure team
4. **Security Updates**: Apply critical patches immediately

```bash
# Maintenance window procedure
# 1. Notify users
echo "Maintenance starting in 10 minutes" | \
    slack-cli send --channel general

# 2. Stop service gracefully
sudo systemctl stop claude-remote-client

# 3. Perform maintenance
# ... maintenance tasks ...

# 4. Start service
sudo systemctl start claude-remote-client

# 5. Verify health
claude-remote-client --health-check

# 6. Notify completion
echo "Maintenance completed successfully" | \
    slack-cli send --channel general
```

## Scaling Operations

### Horizontal Scaling

#### Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml claude-stack

# Scale service
docker service scale claude-stack_claude-remote-client=3

# Check service status
docker service ls
docker service ps claude-stack_claude-remote-client
```

#### Kubernetes Scaling
```bash
# Scale deployment
kubectl scale deployment claude-remote-client --replicas=3 -n claude-remote-client

# Horizontal Pod Autoscaler
kubectl autoscale deployment claude-remote-client \
    --cpu-percent=70 --min=1 --max=5 -n claude-remote-client

# Check scaling status
kubectl get hpa -n claude-remote-client
```

### Vertical Scaling

#### Resource Limits
```yaml
# docker-compose.yml
services:
  claude-remote-client:
    deploy:
      resources:
        limits:
          memory: 1G      # Increased from 512M
          cpus: '1.0'     # Increased from 0.5
        reservations:
          memory: 512M    # Increased from 256M
          cpus: '0.5'     # Increased from 0.25
```

#### Kubernetes Resources
```yaml
# deployment.yaml
resources:
  requests:
    memory: "512Mi"    # Increased from 256Mi
    cpu: "500m"        # Increased from 250m
  limits:
    memory: "1Gi"      # Increased from 512Mi
    cpu: "1000m"       # Increased from 500m
```

## Emergency Procedures

### Service Outage Response

#### Immediate Response (0-5 minutes)
1. **Assess Impact**: Check health endpoints and logs
2. **Quick Fix Attempts**: Restart service, check basic connectivity
3. **Escalation**: Alert on-call engineer if quick fixes fail

```bash
# Emergency restart
sudo systemctl restart claude-remote-client

# Quick health check
curl -f http://localhost:8080/health || echo "Health check failed"

# Check critical logs
tail -50 ~/.claude-remote-client/claude-remote-client.log | grep -i error
```

#### Short-term Response (5-30 minutes)
1. **Root Cause Analysis**: Analyze logs and metrics
2. **Temporary Workarounds**: Implement if possible
3. **Communication**: Update stakeholders

```bash
# Detailed diagnostics
claude-remote-client --health-check
systemctl status claude-remote-client
journalctl -u claude-remote-client --since "30 minutes ago"

# Resource check
free -h
df -h
ps aux | grep claude
```

#### Long-term Response (30+ minutes)
1. **Permanent Fix**: Implement proper solution
2. **Testing**: Verify fix in staging environment
3. **Post-mortem**: Document incident and lessons learned

### Disaster Recovery

#### Complete System Failure
```bash
# 1. Restore from backup
tar -xzf claude-backup-latest.tar.gz -C ~/

# 2. Reinstall if necessary
pip install claude-remote-client

# 3. Restore configuration
cp backup/config.yaml ~/.claude-remote-client/

# 4. Start service
sudo systemctl start claude-remote-client

# 5. Verify functionality
claude-remote-client --health-check
```

#### Data Corruption
```bash
# 1. Stop service immediately
sudo systemctl stop claude-remote-client

# 2. Backup corrupted data
mv ~/.claude-remote-client/sessions.json ~/.claude-remote-client/sessions.json.corrupted

# 3. Restore from backup
cp backup/sessions.json ~/.claude-remote-client/

# 4. Start service
sudo systemctl start claude-remote-client

# 5. Verify data integrity
# Check that sessions are restored correctly
```

### Contact Information

Maintain an emergency contact list:

- **Primary On-call**: [phone] [email]
- **Secondary On-call**: [phone] [email]
- **Infrastructure Team**: [email]
- **Security Team**: [email]
- **Management**: [email]

### Escalation Matrix

1. **Level 1**: Service restart, basic troubleshooting (0-15 min)
2. **Level 2**: Advanced troubleshooting, temporary fixes (15-60 min)
3. **Level 3**: Architecture changes, vendor support (1+ hours)

---

**Remember**: Always test procedures in a staging environment before applying to production!

For additional operational support, consult the [Troubleshooting Guide](TROUBLESHOOTING.md) and [Deployment Guide](DEPLOYMENT_GUIDE.md).