"""
Tests for the monitoring module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from claude_remote_client.monitoring import MetricsCollector, HealthMonitor


class TestMetricsCollector:
    """Test the MetricsCollector class."""
    
    def test_init(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector(window_size=3600)
        assert collector.window_size == 3600
        assert 'messages_processed' in collector.metrics
        assert 'cpu_percent' in collector.system_metrics
        assert collector.health_checks == {}
    
    def test_record_metric(self):
        """Test recording metrics."""
        collector = MetricsCollector()
        
        # Record a metric
        collector.record_metric('messages_processed', 1)
        
        assert len(collector.metrics['messages_processed']) == 1
        timestamp, value = collector.metrics['messages_processed'][0]
        assert value == 1
        assert isinstance(timestamp, datetime)
    
    def test_record_response_time(self):
        """Test recording response times."""
        collector = MetricsCollector()
        
        collector.record_response_time('test_operation', 1.5)
        
        assert len(collector.metrics['response_times']) == 1
        timestamp, value = collector.metrics['response_times'][0]
        assert value['operation'] == 'test_operation'
        assert value['duration'] == 1.5
    
    def test_get_metric_stats(self):
        """Test getting metric statistics."""
        collector = MetricsCollector()
        
        # Test empty metrics
        stats = collector.get_metric_stats('messages_processed')
        assert stats['count'] == 0
        assert stats['rate_per_minute'] == 0
        
        # Add some metrics
        for _ in range(5):
            collector.record_metric('messages_processed')
        
        stats = collector.get_metric_stats('messages_processed')
        assert stats['count'] == 5
        assert stats['rate_per_minute'] == 5  # All within last minute
        assert stats['rate_per_hour'] == 5
    
    def test_get_metric_stats_response_times(self):
        """Test getting response time statistics."""
        collector = MetricsCollector()
        
        # Add response times
        collector.record_response_time('api_call', 1.0)
        collector.record_response_time('api_call', 2.0)
        collector.record_response_time('api_call', 3.0)
        
        stats = collector.get_metric_stats('response_times')
        assert stats['count'] == 3
        assert stats['average_response_time'] == 2.0
        assert stats['min_response_time'] == 1.0
        assert stats['max_response_time'] == 3.0
    
    def test_clean_old_entries(self):
        """Test cleaning old metric entries."""
        collector = MetricsCollector(window_size=1)  # 1 second window
        
        # Add an old entry manually
        old_timestamp = datetime.now() - timedelta(seconds=2)
        collector.metrics['messages_processed'].append((old_timestamp, 1))
        
        # Add a new entry
        collector.record_metric('messages_processed', 1)
        
        # Old entry should be removed
        assert len(collector.metrics['messages_processed']) == 1
        assert collector.metrics['messages_processed'][0][0] > old_timestamp
    
    @pytest.mark.asyncio
    @patch('claude_remote_client.monitoring.psutil')
    async def test_collect_system_metrics(self, mock_psutil):
        """Test collecting system metrics."""
        # Mock psutil functions
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(
            percent=60.0,
            available=1024 * 1024 * 1024  # 1GB
        )
        mock_psutil.disk_usage.return_value = Mock(
            percent=70.0,
            free=10 * 1024 * 1024 * 1024  # 10GB
        )
        
        collector = MetricsCollector()
        metrics = await collector.collect_system_metrics()
        
        assert metrics['cpu_percent'] == 50.0
        assert metrics['memory_percent'] == 60.0
        assert metrics['disk_percent'] == 70.0
        assert metrics['memory_available_mb'] == 1024
        assert metrics['disk_free_gb'] == 10
    
    def test_register_health_check(self):
        """Test registering health checks."""
        collector = MetricsCollector()
        
        async def test_check():
            return True, "All good"
        
        collector.register_health_check('test_check', test_check)
        assert 'test_check' in collector.health_checks
        assert collector.health_checks['test_check'] == test_check
    
    @pytest.mark.asyncio
    async def test_run_health_checks(self):
        """Test running health checks."""
        collector = MetricsCollector()
        
        # Register health checks
        async def healthy_check():
            return True, "Healthy"
        
        async def unhealthy_check():
            return False, "Unhealthy"
        
        async def failing_check():
            raise ValueError("Check failed")
        
        collector.register_health_check('healthy', healthy_check)
        collector.register_health_check('unhealthy', unhealthy_check)
        collector.register_health_check('failing', failing_check)
        
        results = await collector.run_health_checks()
        
        assert results['healthy']['healthy'] is True
        assert results['healthy']['details'] == "Healthy"
        
        assert results['unhealthy']['healthy'] is False
        assert results['unhealthy']['details'] == "Unhealthy"
        
        assert results['failing']['healthy'] is False
        assert "Check failed" in results['failing']['details']
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        collector = MetricsCollector()
        
        # Add some data
        collector.record_metric('messages_processed', 1)
        collector.system_metrics['cpu_percent'].append((datetime.now(), 50.0))
        
        dashboard = collector.get_dashboard_data()
        
        assert 'metrics' in dashboard
        assert 'system' in dashboard
        assert 'timestamp' in dashboard
        assert dashboard['metrics']['messages_processed']['count'] == 1
        assert dashboard['system']['cpu_percent']['current'] == 50.0


class TestHealthMonitor:
    """Test the HealthMonitor class."""
    
    def test_init(self):
        """Test health monitor initialization."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        assert monitor.metrics == collector
        assert monitor.is_running is False
        assert monitor.check_interval == 60
        assert 'cpu_percent' in monitor.thresholds
    
    def test_set_threshold(self):
        """Test setting health thresholds."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        monitor.set_threshold('custom_metric', 100.0)
        assert monitor.thresholds['custom_metric'] == 100.0
    
    def test_add_alert_callback(self):
        """Test adding alert callbacks."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        async def alert_callback(alerts):
            pass
        
        monitor.add_alert_callback(alert_callback)
        assert alert_callback in monitor.alert_callbacks
    
    def test_check_thresholds(self):
        """Test checking metrics against thresholds."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        # Test system metrics exceeding thresholds
        system_metrics = {
            'cpu_percent': 85.0,  # Above threshold of 80
            'memory_percent': 70.0,  # Below threshold of 85
            'disk_percent': 95.0  # Above threshold of 90
        }
        
        alerts = monitor._check_thresholds(system_metrics)
        
        assert len(alerts) == 2  # CPU and disk alerts
        
        cpu_alert = next(a for a in alerts if a['metric'] == 'cpu_percent')
        assert cpu_alert['type'] == 'threshold_exceeded'
        assert cpu_alert['value'] == 85.0
        assert cpu_alert['severity'] == 'warning'
        
        disk_alert = next(a for a in alerts if a['metric'] == 'disk_percent')
        assert disk_alert['severity'] == 'warning'  # 95 is not over 90 * 1.2 (108)
    
    @pytest.mark.asyncio
    async def test_send_alerts(self):
        """Test sending alerts to callbacks."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        # Mock alert callback
        received_alerts = []
        
        async def alert_callback(alerts):
            received_alerts.extend(alerts)
        
        monitor.add_alert_callback(alert_callback)
        
        # Send test alerts
        test_alerts = [{'type': 'test', 'message': 'Test alert'}]
        await monitor._send_alerts(test_alerts)
        
        assert received_alerts == test_alerts
    
    def test_get_health_status(self):
        """Test getting health status."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        # Add some system metrics
        collector.system_metrics['cpu_percent'].append((datetime.now(), 50.0))
        collector.system_metrics['memory_percent'].append((datetime.now(), 60.0))
        
        status = monitor.get_health_status()
        
        assert status['overall_health'] == 'healthy'
        assert status['system']['cpu_percent']['value'] == 50.0
        assert status['system']['cpu_percent']['healthy'] is True
        assert 'timestamp' in status
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the monitor."""
        collector = MetricsCollector()
        monitor = HealthMonitor(collector)
        
        # Start monitor
        await monitor.start()
        assert monitor.is_running is True
        
        # Stop monitor
        await monitor.stop()
        assert monitor.is_running is False