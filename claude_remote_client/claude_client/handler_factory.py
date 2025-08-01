"""
Handler factory for creating Claude communication handlers.

This module provides a factory for creating the appropriate Claude handler
based on configuration, supporting subprocess, MCP, and hybrid modes.
"""

import logging
from typing import Optional, Dict, Any

from .handler_interface import ClaudeHandlerInterface, HandlerType, HandlerFactory
from ..config import Config
from ..exceptions import ConfigurationError


class ClaudeHandlerFactory:
    """
    Factory for creating Claude handlers based on configuration.
    
    This factory abstracts the creation of different handler types and
    provides a unified interface for the application to create handlers
    without knowing the specific implementation details.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._ensure_handlers_registered()
    
    def _ensure_handlers_registered(self) -> None:
        """Ensure all available handlers are registered."""
        try:
            # Import handlers to trigger registration
            from . import subprocess_handler
            from . import mcp_handler
            from . import hybrid_handler
            
            self.logger.debug("All handlers imported and registered")
        except ImportError as e:
            self.logger.warning(f"Some handlers could not be imported: {e}")
    
    def create_handler(self, config: Config) -> ClaudeHandlerInterface:
        """
        Create a Claude handler based on configuration.
        
        Args:
            config: Application configuration
        
        Returns:
            Configured Claude handler instance
        
        Raises:
            ConfigurationError: If handler type is invalid or unavailable
        """
        handler_type_str = config.claude.handler_type.lower()
        
        # Map string to enum
        handler_type_map = {
            'subprocess': HandlerType.SUBPROCESS,
            'mcp': HandlerType.MCP,
            'hybrid': HandlerType.HYBRID
        }
        
        if handler_type_str not in handler_type_map:
            raise ConfigurationError(
                f"Invalid handler type: {handler_type_str}. "
                f"Valid options: {list(handler_type_map.keys())}"
            )
        
        handler_type = handler_type_map[handler_type_str]
        
        # Check if handler is available
        available_handlers = HandlerFactory.get_available_handlers()
        if handler_type not in available_handlers:
            raise ConfigurationError(
                f"Handler type {handler_type_str} is not available. "
                f"Available handlers: {[ht.value for ht in available_handlers]}"
            )
        
        try:
            # Create handler instance
            handler = HandlerFactory.create_handler(handler_type, config)
            
            self.logger.info(f"Created {handler_type_str} handler")
            return handler
            
        except Exception as e:
            raise ConfigurationError(f"Failed to create {handler_type_str} handler: {str(e)}")
    
    def get_available_handler_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about available handler types.
        
        Returns:
            Dictionary mapping handler type names to their information
        """
        available_handlers = HandlerFactory.get_available_handlers()
        
        handler_info = {}
        
        for handler_type in available_handlers:
            info = {
                'name': handler_type.value,
                'description': self._get_handler_description(handler_type),
                'requirements': self._get_handler_requirements(handler_type),
                'capabilities': self._get_handler_capabilities_info(handler_type)
            }
            handler_info[handler_type.value] = info
        
        return handler_info
    
    def _get_handler_description(self, handler_type: HandlerType) -> str:
        """Get description for a handler type."""
        descriptions = {
            HandlerType.SUBPROCESS: (
                "Uses Claude CLI subprocess for communication. "
                "Requires Claude CLI to be installed and accessible."
            ),
            HandlerType.MCP: (
                "Uses Model Context Protocol for native Claude integration. "
                "Provides enhanced capabilities and performance."
            ),
            HandlerType.HYBRID: (
                "Automatically selects between subprocess and MCP based on availability. "
                "Provides fallback capabilities for maximum reliability."
            )
        }
        return descriptions.get(handler_type, "Unknown handler type")
    
    def _get_handler_requirements(self, handler_type: HandlerType) -> Dict[str, Any]:
        """Get requirements for a handler type."""
        requirements = {
            HandlerType.SUBPROCESS: {
                'claude_cli': True,
                'mcp_server': False,
                'network_access': False
            },
            HandlerType.MCP: {
                'claude_cli': False,
                'mcp_server': True,
                'network_access': True
            },
            HandlerType.HYBRID: {
                'claude_cli': True,  # At least one is required
                'mcp_server': True,  # At least one is required
                'network_access': True
            }
        }
        return requirements.get(handler_type, {})
    
    def _get_handler_capabilities_info(self, handler_type: HandlerType) -> Dict[str, Any]:
        """Get capabilities information for a handler type."""
        capabilities = {
            HandlerType.SUBPROCESS: {
                'streaming': True,
                'file_upload': True,
                'session_persistence': True,
                'concurrent_sessions': True,
                'interactive_mode': True,
                'batch_processing': False,
                'custom_tools': False,
                'mcp_servers': False
            },
            HandlerType.MCP: {
                'streaming': True,
                'file_upload': True,
                'session_persistence': True,
                'concurrent_sessions': True,
                'interactive_mode': True,
                'batch_processing': True,
                'custom_tools': True,
                'mcp_servers': True
            },
            HandlerType.HYBRID: {
                'streaming': True,
                'file_upload': True,
                'session_persistence': True,
                'concurrent_sessions': True,
                'interactive_mode': True,
                'batch_processing': True,  # If MCP is available
                'custom_tools': True,      # If MCP is available
                'mcp_servers': True        # If MCP is available
            }
        }
        return capabilities.get(handler_type, {})
    
    def validate_handler_config(self, config: Config) -> Dict[str, Any]:
        """
        Validate handler configuration and return validation results.
        
        Args:
            config: Configuration to validate
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'handler_type': config.claude.handler_type,
            'requirements_met': {}
        }
        
        handler_type_str = config.claude.handler_type.lower()
        
        # Check if handler type is valid
        if handler_type_str not in ['subprocess', 'mcp', 'hybrid']:
            results['valid'] = False
            results['errors'].append(f"Invalid handler type: {handler_type_str}")
            return results
        
        # Check specific requirements
        if handler_type_str in ['subprocess', 'hybrid']:
            # Check Claude CLI availability
            try:
                config.validate_claude_cli()
                results['requirements_met']['claude_cli'] = True
            except Exception as e:
                results['requirements_met']['claude_cli'] = False
                if handler_type_str == 'subprocess':
                    results['valid'] = False
                    results['errors'].append(f"Claude CLI not available: {str(e)}")
                else:
                    results['warnings'].append(f"Claude CLI not available for hybrid mode: {str(e)}")
        
        if handler_type_str in ['mcp', 'hybrid']:
            # Check MCP configuration
            if not config.claude.mcp_server_uri:
                results['requirements_met']['mcp_server'] = False
                if handler_type_str == 'mcp':
                    results['valid'] = False
                    results['errors'].append("MCP server URI is required for MCP mode")
                else:
                    results['warnings'].append("MCP server URI not configured for hybrid mode")
            else:
                results['requirements_met']['mcp_server'] = True
        
        return results
    
    def recommend_handler_type(self, config: Config) -> Dict[str, Any]:
        """
        Recommend the best handler type based on current configuration and environment.
        
        Args:
            config: Current configuration
        
        Returns:
            Dictionary with recommendation information
        """
        validation_results = {}
        
        # Test each handler type
        for handler_type in ['subprocess', 'mcp', 'hybrid']:
            test_config = Config(
                claude=config.claude,
                slack=config.slack,
                projects=config.projects
            )
            test_config.claude.handler_type = handler_type
            
            validation_results[handler_type] = self.validate_handler_config(test_config)
        
        # Determine recommendation
        recommendation = {
            'recommended': 'hybrid',  # Default recommendation
            'reason': 'Provides maximum flexibility and reliability',
            'alternatives': [],
            'validation_results': validation_results
        }
        
        # If hybrid is not available, recommend based on what's available
        if not validation_results['hybrid']['valid']:
            if validation_results['mcp']['valid']:
                recommendation['recommended'] = 'mcp'
                recommendation['reason'] = 'MCP provides enhanced capabilities'
            elif validation_results['subprocess']['valid']:
                recommendation['recommended'] = 'subprocess'
                recommendation['reason'] = 'Subprocess is the most reliable fallback'
            else:
                recommendation['recommended'] = None
                recommendation['reason'] = 'No handlers are currently available'
        
        # Add alternatives
        for handler_type, results in validation_results.items():
            if results['valid'] and handler_type != recommendation['recommended']:
                # Map string to enum
                handler_type_enum = {
                    'subprocess': HandlerType.SUBPROCESS,
                    'mcp': HandlerType.MCP,
                    'hybrid': HandlerType.HYBRID
                }.get(handler_type)
                
                if handler_type_enum:
                    recommendation['alternatives'].append({
                        'type': handler_type,
                        'reason': self._get_handler_description(handler_type_enum)
                    })
        
        return recommendation


# Global factory instance
claude_handler_factory = ClaudeHandlerFactory()


def create_claude_handler(config: Config) -> ClaudeHandlerInterface:
    """
    Convenience function to create a Claude handler.
    
    Args:
        config: Application configuration
    
    Returns:
        Configured Claude handler instance
    """
    return claude_handler_factory.create_handler(config)


def get_handler_recommendations(config: Config) -> Dict[str, Any]:
    """
    Get handler type recommendations for the given configuration.
    
    Args:
        config: Application configuration
    
    Returns:
        Dictionary with recommendations
    """
    return claude_handler_factory.recommend_handler_type(config)