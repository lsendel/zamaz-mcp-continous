# Claude Remote Client Docker Image
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-enhanced.txt ./

# Install Python dependencies
RUN pip install --user --no-warn-script-location -r requirements-enhanced.txt

# Copy application code
COPY . .

# Install the application
RUN pip install --user --no-warn-script-location .

# Production stage
FROM python:3.11-slim as production

# Set labels for metadata
LABEL maintainer="Claude Remote Client Team <support@claude-remote-client.com>" \
      org.label-schema.name="claude-remote-client" \
      org.label-schema.description="Remote Claude AI interaction through Slack" \
      org.label-schema.url="https://github.com/your-org/claude-remote-client" \
      org.label-schema.vcs-url="https://github.com/your-org/claude-remote-client" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.version=$VERSION \
      org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.schema-version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    CLAUDE_REMOTE_CLIENT_CONFIG="/app/config/config.yaml" \
    CLAUDE_REMOTE_CLIENT_DATA_DIR="/app/data"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create application directories
RUN mkdir -p /app/config /app/data /app/logs \
    && chown -R appuser:appuser /app

# Copy Python packages from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application files
COPY --chown=appuser:appuser claude-remote-client.example.yaml /app/config/
COPY --chown=appuser:appuser docs/ /app/docs/
COPY --chown=appuser:appuser scripts/ /app/scripts/

# Create comprehensive health check script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Function to log health check messages\n\
log_health() {\n\
    echo "[HEALTH] $(date +"%Y-%m-%d %H:%M:%S") - $1"\n\
}\n\
\n\
# Check if the application is responsive\n\
log_health "Checking application import..."\n\
if ! python -c "import claude_remote_client; print(\"OK\")" > /dev/null 2>&1; then\n\
    log_health "ERROR: Application import failed"\n\
    exit 1\n\
fi\n\
\n\
# Check if config file exists and is readable\n\
log_health "Checking configuration file..."\n\
if [ ! -r "$CLAUDE_REMOTE_CLIENT_CONFIG" ]; then\n\
    log_health "ERROR: Config file not found or not readable: $CLAUDE_REMOTE_CLIENT_CONFIG"\n\
    exit 1\n\
fi\n\
\n\
# Check if data directory is writable\n\
log_health "Checking data directory..."\n\
if [ ! -w "$CLAUDE_REMOTE_CLIENT_DATA_DIR" ]; then\n\
    log_health "ERROR: Data directory not writable: $CLAUDE_REMOTE_CLIENT_DATA_DIR"\n\
    exit 1\n\
fi\n\
\n\
# Check if Claude CLI is available\n\
log_health "Checking Claude CLI availability..."\n\
if ! command -v claude >/dev/null 2>&1; then\n\
    log_health "WARNING: Claude CLI not found in PATH"\n\
fi\n\
\n\
# Check memory usage\n\
log_health "Checking memory usage..."\n\
if command -v free >/dev/null 2>&1; then\n\
    MEMORY_USAGE=$(free | grep Mem | awk "{print (\$3/\$2) * 100.0}")\n\
    if (( $(echo "$MEMORY_USAGE > 90" | bc -l) )); then\n\
        log_health "WARNING: High memory usage: ${MEMORY_USAGE}%"\n\
    fi\n\
fi\n\
\n\
# Check disk space\n\
log_health "Checking disk space..."\n\
DISK_USAGE=$(df "$CLAUDE_REMOTE_CLIENT_DATA_DIR" | tail -1 | awk "{print \$5}" | sed "s/%//")\n\
if [ "$DISK_USAGE" -gt 85 ]; then\n\
    log_health "WARNING: High disk usage: ${DISK_USAGE}%"\n\
fi\n\
\n\
# Test basic application functionality\n\
log_health "Testing application health endpoint..."\n\
if ! python -c "\n\
import sys\n\
sys.path.insert(0, \"/home/appuser/.local/lib/python3.11/site-packages\")\n\
try:\n\
    from claude_remote_client.monitoring import health_monitor\n\
    print(\"Health monitoring available\")\n\
except ImportError:\n\
    print(\"Health monitoring not available\")\n\
" > /dev/null 2>&1; then\n\
    log_health "WARNING: Health monitoring module not available"\n\
fi\n\
\n\
log_health "Health check passed successfully"\n\
exit 0' > /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh \
    && chown appuser:appuser /app/healthcheck.sh

# Switch to app user
USER appuser

# Set work directory
WORKDIR /app

# Expose port for health checks (if needed)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# Default command
CMD ["claude-remote-client", "--config", "/app/config/config.yaml", "--log-level", "INFO"]

# Add entrypoint script for initialization
COPY --chown=appuser:appuser <<EOF /app/entrypoint.sh
#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Initialize configuration if not exists
if [ ! -f "/app/config/config.yaml" ]; then
    log "No configuration found, copying example config..."
    cp /app/config/claude-remote-client.example.yaml /app/config/config.yaml
    log "Please mount your configuration file to /app/config/config.yaml"
fi

# Ensure data directory exists
mkdir -p "$CLAUDE_REMOTE_CLIENT_DATA_DIR"

# Validate environment variables
if [ -z "$SLACK_BOT_TOKEN" ]; then
    log "WARNING: SLACK_BOT_TOKEN environment variable not set"
fi

if [ -z "$SLACK_CHANNEL_ID" ]; then
    log "WARNING: SLACK_CHANNEL_ID environment variable not set"
fi

# Check if Claude CLI is available (if mounted)
if command -v claude >/dev/null 2>&1; then
    log "Claude CLI found: $(claude --version 2>/dev/null || echo 'version unknown')"
else
    log "WARNING: Claude CLI not found in PATH. Please ensure it's available in the container."
fi

# Run the main application
log "Starting Claude Remote Client..."
exec "$@"
EOF

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]