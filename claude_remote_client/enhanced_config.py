"""
Enhanced configuration management with performance and logging settings.

This module extends the base configuration with additional settings for:
- Enhanced logging configuration
- Performance optimization settings
- Caching configuration
- Rate limiting settings
- Memory management options
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import os

from .config import Config, SlackConfig, ClaudeConfig, ProjectConfig
from .logging_config import DEFAULT_LOGGING_CONFIG


@dataclass
class CacheConfig:
    """Configuration for caching systems."""
    session_cache_size: int = 1000
    session_cache_ttl: int = 3600  # 1 hour
    response_cache_size: int = 1000
    response_cache_ttl: int = 300   # 5 minutes
    enable_response_caching: bool = True
    cache_cleanup_interval: int = 300  # 5 minutes


@dataclass
class PerformanceConfig:
    """Configuration for performance optimizations."""
    enable_connection_pooling: bool = True
    connection_pool_size: int = 10
    connection_pool_min_size: int = 2
    connection_pool_max_idle_time: int = 300  # 5 minutes
    
    enable_rate_limiting: bool = True
    claude_api_rate_limit: float = 10.0  # requests per second
    claude_api_burst_limit: int = 20
    
    enable_batch_processing: bool = True
    batch_size: int = 100
    batch_max_wait_time: float = 1.0
    
    enable_memory_optimization: bool = True
    memory_optimization_interval: int = 600  # 10 minutes
    max_conversation_history: int = 100
    
    enable_metrics_collection: bool = True
    metrics_report_interval: int = 300  # 5 minutes


@dataclass
class LoggingConfig:
    """Enhanced logging configuration."""
    level: str = "INFO"
    
    # Console logging
    console_enabled: bool = True
    console_structured: bool = False
    
    # File logging
    file_enabled: bool = True
    file_path: str = "~/.claude-remote-client/logs/app.log"
    file_structured: bool = True
    file_max_bytes: int = 10 * 1024 * 1024  # 10MB
    file_backup_count: int = 5
    
    # Error file logging
    error_file_enabled: bool = True
    error_file_path: str = "~/.claude-remote-client/logs/errors.log"
    error_file_max_bytes: int = 5 * 1024 * 1024  # 5MB
    error_file_backup_count: int = 3
    
    # Performance logging
    performance_logging_enabled: bool = True
    performance_log_path: str = "~/.claude-remote-client/logs/performance.log"
    
    # Async logging
    enable_async_logging: bool = True
    async_queue_size: int = 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for logging setup."""
        return {
            'level': self.level,
            'console': {
                'enabled': self.console_enabled,
                'structured': self.console_structured
            },
            'file': {
                'enabled': self.file_enabled,
                'path': os.path.expanduser(self.file_path),
                'structured': self.file_structured,
                'max_bytes': self.file_max_bytes,
                'backup_count': self.file_backup_count
            },
            'error_file': {
                'enabled': self.error_file_enabled,
                'path': os.path.expanduser(self.error_file_path),
                'max_bytes': self.error_file_max_bytes,
                'backup_count': self.error_file_backup_count
            },
            'async_enabled': self.enable_async_logging,
            'async_queue_size': self.async_queue_size
        }


@dataclass
class SecurityConfig:
    """Security-related configuration."""
    enable_input_sanitization: bool = True
    max_message_length: int = 10000
    max_conversation_history_size: int = 1000
    enable_rate_limiting_per_user: bool = True
    user_rate_limit: float = 5.0  # requests per second per user
    
    # API security
    require_ssl: bool = True
    verify_ssl_certificates: bool = True
    
    # Session security
    session_timeout: int = 3600  # 1 hour
    max_idle_time: int = 1800   # 30 minutes


@dataclass
class MonitoringConfig:
    """Monitoring and health check configuration."""
    enable_health_checks: bool = True
    health_check_interval: int = 60  # 1 minute
    
    enable_metrics_export: bool = True
    metrics_export_interval: int = 300  # 5 minutes
    metrics_export_format: str = "json"  # json, prometheus
    
    enable_alerting: bool = False
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'memory_usage_mb': 1000,
        'cpu_usage_percent': 80,
        'error_rate_percent': 5,
        'response_time_seconds': 10
    })


@dataclass
class EnhancedConfig(Config):
    """Enhanced configuration with performance and logging settings."""
    
    # Enhanced configuration sections
    caching: CacheConfig = field(default_factory=CacheConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Feature flags
    enable_enhanced_session_manager: bool = True
    enable_performance_optimizations: bool = True
    enable_advanced_logging: bool = True
    enable_monitoring: bool = True
    
    def __post_init__(self):
        """Post-initialization setup."""
        super().__post_init__()
        
        # Ensure data directories exist
        self._ensure_directories()
        
        # Validate configuration
        self._validate_config()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.data_dir,
            Path(self.logging.file_path).parent,
            Path(self.logging.error_file_path).parent,
            Path(self.logging.performance_log_path).parent
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _validate_config(self):
        """Validate configuration settings."""
        # Validate cache settings
        if self.caching.session_cache_size <= 0:
            raise ValueError("Session cache size must be positive")
        
        if self.caching.response_cache_size <= 0:
            raise ValueError("Response cache size must be positive")
        
        # Validate performance settings
        if self.performance.claude_api_rate_limit <= 0:
            raise ValueError("API rate limit must be positive")
        
        if self.performance.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        
        # Validate logging settings
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging.level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.logging.level}")
        
        # Validate security settings
        if self.security.max_message_length <= 0:
            raise ValueError("Max message length must be positive")
        
        if self.security.session_timeout <= 0:
            raise ValueError("Session timeout must be positive")
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration dictionary."""
        return self.logging.to_dict()
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance configuration dictionary."""
        return {
            'connection_pooling': {
                'enabled': self.performance.enable_connection_pooling,
                'max_size': self.performance.connection_pool_size,
                'min_size': self.performance.connection_pool_min_size,
                'max_idle_time': self.performance.connection_pool_max_idle_time
            },
            'rate_limiting': {
                'enabled': self.performance.enable_rate_limiting,
                'claude_api_rate': self.performance.claude_api_rate_limit,
                'claude_api_burst': self.performance.claude_api_burst_limit
            },
            'caching': {
                'session_cache_size': self.caching.session_cache_size,
                'session_cache_ttl': self.caching.session_cache_ttl,
                'response_cache_size': self.caching.response_cache_size,
                'response_cache_ttl': self.caching.response_cache_ttl,
                'enable_response_caching': self.caching.enable_response_caching
            },
            'batch_processing': {
                'enabled': self.performance.enable_batch_processing,
                'batch_size': self.performance.batch_size,
                'max_wait_time': self.performance.batch_max_wait_time
            },
            'memory_optimization': {
                'enabled': self.performance.enable_memory_optimization,
                'optimization_interval': self.performance.memory_optimization_interval,
                'max_conversation_history': self.performance.max_conversation_history
            },
            'metrics': {
                'enabled': self.performance.enable_metrics_collection,
                'report_interval': self.performance.metrics_report_interval
            }
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration dictionary."""
        return {
            'input_sanitization': self.security.enable_input_sanitization,
            'max_message_length': self.security.max_message_length,
            'max_conversation_history_size': self.security.max_conversation_history_size,
            'rate_limiting_per_user': self.security.enable_rate_limiting_per_user,
            'user_rate_limit': self.security.user_rate_limit,
            'ssl': {
                'require_ssl': self.security.require_ssl,
                'verify_certificates': self.security.verify_ssl_certificates
            },
            'session': {
                'timeout': self.security.session_timeout,
                'max_idle_time': self.security.max_idle_time
            }
        }
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration dictionary."""
        return {
            'health_checks': {
                'enabled': self.monitoring.enable_health_checks,
                'interval': self.monitoring.health_check_interval
            },
            'metrics': {
                'export_enabled': self.monitoring.enable_metrics_export,
                'export_interval': self.monitoring.metrics_export_interval,
                'export_format': self.monitoring.metrics_export_format
            },
            'alerting': {
                'enabled': self.monitoring.enable_alerting,
                'thresholds': self.monitoring.alert_thresholds
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedConfig':
        """Create enhanced config from dictionary."""
        # Extract base config data
        base_data = {k: v for k, v in data.items() 
                    if k not in ['caching', 'performance', 'logging', 'security', 'monitoring']}
        
        # Create base config
        base_config = Config.from_dict(base_data)
        
        # Create enhanced config
        enhanced_config = cls(
            slack=base_config.slack,
            claude=base_config.claude,
            projects=base_config.projects,
            log_level=base_config.log_level,
            data_dir=base_config.data_dir,
            max_sessions=base_config.max_sessions,
            task_queue_size=base_config.task_queue_size
        )
        
        # Update enhanced sections if present
        if 'caching' in data:
            enhanced_config.caching = CacheConfig(**data['caching'])
        
        if 'performance' in data:
            enhanced_config.performance = PerformanceConfig(**data['performance'])
        
        if 'logging' in data:
            enhanced_config.logging = LoggingConfig(**data['logging'])
        
        if 'security' in data:
            enhanced_config.security = SecurityConfig(**data['security'])
        
        if 'monitoring' in data:
            enhanced_config.monitoring = MonitoringConfig(**data['monitoring'])
        
        return enhanced_config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        base_dict = super().to_dict()
        
        enhanced_dict = {
            **base_dict,
            'caching': {
                'session_cache_size': self.caching.session_cache_size,
                'session_cache_ttl': self.caching.session_cache_ttl,
                'response_cache_size': self.caching.response_cache_size,
                'response_cache_ttl': self.caching.response_cache_ttl,
                'enable_response_caching': self.caching.enable_response_caching,
                'cache_cleanup_interval': self.caching.cache_cleanup_interval
            },
            'performance': {
                'enable_connection_pooling': self.performance.enable_connection_pooling,
                'connection_pool_size': self.performance.connection_pool_size,
                'connection_pool_min_size': self.performance.connection_pool_min_size,
                'connection_pool_max_idle_time': self.performance.connection_pool_max_idle_time,
                'enable_rate_limiting': self.performance.enable_rate_limiting,
                'claude_api_rate_limit': self.performance.claude_api_rate_limit,
                'claude_api_burst_limit': self.performance.claude_api_burst_limit,
                'enable_batch_processing': self.performance.enable_batch_processing,
                'batch_size': self.performance.batch_size,
                'batch_max_wait_time': self.performance.batch_max_wait_time,
                'enable_memory_optimization': self.performance.enable_memory_optimization,
                'memory_optimization_interval': self.performance.memory_optimization_interval,
                'max_conversation_history': self.performance.max_conversation_history,
                'enable_metrics_collection': self.performance.enable_metrics_collection,
                'metrics_report_interval': self.performance.metrics_report_interval
            },
            'logging': self.logging.to_dict(),
            'security': {
                'enable_input_sanitization': self.security.enable_input_sanitization,
                'max_message_length': self.security.max_message_length,
                'max_conversation_history_size': self.security.max_conversation_history_size,
                'enable_rate_limiting_per_user': self.security.enable_rate_limiting_per_user,
                'user_rate_limit': self.security.user_rate_limit,
                'require_ssl': self.security.require_ssl,
                'verify_ssl_certificates': self.security.verify_ssl_certificates,
                'session_timeout': self.security.session_timeout,
                'max_idle_time': self.security.max_idle_time
            },
            'monitoring': {
                'enable_health_checks': self.monitoring.enable_health_checks,
                'health_check_interval': self.monitoring.health_check_interval,
                'enable_metrics_export': self.monitoring.enable_metrics_export,
                'metrics_export_interval': self.monitoring.metrics_export_interval,
                'metrics_export_format': self.monitoring.metrics_export_format,
                'enable_alerting': self.monitoring.enable_alerting,
                'alert_thresholds': self.monitoring.alert_thresholds
            },
            'feature_flags': {
                'enable_enhanced_session_manager': self.enable_enhanced_session_manager,
                'enable_performance_optimizations': self.enable_performance_optimizations,
                'enable_advanced_logging': self.enable_advanced_logging,
                'enable_monitoring': self.enable_monitoring
            }
        }
        
        return enhanced_dict


def load_enhanced_config(config_path: Optional[str] = None) -> EnhancedConfig:
    """Load enhanced configuration from file."""
    import yaml
    
    if config_path is None:
        config_path = os.path.expanduser("~/.claude-remote-client/config.yaml")
    
    if not os.path.exists(config_path):
        # Create default enhanced config
        return EnhancedConfig()
    
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    return EnhancedConfig.from_dict(data)


def create_enhanced_config_template(output_path: str) -> None:
    """Create an enhanced configuration template file."""
    template_config = EnhancedConfig()
    
    import yaml
    with open(output_path, 'w') as f:
        yaml.dump(template_config.to_dict(), f, default_flow_style=False, indent=2)
