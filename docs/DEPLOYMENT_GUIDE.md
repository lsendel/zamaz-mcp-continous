# Claude Remote Client - Deployment Guide

This guide provides comprehensive instructions for deploying Claude Remote Client in various environments, from development to production.

## Deployment Options Overview

Claude Remote Client supports multiple deployment methods:

1. **[Local Development](#local-development)** - Direct Python execution
2. **[Systemd Service](#systemd-service)** - Linux system service
3. **[Docker Container](#docker-deployment)** - Containerized deployment
4. **[Docker Compose](#docker-compose-deployment)** - Multi-service deployment
5. **[Kubernetes](#kubernetes-deployment)** - Container orchestration
6. **[Cloud Deployment](#cloud-deployment)** - AWS, GCP, Azure

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+), macOS, Windows
- **Python**: 3.9+ (3.11+ recommended)
- **Memory**: 512MB minimum, 1GB recommended
- **Storage**: 1GB free space minimum
- **Network**: Internet access for Slack API

### Dependencies
- **Claude CLI**: Installed and accessible in PATH
- **Slack Bot Token**: With appropriate permissions
- **Configuration**: Valid config.yaml file

## Local Development

### Quick Start

```bash
# Install from PyPI
pip install claude-remote-client

# Run setup wizard
claude-remote-client --setup

# Start the application
claude-remote-client
```

### Development Installation

```bash
# Clone repository
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Start with debug logging
claude-remote-client --log-level DEBUG
```

## Systemd Service

### Installation

1. **Create service user:**
   ```bash
   sudo useradd --system --shell /bin/false --home /var/lib/claude-remote-client claude-bot
   sudo mkdir -p /var/lib/claude-remote-client
   sudo chown claude-bot:claude-bot /var/lib/claude-remote-client
   ```

2. **Install application:**
   ```bash
   sudo pip install claude-remote-client
   ```

3. **Create configuration directory:**
   ```bash
   sudo mkdir -p /etc/claude-remote-client
   sudo cp claude-remote-client.example.yaml /etc/claude-remote-client/config.yaml
   sudo chown -R claude-bot:claude-bot /etc/claude-remote-client
   sudo chmod 600 /etc/claude-remote-client/config.yaml
   ```

4. **Install systemd service:**
   ```bash
   sudo cp systemd/claude-remote-client.service /etc/systemd/system/
   sudo cp systemd/claude-remote-client-maintenance.service /etc/systemd/system/
   sudo cp systemd/claude-remote-client-maintenance.timer /etc/systemd/system/
   sudo cp scripts/claude-remote-client-maintenance /usr/local/bin/
   sudo chmod +x /usr/local/bin/claude-remote-client-maintenance
   ```

5. **Enable and start services:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable claude-remote-client
   sudo systemctl enable claude-remote-client-maintenance.timer
   sudo systemctl start claude-remote-client
   sudo systemctl start claude-remote-client-maintenance.timer
   ```

### Configuration

Edit `/etc/claude-remote-client/config.yaml`:

```yaml
slack:
  bot_token: "xoxb-your-bot-token"
  channel_id: "C1234567890"
  signing_secret: "your-signing-secret"

claude:
  cli_path: "/usr/local/bin/claude"
  default_args:
    - "--dangerously-skip-permissions"
  timeout: 300

projects:
  - name: "production-app"
    path: "/opt/applications/production-app"
    description: "Production application"

log_level: "INFO"
data_dir: "/var/lib/claude-remote-client"
max_sessions: 5
task_queue_size: 50
```

### Environment Variables

Create `/etc/claude-remote-client/environment`:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_CHANNEL_ID=C1234567890
SLACK_SIGNING_SECRET=your-signing-secret
CLAUDE_CLI_PATH=/usr/local/bin/claude
LOG_LEVEL=INFO
```

### Management Commands

```bash
# Check status
sudo systemctl status claude-remote-client

# View logs
sudo journalctl -u claude-remote-client -f

# Restart service
sudo systemctl restart claude-remote-client

# Stop service
sudo systemctl stop claude-remote-client

# Check maintenance timer
sudo systemctl status claude-remote-client-maintenance.timer

# Run maintenance manually
sudo systemctl start claude-remote-client-maintenance
```

## Docker Deployment

### Basic Docker Run

```bash
# Build image
docker build -t claude-remote-client .

# Run container
docker run -d \
  --name claude-remote-client \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_CHANNEL_ID=C1234567890 \
  -v $(pwd)/config.yaml:/app/config/config.yaml:ro \
  -v $(pwd)/projects:/projects:rw \
  --restart unless-stopped \
  claude-remote-client
```

### Docker with Volume Mounts

```bash
# Create volumes
docker volume create claude-data
docker volume create claude-logs

# Run with persistent storage
docker run -d \
  --name claude-remote-client \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_CHANNEL_ID=C1234567890 \
  -v $(pwd)/config.yaml:/app/config/config.yaml:ro \
  -v $(pwd)/projects:/projects:rw \
  -v claude-data:/app/data \
  -v claude-logs:/app/logs \
  --restart unless-stopped \
  --health-cmd="/app/healthcheck.sh" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  claude-remote-client
```

### Docker Management

```bash
# Check container status
docker ps
docker logs claude-remote-client

# Check health
docker inspect --format='{{.State.Health.Status}}' claude-remote-client

# Update container
docker pull claude-remote-client:latest
docker stop claude-remote-client
docker rm claude-remote-client
# Run new container with same configuration

# Backup data
docker run --rm -v claude-data:/data -v $(pwd):/backup alpine tar czf /backup/claude-data-backup.tar.gz -C /data .
```

## Docker Compose Deployment

### Basic Setup

1. **Create project directory:**
   ```bash
   mkdir claude-remote-client-deploy
   cd claude-remote-client-deploy
   ```

2. **Create environment file:**
   ```bash
   cat > .env << EOF
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_CHANNEL_ID=C1234567890
   SLACK_SIGNING_SECRET=your-signing-secret
   LOG_LEVEL=INFO
   MAX_SESSIONS=10
   PROJECTS_DIR=./projects
   VERSION=latest
   EOF
   ```

3. **Create configuration:**
   ```bash
   cp claude-remote-client.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

4. **Create projects directory:**
   ```bash
   mkdir -p projects/web-app
   mkdir -p projects/api-service
   ```

5. **Deploy:**
   ```bash
   docker-compose up -d
   ```

### Production Setup with Monitoring

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  claude-remote-client:
    image: claude-remote-client:latest
    container_name: claude-remote-client
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_CHANNEL_ID=${SLACK_CHANNEL_ID}
      - SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./config.yaml:/app/config/config.yaml:ro
      - ./projects:/projects:rw
      - claude-data:/app/data
      - claude-logs:/app/logs
    networks:
      - claude-network
    restart: unless-stopped
    healthcheck:
      test: ["/app/healthcheck.sh"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    image: redis:7-alpine
    container_name: claude-redis
    command: redis-server --appendonly yes --maxmemory 128mb
    volumes:
      - redis-data:/data
    networks:
      - claude-network
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: claude-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - claude-network
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: claude-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - claude-network
    restart: unless-stopped

networks:
  claude-network:
    driver: bridge

volumes:
  claude-data:
  claude-logs:
  redis-data:
  prometheus-data:
  grafana-data:
```

Deploy production setup:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Kubernetes Deployment

### Basic Deployment

1. **Create namespace:**
   ```bash
   kubectl create namespace claude-remote-client
   ```

2. **Create secrets:**
   ```bash
   kubectl create secret generic claude-secrets \
     --from-literal=slack-bot-token=xoxb-your-token \
     --from-literal=slack-channel-id=C1234567890 \
     --from-literal=slack-signing-secret=your-secret \
     -n claude-remote-client
   ```

3. **Create config map:**
   ```bash
   kubectl create configmap claude-config \
     --from-file=config.yaml \
     -n claude-remote-client
   ```

4. **Deploy application:**
   ```yaml
   # claude-deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: claude-remote-client
     namespace: claude-remote-client
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
             valueFrom:
               secretKeyRef:
                 name: claude-secrets
                 key: slack-channel-id
           - name: SLACK_SIGNING_SECRET
             valueFrom:
               secretKeyRef:
                 name: claude-secrets
                 key: slack-signing-secret
           volumeMounts:
           - name: config
             mountPath: /app/config/config.yaml
             subPath: config.yaml
           - name: data
             mountPath: /app/data
           - name: projects
             mountPath: /projects
           resources:
             requests:
               memory: "256Mi"
               cpu: "250m"
             limits:
               memory: "512Mi"
               cpu: "500m"
           livenessProbe:
             exec:
               command: ["/app/healthcheck.sh"]
             initialDelaySeconds: 30
             periodSeconds: 30
           readinessProbe:
             exec:
               command: ["/app/healthcheck.sh"]
             initialDelaySeconds: 5
             periodSeconds: 10
         volumes:
         - name: config
           configMap:
             name: claude-config
         - name: data
           persistentVolumeClaim:
             claimName: claude-data-pvc
         - name: projects
           persistentVolumeClaim:
             claimName: claude-projects-pvc
   ---
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: claude-data-pvc
     namespace: claude-remote-client
   spec:
     accessModes:
       - ReadWriteOnce
     resources:
       requests:
         storage: 1Gi
   ---
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: claude-projects-pvc
     namespace: claude-remote-client
   spec:
     accessModes:
       - ReadWriteMany
     resources:
       requests:
         storage: 10Gi
   ```

5. **Apply deployment:**
   ```bash
   kubectl apply -f claude-deployment.yaml
   ```

### Kubernetes Management

```bash
# Check deployment status
kubectl get deployments -n claude-remote-client

# Check pods
kubectl get pods -n claude-remote-client

# View logs
kubectl logs -f deployment/claude-remote-client -n claude-remote-client

# Scale deployment
kubectl scale deployment claude-remote-client --replicas=2 -n claude-remote-client

# Update deployment
kubectl set image deployment/claude-remote-client claude-remote-client=claude-remote-client:v1.1.0 -n claude-remote-client

# Check health
kubectl describe pod -l app=claude-remote-client -n claude-remote-client
```

## Cloud Deployment

### AWS ECS

1. **Create task definition:**
   ```json
   {
     "family": "claude-remote-client",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "256",
     "memory": "512",
     "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
     "containerDefinitions": [
       {
         "name": "claude-remote-client",
         "image": "your-account.dkr.ecr.region.amazonaws.com/claude-remote-client:latest",
         "essential": true,
         "environment": [
           {"name": "LOG_LEVEL", "value": "INFO"}
         ],
         "secrets": [
           {"name": "SLACK_BOT_TOKEN", "valueFrom": "arn:aws:secretsmanager:region:account:secret:claude/slack-token"},
           {"name": "SLACK_CHANNEL_ID", "valueFrom": "arn:aws:secretsmanager:region:account:secret:claude/channel-id"}
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/claude-remote-client",
             "awslogs-region": "us-west-2",
             "awslogs-stream-prefix": "ecs"
           }
         },
         "healthCheck": {
           "command": ["/app/healthcheck.sh"],
           "interval": 30,
           "timeout": 5,
           "retries": 3
         }
       }
     ]
   }
   ```

2. **Create service:**
   ```bash
   aws ecs create-service \
     --cluster claude-cluster \
     --service-name claude-remote-client \
     --task-definition claude-remote-client:1 \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
   ```

### Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT-ID/claude-remote-client

# Deploy to Cloud Run
gcloud run deploy claude-remote-client \
  --image gcr.io/PROJECT-ID/claude-remote-client \
  --platform managed \
  --region us-central1 \
  --set-env-vars LOG_LEVEL=INFO \
  --set-secrets SLACK_BOT_TOKEN=claude-slack-token:latest \
  --set-secrets SLACK_CHANNEL_ID=claude-channel-id:latest \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 1 \
  --no-allow-unauthenticated
```

### Azure Container Instances

```bash
# Create resource group
az group create --name claude-rg --location eastus

# Create container instance
az container create \
  --resource-group claude-rg \
  --name claude-remote-client \
  --image claude-remote-client:latest \
  --cpu 1 \
  --memory 1 \
  --restart-policy Always \
  --environment-variables LOG_LEVEL=INFO \
  --secure-environment-variables SLACK_BOT_TOKEN=xoxb-your-token SLACK_CHANNEL_ID=C1234567890
```

## Monitoring and Observability

### Health Checks

The application provides multiple health check endpoints for different deployment scenarios:

#### Built-in Health Checks

```bash
# CLI health check
claude-remote-client --health-check

# Dry-run test (validates without connecting to Slack)
claude-remote-client --dry-run

# System requirements check
claude-remote-client --check
```

#### HTTP Health Endpoints

When running, the application exposes health check endpoints on port 8080 (configurable):

```bash
# Basic health check
curl http://localhost:8080/health

# Liveness probe (for container orchestrators)
curl http://localhost:8080/health/live

# Readiness probe (for load balancers)
curl http://localhost:8080/health/ready

# Detailed health information
curl http://localhost:8080/health/detailed

# Application metrics
curl http://localhost:8080/metrics

# Prometheus format metrics
curl http://localhost:8080/metrics?format=prometheus

# Service status
curl http://localhost:8080/status

# Version information
curl http://localhost:8080/version
```

#### Container Health Checks

```bash
# Docker health check
docker exec claude-remote-client /app/healthcheck.sh

# Check container health status
docker inspect --format='{{.State.Health.Status}}' claude-remote-client

# Kubernetes health check
kubectl exec deployment/claude-remote-client -- /app/healthcheck.sh

# Check pod health
kubectl describe pod -l app=claude-remote-client -n claude-remote-client
```

#### Health Check Configuration

Configure health check port in your configuration file:

```yaml
# config.yaml
health_port: 8080  # Default port for health endpoints
```

Or via command line:

```bash
# Custom health port
claude-remote-client --health-port 9090

# Disable health server
claude-remote-client --no-health-server
```

### Logging

```bash
# Local logs
tail -f ~/.claude-remote-client/claude-remote-client.log

# Systemd logs
journalctl -u claude-remote-client -f

# Docker logs
docker logs -f claude-remote-client

# Kubernetes logs
kubectl logs -f deployment/claude-remote-client -n claude-remote-client
```

### Metrics Collection

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'claude-remote-client'
    static_configs:
      - targets: ['claude-remote-client:8080']
    metrics_path: /metrics
    scrape_interval: 30s
```

### Alerting

Example Prometheus alerts:

```yaml
groups:
  - name: claude-remote-client
    rules:
      - alert: ClaudeRemoteClientDown
        expr: up{job="claude-remote-client"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Claude Remote Client is down"
          
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes{job="claude-remote-client"} > 500000000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
```

## Security Considerations

### Production Security

1. **Use secrets management:**
   ```bash
   # Kubernetes secrets
   kubectl create secret generic claude-secrets --from-literal=token=xoxb-...
   
   # Docker secrets
   echo "xoxb-your-token" | docker secret create slack_token -
   
   # AWS Secrets Manager
   aws secretsmanager create-secret --name claude/slack-token --secret-string "xoxb-your-token"
   ```

2. **Network security:**
   ```yaml
   # Docker network isolation
   networks:
     claude-internal:
       driver: bridge
       internal: true
   ```

3. **File permissions:**
   ```bash
   # Restrict config file access
   chmod 600 /etc/claude-remote-client/config.yaml
   chown claude-bot:claude-bot /etc/claude-remote-client/config.yaml
   ```

4. **Container security:**
   ```dockerfile
   # Run as non-root user
   USER 1000:1000
   
   # Security options
   --security-opt no-new-privileges:true
   --read-only
   --tmpfs /tmp
   ```

## Backup and Recovery

### Data Backup

```bash
# Local backup
tar -czf claude-backup-$(date +%Y%m%d).tar.gz ~/.claude-remote-client/

# Docker volume backup
docker run --rm -v claude-data:/data -v $(pwd):/backup alpine tar czf /backup/claude-data-backup.tar.gz -C /data .

# Kubernetes backup
kubectl exec deployment/claude-remote-client -- tar czf - /app/data | gzip > claude-k8s-backup.tar.gz
```

### Configuration Backup

```bash
# Backup configuration
cp /etc/claude-remote-client/config.yaml config-backup-$(date +%Y%m%d).yaml

# Version control
git add config.yaml
git commit -m "Update configuration"
git push
```

### Recovery Procedures

```bash
# Restore from backup
tar -xzf claude-backup-20240131.tar.gz -C ~/

# Restore Docker volume
docker run --rm -v claude-data:/data -v $(pwd):/backup alpine tar xzf /backup/claude-data-backup.tar.gz -C /data

# Restart services
systemctl restart claude-remote-client
# or
docker-compose restart
# or
kubectl rollout restart deployment/claude-remote-client
```

## Troubleshooting Deployment Issues

### Common Problems

1. **Permission denied errors:**
   ```bash
   # Fix file permissions
   sudo chown -R claude-bot:claude-bot /var/lib/claude-remote-client
   sudo chmod 755 /var/lib/claude-remote-client
   sudo chmod 600 /etc/claude-remote-client/config.yaml
   ```

2. **Network connectivity issues:**
   ```bash
   # Test network connectivity
   curl -I https://slack.com/api/auth.test
   
   # Check DNS resolution
   nslookup slack.com
   
   # Test from container
   docker exec claude-remote-client curl -I https://slack.com/api/auth.test
   ```

3. **Resource constraints:**
   ```bash
   # Check memory usage
   free -h
   docker stats claude-remote-client
   kubectl top pods -n claude-remote-client
   
   # Check disk space
   df -h
   docker system df
   ```

4. **Configuration issues:**
   ```bash
   # Validate configuration
   claude-remote-client --validate
   
   # Test dry run
   claude-remote-client --dry-run
   
   # Check health
   claude-remote-client --health-check
   ```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
claude-remote-client

# Docker debug
docker run -e LOG_LEVEL=DEBUG claude-remote-client

# Kubernetes debug
kubectl set env deployment/claude-remote-client LOG_LEVEL=DEBUG -n claude-remote-client
```

## Performance Optimization

### Resource Tuning

```yaml
# Docker resource limits
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

### Configuration Optimization

```yaml
# Optimize for production
max_sessions: 5          # Reduce for lower memory usage
task_queue_size: 50      # Reduce queue size
session_timeout: 1800    # 30 minutes
reconnect_attempts: 3    # Reduce retry attempts
```

### Scaling Considerations

- **Horizontal scaling**: Deploy multiple instances with load balancing
- **Vertical scaling**: Increase CPU/memory resources
- **Database scaling**: Use external Redis for session storage
- **Monitoring**: Implement comprehensive monitoring and alerting

---

**Your Claude Remote Client is now ready for production deployment! 🚀**

For additional help with deployment issues, consult the [Troubleshooting Guide](TROUBLESHOOTING.md) or reach out to the community.