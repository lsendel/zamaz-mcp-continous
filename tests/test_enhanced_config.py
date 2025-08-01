"""
Tests for enhanced configuration management.
"""

import pytest
from pathlib import Path
import tempfile
import json
import yaml
from unittest.mock import patch, mock_open

from claude_remote_client.enhanced_config import (
    CacheConfig,
    PerformanceConfig,
    LoggingConfig,
    MonitoringConfig,
    SecurityConfig,
    EnhancedConfig,
    load_enhanced_config,
    create_enhanced_config_template
)
from claude_remote_client.config import SlackConfig, ClaudeConfig, ProjectConfig
from claude_remote_client.exceptions import ConfigurationError


class TestCacheConfig:
    """Test cases for CacheConfig."""
    
    def test_cache_config_defaults(self):
        """Test CacheConfig default values."""
        config = CacheConfig()
        
        assert config.session_cache_size == 1000
        assert config.session_cache_ttl == 3600
        assert config.response_cache_size == 1000
        assert config.response_cache_ttl == 300
        assert config.enable_response_caching is True
        assert config.cache_cleanup_interval == 300
    
    def test_cache_config_custom_values(self):
        """Test CacheConfig with custom values."""
        config = CacheConfig(
            session_cache_size=2000,
            session_cache_ttl=7200,
            enable_response_caching=False
        )
        
        assert config.session_cache_size == 2000
        assert config.session_cache_ttl == 7200
        assert config.enable_response_caching is False


class TestPerformanceConfig:
    """Test cases for PerformanceConfig."""
    
    def test_performance_config_defaults(self):
        """Test PerformanceConfig default values."""
        config = PerformanceConfig()
        
        assert config.enable_connection_pooling is True
        assert config.connection_pool_size == 10
        assert config.enable_rate_limiting is True
        assert config.claude_api_rate_limit == 10.0
        assert config.enable_batch_processing is True
        assert config.batch_size == 100
        assert config.enable_memory_optimization is True
        assert config.max_conversation_history == 100
    
    def test_performance_config_custom_values(self):
        """Test PerformanceConfig with custom values."""
        config = PerformanceConfig(
            enable_connection_pooling=False,
            claude_api_rate_limit=5.0,
            batch_size=50
        )
        
        assert config.enable_connection_pooling is False
        assert config.claude_api_rate_limit == 5.0
        assert config.batch_size == 50


class TestLoggingConfig:
    """Test cases for LoggingConfig."""
    
    def test_logging_config_defaults(self):
        """Test LoggingConfig default values."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.console_enabled is True
        assert config.file_enabled is True
        assert config.performance_logging_enabled is True
        assert config.enable_async_logging is True
    
    def test_logging_config_custom_values(self):
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(
            level="DEBUG",
            performance_logging_enabled=False,
            enable_async_logging=False
        )
        
        assert config.level == "DEBUG"
        assert config.performance_logging_enabled is False
        assert config.enable_async_logging is False
    
    def test_logging_config_to_dict(self):
        """Test LoggingConfig to_dict method."""
        config = LoggingConfig()
        config_dict = config.to_dict()
        
        assert config_dict['level'] == 'INFO'
        assert config_dict['console']['enabled'] is True
        assert config_dict['file']['enabled'] is True


class TestSecurityConfig:
    """Test cases for SecurityConfig."""
    
    def test_security_config_defaults(self):
        """Test SecurityConfig default values."""
        config = SecurityConfig()
        
        assert config.enable_input_sanitization is True
        assert config.max_message_length == 10000
        assert config.require_ssl is True
        assert config.session_timeout == 3600
    
    def test_security_config_custom_values(self):
        """Test SecurityConfig with custom values."""
        config = SecurityConfig(
            max_message_length=5000,
            session_timeout=1800,
            require_ssl=False
        )
        
        assert config.max_message_length == 5000
        assert config.session_timeout == 1800
        assert config.require_ssl is False


class TestMonitoringConfig:
    """Test cases for MonitoringConfig."""
    
    def test_monitoring_config_defaults(self):
        """Test MonitoringConfig default values."""
        config = MonitoringConfig()
        
        assert config.enable_health_checks is True
        assert config.health_check_interval == 60
        assert config.enable_metrics_export is True
        assert config.metrics_export_interval == 300
        assert config.enable_alerting is False
    
    def test_monitoring_config_custom_values(self):
        """Test MonitoringConfig with custom values."""
        config = MonitoringConfig(
            enable_health_checks=False,
            health_check_interval=120,
            enable_alerting=True
        )
        
        assert config.enable_health_checks is False
        assert config.health_check_interval == 120
        assert config.enable_alerting is True


class TestEnhancedConfig:
    """Test cases for EnhancedConfig."""
    
    def test_enhanced_config_creation(self):
        """Test creating EnhancedConfig with all components."""
        slack_config = SlackConfig(bot_token="test-token")
        claude_config = ClaudeConfig(cli_path="/usr/bin/claude")
        
        config = EnhancedConfig(
            slack=slack_config,
            claude=claude_config
        )
        
        assert config.slack.bot_token == "test-token"
        assert config.claude.cli_path == "/usr/bin/claude"
        assert isinstance(config.caching, CacheConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.monitoring, MonitoringConfig)
        assert isinstance(config.security, SecurityConfig)
    
    def test_enhanced_config_methods(self):
        """Test EnhancedConfig methods."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        # Test get_logging_config
        log_config = config.get_logging_config()
        assert log_config['level'] == 'INFO'
        assert log_config['console']['enabled'] is True
        
        # Test feature flags
        assert config.enable_enhanced_session_manager is True
        assert config.enable_performance_optimizations is True
        assert config.enable_advanced_logging is True
        assert config.enable_monitoring is True


class TestConfigManagement:
    """Test cases for configuration management functions."""
    
    def test_load_enhanced_config_nonexistent(self):
        """Test loading config when file doesn't exist."""
        config = load_enhanced_config("/nonexistent/path/config.yaml")
        
        # Should return default config
        assert isinstance(config, EnhancedConfig)
        assert config.slack.bot_token == ""
    
    def test_get_security_config(self):
        """Test getting security configuration dictionary."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        sec_config = config.get_security_config()
        
        assert 'input_sanitization' in sec_config
        assert 'max_message_length' in sec_config
        assert 'ssl' in sec_config
        assert sec_config['max_message_length'] == 10000
    
    def test_get_monitoring_config(self):
        """Test getting monitoring configuration dictionary."""
        config = EnhancedConfig(
            slack=SlackConfig(bot_token="test-token"),
            claude=ClaudeConfig(cli_path="/usr/bin/claude")
        )
        
        mon_config = config.get_monitoring_config()
        
        assert 'health_checks' in mon_config
        assert 'metrics' in mon_config
        assert 'alerting' in mon_config
        assert mon_config['health_checks']['interval'] == 60