"""
Health check HTTP server for monitoring and deployment health checks.

This module provides a simple HTTP server that exposes health check endpoints
for monitoring systems, load balancers, and deployment orchestrators.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from aiohttp import web, web_request
from aiohttp.web_response import Response

from .monitoring import health_monitor, metrics_collector


class HealthServer:
    """
    HTTP server for health check and monitoring endpoints.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        """
        Initialize health server.
        
        Args:
            host: Server host address
            port: Server port
        """
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup HTTP routes."""
        self.app.router.add_get('/', self._root_handler)
        self.app.router.add_get('/health', self._health_handler)
        self.app.router.add_get('/health/live', self._liveness_handler)
        self.app.router.add_get('/health/ready', self._readiness_handler)
        self.app.router.add_get('/health/detailed', self._detailed_health_handler)
        self.app.router.add_get('/metrics', self._metrics_handler)
        self.app.router.add_get('/status', self._status_handler)
        self.app.router.add_get('/version', self._version_handler)
    
    async def start(self) -> None:
        """Start the health server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            self.logger.info(f"Health server started on {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to start health server: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the health server."""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            self.logger.info("Health server stopped")
        except Exception as e:
            self.logger.error(f"Error stopping health server: {e}")
    
    async def _root_handler(self, request: web_request.Request) -> Response:
        """Root endpoint handler."""
        return web.json_response({
            'service': 'claude-remote-client',
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'endpoints': {
                '/health': 'Basic health check',
                '/health/live': 'Liveness probe',
                '/health/ready': 'Readiness probe',
                '/health/detailed': 'Detailed health information',
                '/metrics': 'Application metrics',
                '/status': 'Service status',
                '/version': 'Version information'
            }
        })
    
    async def _health_handler(self, request: web_request.Request) -> Response:
        """Basic health check endpoint."""
        try:
            health_status = health_monitor.get_health_status()
            status_code = 200 if health_status['overall_health'] == 'healthy' else 503
            
            return web.json_response(
                health_status,
                status=status_code
            )
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return web.json_response(
                {
                    'overall_health': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=503
            )
    
    async def _liveness_handler(self, request: web_request.Request) -> Response:
        """
        Liveness probe endpoint.
        
        This endpoint checks if the application is alive and should be restarted
        if it fails. It performs minimal checks to avoid false positives.
        """
        try:
            # Basic application availability check
            import claude_remote_client
            
            return web.json_response({
                'status': 'alive',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Liveness check failed: {e}")
            return web.json_response(
                {
                    'status': 'dead',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=503
            )
    
    async def _readiness_handler(self, request: web_request.Request) -> Response:
        """
        Readiness probe endpoint.
        
        This endpoint checks if the application is ready to serve traffic.
        It performs more comprehensive checks than liveness.
        """
        try:
            # Check critical dependencies
            checks = {
                'config_readable': health_monitor._check_config_readable(),
                'data_directory_writable': health_monitor._check_data_directory(),
                'claude_cli_available': health_monitor._check_claude_cli()
            }
            
            all_ready = all(check['healthy'] for check in checks.values())
            status_code = 200 if all_ready else 503
            
            return web.json_response(
                {
                    'status': 'ready' if all_ready else 'not_ready',
                    'checks': checks,
                    'timestamp': datetime.now().isoformat()
                },
                status=status_code
            )
        except Exception as e:
            self.logger.error(f"Readiness check failed: {e}")
            return web.json_response(
                {
                    'status': 'not_ready',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=503
            )
    
    async def _detailed_health_handler(self, request: web_request.Request) -> Response:
        """Detailed health information endpoint."""
        try:
            detailed_status = health_monitor.get_detailed_health_status()
            status_code = 200 if detailed_status['overall_health'] == 'healthy' else 503
            
            return web.json_response(
                detailed_status,
                status=status_code
            )
        except Exception as e:
            self.logger.error(f"Detailed health check failed: {e}")
            return web.json_response(
                {
                    'overall_health': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=503
            )
    
    async def _metrics_handler(self, request: web_request.Request) -> Response:
        """Metrics endpoint for monitoring systems."""
        try:
            # Get metrics in different formats based on Accept header
            accept_header = request.headers.get('Accept', 'application/json')
            
            if 'text/plain' in accept_header or 'prometheus' in request.query.get('format', ''):
                # Prometheus format
                metrics_data = metrics_collector.get_dashboard_data()
                prometheus_metrics = self._format_prometheus_metrics(metrics_data)
                return web.Response(
                    text=prometheus_metrics,
                    content_type='text/plain; version=0.0.4'
                )
            else:
                # JSON format
                metrics_data = metrics_collector.get_dashboard_data()
                return web.json_response(metrics_data)
        
        except Exception as e:
            self.logger.error(f"Metrics endpoint failed: {e}")
            return web.json_response(
                {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=500
            )
    
    async def _status_handler(self, request: web_request.Request) -> Response:
        """Service status endpoint."""
        try:
            # Collect comprehensive status information
            system_metrics = await metrics_collector.collect_system_metrics()
            health_checks = await metrics_collector.run_health_checks()
            
            status_info = {
                'service': 'claude-remote-client',
                'status': 'running',
                'system_metrics': system_metrics,
                'health_checks': health_checks,
                'uptime_seconds': health_monitor._get_uptime(),
                'version': health_monitor._get_version(),
                'timestamp': datetime.now().isoformat()
            }
            
            return web.json_response(status_info)
        
        except Exception as e:
            self.logger.error(f"Status endpoint failed: {e}")
            return web.json_response(
                {
                    'service': 'claude-remote-client',
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=500
            )
    
    async def _version_handler(self, request: web_request.Request) -> Response:
        """Version information endpoint."""
        try:
            version_info = {
                'service': 'claude-remote-client',
                'version': health_monitor._get_version(),
                'python_version': self._get_python_version(),
                'build_info': self._get_build_info(),
                'timestamp': datetime.now().isoformat()
            }
            
            return web.json_response(version_info)
        
        except Exception as e:
            self.logger.error(f"Version endpoint failed: {e}")
            return web.json_response(
                {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                },
                status=500
            )
    
    def _format_prometheus_metrics(self, metrics_data: Dict[str, Any]) -> str:
        """Format metrics data for Prometheus."""
        lines = []
        
        # Add metadata
        lines.append('# HELP claude_remote_client_info Information about Claude Remote Client')
        lines.append('# TYPE claude_remote_client_info gauge')
        lines.append(f'claude_remote_client_info{{version="{health_monitor._get_version()}"}} 1')
        lines.append('')
        
        # System metrics
        if 'system' in metrics_data:
            for metric_name, metric_data in metrics_data['system'].items():
                if isinstance(metric_data, dict) and 'current' in metric_data:
                    prometheus_name = f'claude_system_{metric_name}'
                    lines.append(f'# HELP {prometheus_name} System {metric_name}')
                    lines.append(f'# TYPE {prometheus_name} gauge')
                    lines.append(f'{prometheus_name} {metric_data["current"]}')
                    lines.append('')
        
        # Application metrics
        if 'metrics' in metrics_data:
            for metric_name, metric_data in metrics_data['metrics'].items():
                if isinstance(metric_data, dict):
                    if 'count' in metric_data:
                        prometheus_name = f'claude_{metric_name}_total'
                        lines.append(f'# HELP {prometheus_name} Total {metric_name}')
                        lines.append(f'# TYPE {prometheus_name} counter')
                        lines.append(f'{prometheus_name} {metric_data["count"]}')
                        lines.append('')
                    
                    if 'rate_per_minute' in metric_data:
                        prometheus_name = f'claude_{metric_name}_rate'
                        lines.append(f'# HELP {prometheus_name} Rate of {metric_name} per minute')
                        lines.append(f'# TYPE {prometheus_name} gauge')
                        lines.append(f'{prometheus_name} {metric_data["rate_per_minute"]}')
                        lines.append('')
        
        return '\n'.join(lines)
    
    def _get_python_version(self) -> str:
        """Get Python version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def _get_build_info(self) -> Dict[str, str]:
        """Get build information."""
        import os
        return {
            'build_date': os.environ.get('BUILD_DATE', 'unknown'),
            'vcs_ref': os.environ.get('VCS_REF', 'unknown'),
            'platform': os.environ.get('PLATFORM', 'unknown')
        }


# Global health server instance
health_server = HealthServer()


async def start_health_server(host: str = '0.0.0.0', port: int = 8080) -> None:
    """
    Start the health server.
    
    Args:
        host: Server host
        port: Server port
    """
    global health_server
    health_server = HealthServer(host, port)
    await health_server.start()


async def stop_health_server() -> None:
    """Stop the health server."""
    global health_server
    if health_server:
        await health_server.stop()