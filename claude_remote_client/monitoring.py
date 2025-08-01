"""
Monitoring and health check functionality.

This module provides system health monitoring, performance metrics,
and status reporting capabilities.
"""

import asyncio
import psutil
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
import logging

from .exceptions import ClaudeRemoteClientError


class MetricsCollector:
    """
    Collects and tracks system metrics and performance data.
    """
    
    def __init__(self, window_size: int = 3600):
        """
        Initialize metrics collector.
        
        Args:
            window_size: Time window in seconds for metrics (default: 1 hour)
        """
        self.logger = logging.getLogger(__name__)
        self.window_size = window_size
        
        # Metric storage with timestamp
        self.metrics: Dict[str, deque] = {
            'messages_processed': deque(),
            'commands_executed': deque(),
            'errors_encountered': deque(),
            'response_times': deque(),
            'session_creations': deque(),
            'queue_operations': deque()
        }
        
        # System metrics
        self.system_metrics = {
            'cpu_percent': deque(),
            'memory_percent': deque(),
            'disk_usage': deque()
        }
        
        # Health check callbacks
        self.health_checks: Dict[str, Callable] = {}
    
    def record_metric(self, metric_name: str, value: Any = 1) -> None:
        """
        Record a metric value with timestamp.
        
        Args:
            metric_name: Name of the metric
            value: Metric value (default: 1 for counters)
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = deque()
        
        timestamp = datetime.now()
        self.metrics[metric_name].append((timestamp, value))
        
        # Clean old entries
        self._clean_old_entries(self.metrics[metric_name])
    
    def record_response_time(self, operation: str, duration: float) -> None:
        """
        Record response time for an operation.
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
        """
        self.record_metric('response_times', {
            'operation': operation,
            'duration': duration
        })
    
    def get_metric_stats(self, metric_name: str) -> Dict[str, Any]:
        """
        Get statistics for a metric.
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            Dict containing metric statistics
        """
        if metric_name not in self.metrics:
            return {'error': f"Unknown metric: {metric_name}"}
        
        entries = self.metrics[metric_name]
        if not entries:
            return {
                'count': 0,
                'rate_per_minute': 0,
                'rate_per_hour': 0
            }
        
        # Calculate time-based statistics
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        minute_count = sum(1 for ts, _ in entries if ts > minute_ago)
        hour_count = sum(1 for ts, _ in entries if ts > hour_ago)
        
        # For response times, calculate averages
        if metric_name == 'response_times':
            recent_times = [v['duration'] for ts, v in entries if ts > minute_ago]
            avg_response_time = sum(recent_times) / len(recent_times) if recent_times else 0
            
            return {
                'count': len(entries),
                'rate_per_minute': minute_count,
                'rate_per_hour': hour_count,
                'average_response_time': avg_response_time,
                'min_response_time': min(recent_times) if recent_times else 0,
                'max_response_time': max(recent_times) if recent_times else 0
            }
        
        return {
            'count': len(entries),
            'rate_per_minute': minute_count,
            'rate_per_hour': hour_count
        }
    
    def _clean_old_entries(self, entries: deque) -> None:
        """Remove entries older than the window size."""
        cutoff = datetime.now() - timedelta(seconds=self.window_size)
        while entries and entries[0][0] < cutoff:
            entries.popleft()
    
    async def collect_system_metrics(self) -> Dict[str, float]:
        """
        Collect current system metrics.
        
        Returns:
            Dict containing system metrics
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage for data directory
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Record metrics
            timestamp = datetime.now()
            self.system_metrics['cpu_percent'].append((timestamp, cpu_percent))
            self.system_metrics['memory_percent'].append((timestamp, memory_percent))
            self.system_metrics['disk_usage'].append((timestamp, disk_percent))
            
            # Clean old entries
            for metric_deque in self.system_metrics.values():
                self._clean_old_entries(metric_deque)
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_free_gb': disk.free / (1024 * 1024 * 1024)
            }
        
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    def register_health_check(self, name: str, check_func: Callable) -> None:
        """
        Register a health check function.
        
        Args:
            name: Name of the health check
            check_func: Async function that returns (healthy: bool, details: str)
        """
        self.health_checks[name] = check_func
    
    async def run_health_checks(self) -> Dict[str, Dict[str, Any]]:
        """
        Run all registered health checks.
        
        Returns:
            Dict mapping check names to results
        """
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                healthy, details = await check_func()
                duration = time.time() - start_time
                
                results[name] = {
                    'healthy': healthy,
                    'details': details,
                    'duration': duration,
                    'timestamp': datetime.now().isoformat()
                }
            
            except Exception as e:
                results[name] = {
                    'healthy': False,
                    'details': f"Check failed: {str(e)}",
                    'duration': 0,
                    'timestamp': datetime.now().isoformat()
                }
        
        return results
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Returns:
            Dict containing all monitoring data
        """
        # Get metric statistics
        metrics_stats = {}
        for metric_name in self.metrics:
            metrics_stats[metric_name] = self.get_metric_stats(metric_name)
        
        # Get recent system metrics
        system_stats = {}
        for metric_name, entries in self.system_metrics.items():
            if entries:
                recent_values = [v for _, v in entries]
                system_stats[metric_name] = {
                    'current': recent_values[-1],
                    'average': sum(recent_values) / len(recent_values),
                    'min': min(recent_values),
                    'max': max(recent_values)
                }
        
        return {
            'metrics': metrics_stats,
            'system': system_stats,
            'timestamp': datetime.now().isoformat()
        }


class HealthMonitor:
    """
    Monitors system health and provides alerting capabilities.
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        """
        Initialize health monitor.
        
        Args:
            metrics_collector: MetricsCollector instance
        """
        self.logger = logging.getLogger(__name__)
        self.metrics = metrics_collector
        self.is_running = False
        self.check_interval = 60  # seconds
        
        # Health thresholds
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'error_rate_per_minute': 10,
            'response_time_avg': 5.0  # seconds
        }
        
        # Alert callbacks
        self.alert_callbacks: List[Callable] = []
    
    def set_threshold(self, metric: str, value: float) -> None:
        """
        Set a health threshold.
        
        Args:
            metric: Metric name
            value: Threshold value
        """
        self.thresholds[metric] = value
    
    def add_alert_callback(self, callback: Callable) -> None:
        """
        Add an alert callback function.
        
        Args:
            callback: Function to call on alert (async)
        """
        self.alert_callbacks.append(callback)
    
    async def start(self) -> None:
        """Start the health monitoring loop."""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info("Starting health monitor")
        
        asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop the health monitoring loop."""
        self.is_running = False
        self.logger.info("Stopping health monitor")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_running:
            try:
                # Collect system metrics
                system_metrics = await self.metrics.collect_system_metrics()
                
                # Run health checks
                health_results = await self.metrics.run_health_checks()
                
                # Check thresholds
                alerts = self._check_thresholds(system_metrics)
                
                # Send alerts if any
                if alerts:
                    await self._send_alerts(alerts)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
            
            except Exception as e:
                self.logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def _check_thresholds(self, system_metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Check metrics against thresholds.
        
        Args:
            system_metrics: Current system metrics
        
        Returns:
            List of alerts
        """
        alerts = []
        
        # Check system metrics
        for metric, value in system_metrics.items():
            if metric in self.thresholds and value > self.thresholds[metric]:
                alerts.append({
                    'type': 'threshold_exceeded',
                    'metric': metric,
                    'value': value,
                    'threshold': self.thresholds[metric],
                    'severity': 'warning' if value < self.thresholds[metric] * 1.2 else 'critical'
                })
        
        # Check error rate
        error_stats = self.metrics.get_metric_stats('errors_encountered')
        if error_stats['rate_per_minute'] > self.thresholds.get('error_rate_per_minute', 10):
            alerts.append({
                'type': 'high_error_rate',
                'metric': 'error_rate_per_minute',
                'value': error_stats['rate_per_minute'],
                'threshold': self.thresholds.get('error_rate_per_minute', 10),
                'severity': 'critical'
            })
        
        # Check response times
        response_stats = self.metrics.get_metric_stats('response_times')
        if 'average_response_time' in response_stats:
            avg_time = response_stats['average_response_time']
            if avg_time > self.thresholds.get('response_time_avg', 5.0):
                alerts.append({
                    'type': 'slow_response',
                    'metric': 'response_time_avg',
                    'value': avg_time,
                    'threshold': self.thresholds.get('response_time_avg', 5.0),
                    'severity': 'warning'
                })
        
        return alerts
    
    async def _send_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """
        Send alerts to registered callbacks.
        
        Args:
            alerts: List of alerts to send
        """
        for callback in self.alert_callbacks:
            try:
                await callback(alerts)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status.
        
        Returns:
            Dict containing health status
        """
        # Get latest system metrics
        system_status = {}
        for metric_name, entries in self.metrics.system_metrics.items():
            if entries:
                current_value = entries[-1][1]
                threshold = self.thresholds.get(metric_name, 100)
                system_status[metric_name] = {
                    'value': current_value,
                    'threshold': threshold,
                    'healthy': current_value <= threshold
                }
        
        # Overall health
        all_healthy = all(s['healthy'] for s in system_status.values())
        
        return {
            'overall_health': 'healthy' if all_healthy else 'unhealthy',
            'system': system_status,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_detailed_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status with detailed metrics.
        
        Returns:
            Dict containing detailed health information
        """
        # Basic health status
        basic_status = self.get_health_status()
        
        # Application metrics
        app_metrics = {}
        for metric_name in self.metrics.metrics:
            stats = self.metrics.get_metric_stats(metric_name)
            app_metrics[metric_name] = stats
        
        # Recent errors
        error_entries = self.metrics.metrics.get('errors_encountered', deque())
        recent_errors = []
        cutoff = datetime.now() - timedelta(minutes=5)
        for timestamp, error_data in error_entries:
            if timestamp > cutoff:
                recent_errors.append({
                    'timestamp': timestamp.isoformat(),
                    'error': str(error_data)
                })
        
        # Service status checks
        service_checks = {
            'config_readable': self._check_config_readable(),
            'data_directory_writable': self._check_data_directory(),
            'claude_cli_available': self._check_claude_cli(),
            'memory_usage_acceptable': self._check_memory_usage(),
            'disk_space_sufficient': self._check_disk_space()
        }
        
        return {
            **basic_status,
            'application_metrics': app_metrics,
            'recent_errors': recent_errors,
            'service_checks': service_checks,
            'uptime_seconds': self._get_uptime(),
            'version': self._get_version()
        }
    
    def _check_config_readable(self) -> Dict[str, Any]:
        """Check if configuration file is readable."""
        import os
        config_path = os.environ.get('CLAUDE_REMOTE_CLIENT_CONFIG', 'config.yaml')
        try:
            readable = os.path.isfile(config_path) and os.access(config_path, os.R_OK)
            return {
                'healthy': readable,
                'details': f"Config file {'readable' if readable else 'not readable'}: {config_path}"
            }
        except Exception as e:
            return {
                'healthy': False,
                'details': f"Error checking config: {str(e)}"
            }
    
    def _check_data_directory(self) -> Dict[str, Any]:
        """Check if data directory is writable."""
        import os
        data_dir = os.environ.get('CLAUDE_REMOTE_CLIENT_DATA_DIR', './data')
        try:
            os.makedirs(data_dir, exist_ok=True)
            writable = os.access(data_dir, os.W_OK)
            return {
                'healthy': writable,
                'details': f"Data directory {'writable' if writable else 'not writable'}: {data_dir}"
            }
        except Exception as e:
            return {
                'healthy': False,
                'details': f"Error checking data directory: {str(e)}"
            }
    
    def _check_claude_cli(self) -> Dict[str, Any]:
        """Check if Claude CLI is available."""
        import shutil
        claude_path = shutil.which('claude')
        available = claude_path is not None
        return {
            'healthy': available,
            'details': f"Claude CLI {'found' if available else 'not found'}" + 
                      (f" at {claude_path}" if available else " in PATH")
        }
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        """Check current memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            acceptable = usage_percent < 85
            return {
                'healthy': acceptable,
                'details': f"Memory usage: {usage_percent:.1f}% ({'acceptable' if acceptable else 'high'})"
            }
        except Exception as e:
            return {
                'healthy': False,
                'details': f"Error checking memory: {str(e)}"
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import psutil
            import os
            data_dir = os.environ.get('CLAUDE_REMOTE_CLIENT_DATA_DIR', './data')
            disk = psutil.disk_usage(data_dir)
            usage_percent = (disk.used / disk.total) * 100
            sufficient = usage_percent < 90
            return {
                'healthy': sufficient,
                'details': f"Disk usage: {usage_percent:.1f}% ({'sufficient' if sufficient else 'low space'})"
            }
        except Exception as e:
            return {
                'healthy': False,
                'details': f"Error checking disk space: {str(e)}"
            }
    
    def _get_uptime(self) -> float:
        """Get application uptime in seconds."""
        # This would need to be implemented with application start time tracking
        # For now, return 0 as placeholder
        return 0.0
    
    def _get_version(self) -> str:
        """Get application version."""
        try:
            import claude_remote_client
            return getattr(claude_remote_client, '__version__', 'unknown')
        except:
            return 'unknown'


# Global instances
metrics_collector = MetricsCollector()
health_monitor = HealthMonitor(metrics_collector)