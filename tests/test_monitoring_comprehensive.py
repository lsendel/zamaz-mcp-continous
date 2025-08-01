"""
Comprehensive unit tests for the monitoring module.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from claude_remote_client.monitoring import (
    MetricsCollector
)


# Tests for other monitoring components can be added as they become available


class TestMetricsCollector:
    """Test the MetricsCollector class."""
    
    def test_metrics_collector_creation(self):
        """Test creating metrics collector."""
        collector = MetricsCollector()
        assert hasattr(collector, 'logger')
        assert hasattr(collector, 'window_size')
        assert hasattr(collector, 'metrics')
        assert hasattr(collector, 'system_metrics')
        assert collector.window_size == 3600  # Default 1 hour
    
    def test_metrics_collector_custom_window(self):
        """Test creating metrics collector with custom window size."""
        collector = MetricsCollector(window_size=1800)  # 30 minutes
        assert collector.window_size == 1800
    
    def test_metrics_collector_has_expected_metrics(self):
        """Test that metrics collector has expected metric types."""
        collector = MetricsCollector()
        
        expected_metrics = [
            'messages_processed',
            'commands_executed', 
            'errors_encountered',
            'response_times',
            'session_creations',
            'queue_operations'
        ]
        
        for metric in expected_metrics:
            assert metric in collector.metrics
            assert hasattr(collector.metrics[metric], 'append')  # Should be deque
    
    def test_system_metrics_structure(self):
        """Test system metrics structure."""
        collector = MetricsCollector()
        
        expected_system_metrics = [
            'cpu_percent',
            'memory_percent',
            'disk_usage'
        ]
        
        for metric in expected_system_metrics:
            assert metric in collector.system_metrics
            assert hasattr(collector.system_metrics[metric], 'append')  # Should be deque