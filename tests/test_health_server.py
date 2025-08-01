"""
Tests for health server functionality.
"""

import asyncio
import json
import pytest
from aiohttp import ClientSession
from unittest.mock import AsyncMock, patch, MagicMock

from claude_remote_client.health_server import HealthServer, start_health_server, stop_health_server
from claude_remote_client.monitoring import health_monitor, metrics_collector


class TestHealthServer:
    """Test health server functionality."""
    
    @pytest.fixture
    async def health_server(self):
        """Create a health server instance for testing."""
        server = HealthServer(host='127.0.0.1', port=8081)  # Use different port for testing
        await server.start()
        yield server
        await server.stop()
    
    @pytest.fixture
    async def client_session(self):
        """Create an HTTP client session for testing."""
        async with ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_health_server_start_stop(self):
        """Test health server can start and stop."""
        server = HealthServer(host='127.0.0.1', port=8082)
        
        # Start server
        await server.start()
        assert server.runner is not None
        assert server.site is not None
        
        # Stop server
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, health_server, client_session):
        """Test root endpoint returns service information."""
        async with client_session.get('http://127.0.0.1:8081/') as response:
            assert response.status == 200
            data = await response.json()
            
            assert data['service'] == 'claude-remote-client'
            assert data['status'] == 'running'
            assert 'endpoints' in data
            assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_health_endpoint_healthy(self, health_server, client_session):
        """Test health endpoint when system is healthy."""
        # Mock health monitor to return healthy status
        with patch.object(health_monitor, 'get_health_status') as mock_health:
            mock_health.return_value = {
                'overall_health': 'healthy',
                'system': {},
                'timestamp': '2024-01-31T10:30:00Z'
            }
            
            async with client_session.get('http://127.0.0.1:8081/health') as response:
                assert response.status == 200
                data = await response.json()
                
                assert data['overall_health'] == 'healthy'
                assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_health_endpoint_unhealthy(self, health_server, client_session):
        """Test health endpoint when system is unhealthy."""
        # Mock health monitor to return unhealthy status
        with patch.object(health_monitor, 'get_health_status') as mock_health:
            mock_health.return_value = {
                'overall_health': 'unhealthy',
                'system': {},
                'timestamp': '2024-01-31T10:30:00Z'
            }
            
            async with client_session.get('http://127.0.0.1:8081/health') as response:
                assert response.status == 503
                data = await response.json()
                
                assert data['overall_health'] == 'unhealthy'
    
    @pytest.mark.asyncio
    async def test_liveness_endpoint(self, health_server, client_session):
        """Test liveness probe endpoint."""
        async with client_session.get('http://127.0.0.1:8081/health/live') as response:
            assert response.status == 200
            data = await response.json()
            
            assert data['status'] == 'alive'
            assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_readiness_endpoint(self, health_server, client_session):
        """Test readiness probe endpoint."""
        # Mock health monitor methods
        with patch.object(health_monitor, '_check_config_readable') as mock_config, \
             patch.object(health_monitor, '_check_data_directory') as mock_data, \
             patch.object(health_monitor, '_check_claude_cli') as mock_claude:
            
            mock_config.return_value = {'healthy': True, 'details': 'Config readable'}
            mock_data.return_value = {'healthy': True, 'details': 'Data directory writable'}
            mock_claude.return_value = {'healthy': True, 'details': 'Claude CLI available'}
            
            async with client_session.get('http://127.0.0.1:8081/health/ready') as response:
                assert response.status == 200
                data = await response.json()
                
                assert data['status'] == 'ready'
                assert 'checks' in data
                assert len(data['checks']) == 3
    
    @pytest.mark.asyncio
    async def test_readiness_endpoint_not_ready(self, health_server, client_session):
        """Test readiness probe when not ready."""
        # Mock health monitor methods with failure
        with patch.object(health_monitor, '_check_config_readable') as mock_config, \
             patch.object(health_monitor, '_check_data_directory') as mock_data, \
             patch.object(health_monitor, '_check_claude_cli') as mock_claude:
            
            mock_config.return_value = {'healthy': False, 'details': 'Config not readable'}
            mock_data.return_value = {'healthy': True, 'details': 'Data directory writable'}
            mock_claude.return_value = {'healthy': True, 'details': 'Claude CLI available'}
            
            async with client_session.get('http://127.0.0.1:8081/health/ready') as response:
                assert response.status == 503
                data = await response.json()
                
                assert data['status'] == 'not_ready'
                assert 'checks' in data
    
    @pytest.mark.asyncio
    async def test_detailed_health_endpoint(self, health_server, client_session):
        """Test detailed health endpoint."""
        # Mock health monitor to return detailed status
        with patch.object(health_monitor, 'get_detailed_health_status') as mock_detailed:
            mock_detailed.return_value = {
                'overall_health': 'healthy',
                'application_metrics': {},
                'recent_errors': [],
                'service_checks': {},
                'uptime_seconds': 3600,
                'version': '1.0.0',
                'timestamp': '2024-01-31T10:30:00Z'
            }
            
            async with client_session.get('http://127.0.0.1:8081/health/detailed') as response:
                assert response.status == 200
                data = await response.json()
                
                assert data['overall_health'] == 'healthy'
                assert 'application_metrics' in data
                assert 'service_checks' in data
                assert 'uptime_seconds' in data
                assert 'version' in data
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint_json(self, health_server, client_session):
        """Test metrics endpoint returns JSON format."""
        # Mock metrics collector
        with patch.object(metrics_collector, 'get_dashboard_data') as mock_metrics:
            mock_metrics.return_value = {
                'metrics': {
                    'messages_processed': {'count': 100, 'rate_per_minute': 5}
                },
                'system': {
                    'cpu_percent': {'current': 15.2}
                },
                'timestamp': '2024-01-31T10:30:00Z'
            }
            
            async with client_session.get('http://127.0.0.1:8081/metrics') as response:
                assert response.status == 200
                assert response.content_type.startswith('application/json')
                data = await response.json()
                
                assert 'metrics' in data
                assert 'system' in data
                assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint_prometheus(self, health_server, client_session):
        """Test metrics endpoint returns Prometheus format."""
        # Mock metrics collector
        with patch.object(metrics_collector, 'get_dashboard_data') as mock_metrics:
            mock_metrics.return_value = {
                'metrics': {
                    'messages_processed': {'count': 100, 'rate_per_minute': 5}
                },
                'system': {
                    'cpu_percent': {'current': 15.2}
                },
                'timestamp': '2024-01-31T10:30:00Z'
            }
            
            # Mock version
            with patch.object(health_monitor, '_get_version', return_value='1.0.0'):
                async with client_session.get('http://127.0.0.1:8081/metrics?format=prometheus') as response:
                    assert response.status == 200
                    assert response.content_type.startswith('text/plain')
                    text = await response.text()
                    
                    assert 'claude_remote_client_info' in text
                    assert 'claude_system_cpu_percent' in text
                    assert 'claude_messages_processed_total' in text
    
    @pytest.mark.asyncio
    async def test_status_endpoint(self, health_server, client_session):
        """Test status endpoint."""
        # Mock system metrics and health checks
        with patch.object(metrics_collector, 'collect_system_metrics') as mock_system, \
             patch.object(metrics_collector, 'run_health_checks') as mock_checks, \
             patch.object(health_monitor, '_get_uptime', return_value=3600), \
             patch.object(health_monitor, '_get_version', return_value='1.0.0'):
            
            mock_system.return_value = {'cpu_percent': 15.2, 'memory_percent': 45.8}
            mock_checks.return_value = {'test_check': {'healthy': True, 'details': 'OK'}}
            
            async with client_session.get('http://127.0.0.1:8081/status') as response:
                assert response.status == 200
                data = await response.json()
                
                assert data['service'] == 'claude-remote-client'
                assert data['status'] == 'running'
                assert 'system_metrics' in data
                assert 'health_checks' in data
                assert 'uptime_seconds' in data
                assert 'version' in data
    
    @pytest.mark.asyncio
    async def test_version_endpoint(self, health_server, client_session):
        """Test version endpoint."""
        with patch.object(health_monitor, '_get_version', return_value='1.0.0'):
            async with client_session.get('http://127.0.0.1:8081/version') as response:
                assert response.status == 200
                data = await response.json()
                
                assert data['service'] == 'claude-remote-client'
                assert data['version'] == '1.0.0'
                assert 'python_version' in data
                assert 'build_info' in data
                assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_error_handling(self, health_server, client_session):
        """Test error handling in endpoints."""
        # Mock health monitor to raise exception
        with patch.object(health_monitor, 'get_health_status', side_effect=Exception('Test error')):
            async with client_session.get('http://127.0.0.1:8081/health') as response:
                assert response.status == 503
                data = await response.json()
                
                assert data['overall_health'] == 'unhealthy'
                assert 'error' in data
                assert data['error'] == 'Test error'


class TestHealthServerGlobalFunctions:
    """Test global health server functions."""
    
    @pytest.mark.asyncio
    async def test_start_stop_health_server(self):
        """Test global start/stop functions."""
        # Start health server
        await start_health_server(host='127.0.0.1', port=8083)
        
        # Test that server is running
        async with ClientSession() as session:
            async with session.get('http://127.0.0.1:8083/') as response:
                assert response.status == 200
        
        # Stop health server
        await stop_health_server()
    
    def test_format_prometheus_metrics(self):
        """Test Prometheus metrics formatting."""
        server = HealthServer()
        
        metrics_data = {
            'metrics': {
                'messages_processed': {'count': 100, 'rate_per_minute': 5},
                'errors_encountered': {'count': 3, 'rate_per_minute': 0.1}
            },
            'system': {
                'cpu_percent': {'current': 15.2},
                'memory_percent': {'current': 45.8}
            }
        }
        
        with patch.object(health_monitor, '_get_version', return_value='1.0.0'):
            prometheus_text = server._format_prometheus_metrics(metrics_data)
            
            # Check that Prometheus format is correct
            assert 'claude_remote_client_info{version="1.0.0"} 1' in prometheus_text
            assert 'claude_system_cpu_percent 15.2' in prometheus_text
            assert 'claude_system_memory_percent 45.8' in prometheus_text
            assert 'claude_messages_processed_total 100' in prometheus_text
            assert 'claude_messages_processed_rate 5' in prometheus_text
            
            # Check metadata
            assert '# HELP claude_remote_client_info Information about Claude Remote Client' in prometheus_text
            assert '# TYPE claude_remote_client_info gauge' in prometheus_text
    
    def test_get_python_version(self):
        """Test Python version retrieval."""
        server = HealthServer()
        version = server._get_python_version()
        
        # Should return version in format "3.11.0"
        assert isinstance(version, str)
        assert len(version.split('.')) >= 2
    
    def test_get_build_info(self):
        """Test build info retrieval."""
        server = HealthServer()
        build_info = server._get_build_info()
        
        assert isinstance(build_info, dict)
        assert 'build_date' in build_info
        assert 'vcs_ref' in build_info
        assert 'platform' in build_info