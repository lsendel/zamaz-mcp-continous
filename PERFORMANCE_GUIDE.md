# Performance and Scalability Guide

This guide covers the performance optimizations and scalability features implemented in Claude Remote Client.

## Overview

The enhanced version includes several performance optimizations:

- **Enhanced Logging**: Structured logging with performance metrics
- **Caching Systems**: LRU caches for sessions and responses
- **Connection Pooling**: Efficient resource management
- **Rate Limiting**: API call throttling
- **Memory Optimization**: Automatic cleanup and optimization
- **Batch Processing**: Efficient bulk operations
- **Performance Monitoring**: Real-time metrics and reporting

## Configuration

### Enhanced Configuration File

Create an enhanced configuration file with performance settings:

```yaml
# Enhanced Claude Remote Client Configuration

slack:
  bot_token: 'xoxb-your-bot-token'
  channel_id: 'C1234567890'
  signing_secret: 'your-signing-secret'

claude:
  cli_path: 'claude'
  default_args:
    - '--dangerously-skip-permissions'
  timeout: 300

projects:
  - name: 'my-project'
    path: '/path/to/my-project'
    description: 'My main project'

# Performance Configuration
performance:
  enable_connection_pooling: true
  connection_pool_size: 10
  connection_pool_min_size: 2
  connection_pool_max_idle_time: 300
  
  enable_rate_limiting: true
  claude_api_rate_limit: 10.0  # requests per second
  claude_api_burst_limit: 20
  
  enable_batch_processing: true
  batch_size: 100
  batch_max_wait_time: 1.0
  
  enable_memory_optimization: true
  memory_optimization_interval: 600
  max_conversation_history: 100
  
  enable_metrics_collection: true
  metrics_report_interval: 300

# Caching Configuration
caching:
  session_cache_size: 1000
  session_cache_ttl: 3600
  response_cache_size: 1000
  response_cache_ttl: 300
  enable_response_caching: true
  cache_cleanup_interval: 300

# Enhanced Logging Configuration
logging:
  level: 'INFO'
  console_enabled: true
  console_structured: false
  
  file_enabled: true
  file_path: '~/.claude-remote-client/logs/app.log'
  file_structured: true
  file_max_bytes: 10485760  # 10MB
  file_backup_count: 5
  
  error_file_enabled: true
  error_file_path: '~/.claude-remote-client/logs/errors.log'
  error_file_max_bytes: 5242880  # 5MB
  error_file_backup_count: 3
  
  performance_logging_enabled: true
  performance_log_path: '~/.claude-remote-client/logs/performance.log'
  
  enable_async_logging: true
  async_queue_size: 1000

# Security Configuration
security:
  enable_input_sanitization: true
  max_message_length: 10000
  max_conversation_history_size: 1000
  enable_rate_limiting_per_user: true
  user_rate_limit: 5.0
  
  require_ssl: true
  verify_ssl_certificates: true
  
  session_timeout: 3600
  max_idle_time: 1800

# Monitoring Configuration
monitoring:
  enable_health_checks: true
  health_check_interval: 60
  
  enable_metrics_export: true
  metrics_export_interval: 300
  metrics_export_format: 'json'
  
  enable_alerting: false
  alert_thresholds:
    memory_usage_mb: 1000
    cpu_usage_percent: 80
    error_rate_percent: 5
    response_time_seconds: 10

# Feature Flags
feature_flags:
  enable_enhanced_session_manager: true
  enable_performance_optimizations: true
  enable_advanced_logging: true
  enable_monitoring: true

log_level: 'INFO'
data_dir: '~/.claude-remote-client'
max_sessions: 10
task_queue_size: 100
```

## Usage Examples

### Using Enhanced Session Manager

```python
from claude_remote_client.enhanced_config import load_enhanced_config
from claude_remote_client.session_manager.enhanced_session_manager import EnhancedSessionManager

# Load enhanced configuration
config = load_enhanced_config()

# Create enhanced session manager
session_manager = EnhancedSessionManager(config)
await session_manager.start()

# Create session with caching
session = await session_manager.create_session("my-project")

# Send message with response caching
response = await session_manager.send_message(
    session.session_id, 
    "Analyze this code",
    use_cache=True,
    cache_response=True
)

# Get performance metrics
metrics = await session_manager.get_session_metrics()
print(f"Cache hit rate: {metrics['caching']['response_cache']['hit_rate']:.2%}")

# Optimize memory usage
optimization_stats = await session_manager.optimize_memory_usage()
print(f"Memory saved: {optimization_stats['memory_usage']['saved_bytes'] / 1024 / 1024:.2f} MB")

await session_manager.stop()
```

### Using Performance Utilities

```python
from claude_remote_client.performance import LRUCache, RateLimiter, BatchProcessor

# LRU Cache usage
cache = LRUCache[str](max_size=1000, default_ttl=300)
await cache.set("key", "value")
value = await cache.get("key")

# Rate limiter usage
rate_limiter = RateLimiter(rate=10.0, burst=20)
if await rate_limiter.acquire():
    # Make API call
    pass
else:
    # Wait for tokens
    await rate_limiter.wait_for_tokens()

# Batch processor usage
async def process_batch(items):
    # Process items in batch
    print(f"Processing {len(items)} items")

processor = BatchProcessor(process_batch, batch_size=100)
await processor.start()

for i in range(1000):
    await processor.add_item(f"item_{i}")

await processor.stop()
```

### Enhanced Logging

```python
from claude_remote_client.logging_config import setup_enhanced_logging, performance_monitor

# Setup enhanced logging
config = {
    'level': 'INFO',
    'console': {'enabled': True, 'structured': False},
    'file': {
        'enabled': True,
        'path': '/path/to/app.log',
        'structured': True
    }
}

logger = setup_enhanced_logging(config)

# Use performance monitoring decorator
@performance_monitor("my_operation")
async def my_async_function():
    # Your code here
    pass

# Log with context
logger.log_with_context(
    logging.INFO,
    "User action performed",
    user_id="user123",
    action="create_session",
    project="my-project"
)

# Log API calls
logger.log_api_call(
    service="claude",
    method="send_message",
    duration=1.23,
    status="success",
    session_id="session123"
)
```

## Performance Monitoring

### Metrics Collection

The system automatically collects various performance metrics:

- **Response Times**: API call durations
- **Cache Performance**: Hit rates and efficiency
- **Memory Usage**: Session and cache memory consumption
- **Error Rates**: Failed operations and exceptions
- **Throughput**: Messages processed per second

### Health Checks

```python
# Get comprehensive health status
health_status = await session_manager.health_check()

print(f"Overall status: {health_status['status']}")
print(f"Session manager: {health_status['components']['session_manager']['status']}")
print(f"Cache hit rate: {health_status['components']['caching']['session_cache']['hit_rate']:.2%}")
```

### Performance Benchmarks

Run performance tests to validate system performance:

```bash
# Run performance tests
pytest tests/test_performance.py -m performance -v

# Run specific performance test
pytest tests/test_performance.py::TestSessionManagerPerformance::test_concurrent_session_creation -v

# Run with benchmarking
pytest tests/test_performance.py --benchmark-only
```

## Optimization Tips

### Memory Optimization

1. **Configure conversation history limits**:
   ```yaml
   performance:
     max_conversation_history: 100
   ```

2. **Enable automatic memory optimization**:
   ```yaml
   performance:
     enable_memory_optimization: true
     memory_optimization_interval: 600
   ```

3. **Monitor memory usage**:
   ```python
   stats = await session_manager.optimize_memory_usage()
   print(f"Memory saved: {stats['memory_usage']['savings_percentage']:.1f}%")
   ```

### Cache Optimization

1. **Tune cache sizes based on usage**:
   ```yaml
   caching:
     session_cache_size: 1000  # Adjust based on concurrent sessions
     response_cache_size: 1000  # Adjust based on response patterns
   ```

2. **Configure TTL values**:
   ```yaml
   caching:
     session_cache_ttl: 3600    # 1 hour
     response_cache_ttl: 300    # 5 minutes
   ```

3. **Monitor cache performance**:
   ```python
   cache_stats = await session_manager.session_cache.get_stats()
   if cache_stats['hit_rate'] < 0.8:
       # Consider increasing cache size or TTL
   ```

### Rate Limiting

1. **Configure appropriate limits**:
   ```yaml
   performance:
     claude_api_rate_limit: 10.0  # Requests per second
     claude_api_burst_limit: 20   # Burst capacity
   ```

2. **Monitor rate limiting**:
   ```python
   # Check if rate limited
   if not await rate_limiter.acquire():
       await rate_limiter.wait_for_tokens()
   ```

### Connection Pooling

1. **Configure pool sizes**:
   ```yaml
   performance:
     connection_pool_size: 10      # Maximum connections
     connection_pool_min_size: 2   # Minimum connections
     connection_pool_max_idle_time: 300  # 5 minutes
   ```

2. **Use connection pool**:
   ```python
   async with session_manager.process_pool.get_connection() as conn:
       # Use connection
       pass
   ```

## Troubleshooting

### Performance Issues

1. **High Memory Usage**:
   - Check conversation history sizes
   - Run memory optimization
   - Reduce cache sizes if needed

2. **Slow Response Times**:
   - Check rate limiting settings
   - Monitor cache hit rates
   - Verify connection pool configuration

3. **High CPU Usage**:
   - Enable async logging
   - Increase batch processing sizes
   - Check for inefficient operations

### Monitoring and Alerts

1. **Enable comprehensive monitoring**:
   ```yaml
   monitoring:
     enable_health_checks: true
     enable_metrics_export: true
     enable_alerting: true
   ```

2. **Set appropriate thresholds**:
   ```yaml
   monitoring:
     alert_thresholds:
       memory_usage_mb: 1000
       cpu_usage_percent: 80
       error_rate_percent: 5
       response_time_seconds: 10
   ```

3. **Monitor log files**:
   ```bash
   tail -f ~/.claude-remote-client/logs/performance.log
   ```

## Best Practices

1. **Configuration Management**:
   - Use environment-specific configurations
   - Version control your configuration files
   - Validate configurations before deployment

2. **Resource Management**:
   - Always use async context managers
   - Properly clean up resources
   - Monitor resource usage regularly

3. **Testing**:
   - Run performance tests regularly
   - Benchmark critical operations
   - Test under realistic load conditions

4. **Monitoring**:
   - Set up comprehensive logging
   - Monitor key performance metrics
   - Set up alerts for critical issues

5. **Optimization**:
   - Profile your application regularly
   - Optimize based on actual usage patterns
   - Balance performance with resource usage
