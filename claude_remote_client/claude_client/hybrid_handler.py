"""
Hybrid handler that can switch between subprocess and MCP modes.

This handler provides a seamless transition between subprocess and MCP
implementations, allowing users to benefit from both approaches based
on availability and requirements.
"""

import asyncio
import logging
from typing import Optional, AsyncIterator, Dict, Any, List, Union
from datetime import datetime

from .handler_interface import (
    ClaudeHandlerInterface, 
    HandlerType, 
    HandlerCapabilities, 
    SessionInfo
)
from .subprocess_handler import SubprocessClaudeHandler
from .mcp_handler import MCPClaudeHandler
from ..models import SessionStatus
from ..config import Config
from ..exceptions import ClaudeProcessError, SessionError


class HybridClaudeHandler(ClaudeHandlerInterface):
    """
    Hybrid handler that can use both subprocess and MCP modes.
    
    This handler automatically selects the best available communication
    method based on configuration and runtime conditions. It can fall
    back between methods if one becomes unavailable.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the hybrid handler.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Handler instances
        self.subprocess_handler: Optional[SubprocessClaudeHandler] = None
        self.mcp_handler: Optional[MCPClaudeHandler] = None
        self.active_handler: Optional[ClaudeHandlerInterface] = None
        self.active_handler_type: Optional[HandlerType] = None
        
        # Configuration
        self.prefer_mcp = getattr(config.claude, 'prefer_mcp', True)
        self.fallback_enabled = getattr(config.claude, 'fallback_to_subprocess', True)
        
        # State tracking
        self.initialization_attempted = {'mcp': False, 'subprocess': False}
        self.initialization_successful = {'mcp': False, 'subprocess': False}
        self.last_fallback_time: Optional[datetime] = None
        self.fallback_cooldown = 60  # seconds
    
    async def initialize(self) -> None:
        """
        Initialize the hybrid handler by setting up available handlers.
        
        Raises:
            ClaudeProcessError: If no handlers can be initialized
        """
        self.logger.info("Initializing hybrid handler...")
        
        # Try to initialize handlers based on preference
        if self.prefer_mcp:
            await self._try_initialize_mcp()
            if not self.initialization_successful['mcp']:
                await self._try_initialize_subprocess()
        else:
            await self._try_initialize_subprocess()
            if not self.initialization_successful['subprocess']:
                await self._try_initialize_mcp()
        
        # Select active handler
        await self._select_active_handler()
        
        if not self.active_handler:
            raise ClaudeProcessError(
                "Failed to initialize any Claude handler. "
                "Check your configuration and ensure Claude CLI or MCP server is available."
            )
        
        self.logger.info(f"Hybrid handler initialized with {self.active_handler_type.value} as active")
    
    async def _try_initialize_mcp(self) -> None:
        """Try to initialize MCP handler."""
        if self.initialization_attempted['mcp']:
            return
        
        self.initialization_attempted['mcp'] = True
        
        try:
            self.logger.info("Attempting to initialize MCP handler...")
            self.mcp_handler = MCPClaudeHandler(self.config)
            await self.mcp_handler.initialize()
            self.initialization_successful['mcp'] = True
            self.logger.info("MCP handler initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize MCP handler: {e}")
            self.mcp_handler = None
    
    async def _try_initialize_subprocess(self) -> None:
        """Try to initialize subprocess handler."""
        if self.initialization_attempted['subprocess']:
            return
        
        self.initialization_attempted['subprocess'] = True
        
        try:
            self.logger.info("Attempting to initialize subprocess handler...")
            # Note: SubprocessClaudeHandler doesn't have an initialize method in current implementation
            # This is a design consideration for the evolution
            self.subprocess_handler = SubprocessClaudeHandler(self.config.claude)
            self.initialization_successful['subprocess'] = True
            self.logger.info("Subprocess handler initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize subprocess handler: {e}")
            self.subprocess_handler = None
    
    async def _select_active_handler(self) -> None:
        """Select the active handler based on availability and preference."""
        if self.prefer_mcp and self.initialization_successful['mcp']:
            self.active_handler = self.mcp_handler
            self.active_handler_type = HandlerType.MCP
        elif self.initialization_successful['subprocess']:
            self.active_handler = self.subprocess_handler
            self.active_handler_type = HandlerType.SUBPROCESS
        elif self.initialization_successful['mcp']:
            self.active_handler = self.mcp_handler
            self.active_handler_type = HandlerType.MCP
        else:
            self.active_handler = None
            self.active_handler_type = None
    
    async def _try_fallback(self) -> bool:
        """
        Try to fall back to alternative handler.
        
        Returns:
            True if fallback was successful, False otherwise
        """
        if not self.fallback_enabled:
            return False
        
        # Check cooldown
        if (self.last_fallback_time and 
            (datetime.now() - self.last_fallback_time).total_seconds() < self.fallback_cooldown):
            return False
        
        self.last_fallback_time = datetime.now()
        
        # Try alternative handler
        if self.active_handler_type == HandlerType.MCP:
            if self.initialization_successful['subprocess']:
                self.logger.info("Falling back from MCP to subprocess handler")
                self.active_handler = self.subprocess_handler
                self.active_handler_type = HandlerType.SUBPROCESS
                return True
            else:
                # Try to initialize subprocess if not done yet
                await self._try_initialize_subprocess()
                if self.initialization_successful['subprocess']:
                    self.active_handler = self.subprocess_handler
                    self.active_handler_type = HandlerType.SUBPROCESS
                    return True
        
        elif self.active_handler_type == HandlerType.SUBPROCESS:
            if self.initialization_successful['mcp']:
                self.logger.info("Falling back from subprocess to MCP handler")
                self.active_handler = self.mcp_handler
                self.active_handler_type = HandlerType.MCP
                return True
            else:
                # Try to initialize MCP if not done yet
                await self._try_initialize_mcp()
                if self.initialization_successful['mcp']:
                    self.active_handler = self.mcp_handler
                    self.active_handler_type = HandlerType.MCP
                    return True
        
        return False
    
    async def _execute_with_fallback(self, operation_name: str, operation_func):
        """
        Execute an operation with automatic fallback on failure.
        
        Args:
            operation_name: Name of the operation for logging
            operation_func: Async function to execute
        
        Returns:
            Result of the operation
        
        Raises:
            Exception: If operation fails on all available handlers
        """
        if not self.active_handler:
            raise ClaudeProcessError("No active handler available")
        
        try:
            return await operation_func(self.active_handler)
        except Exception as e:
            self.logger.warning(f"{operation_name} failed on {self.active_handler_type.value}: {e}")
            
            # Try fallback
            if await self._try_fallback():
                self.logger.info(f"Retrying {operation_name} with {self.active_handler_type.value}")
                try:
                    return await operation_func(self.active_handler)
                except Exception as fallback_error:
                    self.logger.error(f"{operation_name} also failed on fallback handler: {fallback_error}")
                    raise fallback_error
            else:
                raise e
    
    async def start_session(
        self,
        project_path: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Start a new Claude session using the active handler."""
        async def _start_session(handler):
            return await handler.start_session(project_path, session_id, **kwargs)
        
        return await self._execute_with_fallback("start_session", _start_session)
    
    async def send_message(self, message: str, **kwargs) -> str:
        """Send a message using the active handler."""
        async def _send_message(handler):
            return await handler.send_message(message, **kwargs)
        
        return await self._execute_with_fallback("send_message", _send_message)
    
    async def stream_message(
        self,
        message: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a message using the active handler."""
        if not self.active_handler:
            raise ClaudeProcessError("No active handler available")
        
        try:
            async for chunk in self.active_handler.stream_message(message, **kwargs):
                yield chunk
        except Exception as e:
            self.logger.warning(f"stream_message failed on {self.active_handler_type.value}: {e}")
            
            # Try fallback for streaming
            if await self._try_fallback():
                self.logger.info(f"Retrying stream_message with {self.active_handler_type.value}")
                async for chunk in self.active_handler.stream_message(message, **kwargs):
                    yield chunk
            else:
                raise e
    
    async def end_session(self) -> None:
        """End the current session on the active handler."""
        if self.active_handler:
            await self.active_handler.end_session()
    
    async def get_session_info(self) -> SessionInfo:
        """Get session information from the active handler."""
        if not self.active_handler:
            raise SessionError("No active handler available")
        
        session_info = await self.active_handler.get_session_info()
        # Update handler type to reflect hybrid nature
        session_info.handler_type = HandlerType.HYBRID
        session_info.metadata = session_info.metadata or {}
        session_info.metadata.update({
            'active_handler': self.active_handler_type.value,
            'available_handlers': [
                ht.value for ht, available in self.initialization_successful.items() 
                if available
            ],
            'fallback_enabled': self.fallback_enabled
        })
        return session_info
    
    async def is_healthy(self) -> bool:
        """Check if the active handler is healthy."""
        if not self.active_handler:
            return False
        
        try:
            return await self.active_handler.is_healthy()
        except Exception:
            # Try fallback if health check fails
            if await self._try_fallback():
                try:
                    return await self.active_handler.is_healthy()
                except Exception:
                    return False
            return False
    
    async def get_context_info(self) -> Dict[str, Any]:
        """Get context information from the active handler."""
        async def _get_context_info(handler):
            return await handler.get_context_info()
        
        context_info = await self._execute_with_fallback("get_context_info", _get_context_info)
        context_info['active_handler'] = self.active_handler_type.value
        return context_info
    
    async def clear_context(self) -> None:
        """Clear context on the active handler."""
        async def _clear_context(handler):
            return await handler.clear_context()
        
        await self._execute_with_fallback("clear_context", _clear_context)
    
    async def add_context_file(self, file_path: str, content: str) -> None:
        """Add a file to context using the active handler."""
        async def _add_context_file(handler):
            return await handler.add_context_file(file_path, content)
        
        await self._execute_with_fallback("add_context_file", _add_context_file)
    
    async def execute_command(
        self,
        command: str,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute a command using the active handler."""
        async def _execute_command(handler):
            return await handler.execute_command(command, timeout)
        
        result = await self._execute_with_fallback("execute_command", _execute_command)
        result['metadata'] = result.get('metadata', {})
        result['metadata']['handler_type'] = self.active_handler_type.value
        return result
    
    async def get_capabilities(self) -> HandlerCapabilities:
        """Get combined capabilities of available handlers."""
        if not self.active_handler:
            raise ClaudeProcessError("No active handler available")
        
        active_capabilities = await self.active_handler.get_capabilities()
        
        # If we have both handlers, combine capabilities
        if (self.initialization_successful['mcp'] and 
            self.initialization_successful['subprocess']):
            
            # Get capabilities from both handlers
            mcp_caps = await self.mcp_handler.get_capabilities()
            subprocess_caps = await self.subprocess_handler.get_capabilities()
            
            # Combine capabilities (take the best of both)
            combined_capabilities = HandlerCapabilities(
                streaming=mcp_caps.streaming or subprocess_caps.streaming,
                context_window=max(mcp_caps.context_window, subprocess_caps.context_window),
                file_upload=mcp_caps.file_upload or subprocess_caps.file_upload,
                models=list(set(mcp_caps.models + subprocess_caps.models)),
                session_persistence=mcp_caps.session_persistence or subprocess_caps.session_persistence,
                concurrent_sessions=mcp_caps.concurrent_sessions or subprocess_caps.concurrent_sessions,
                interactive_mode=mcp_caps.interactive_mode or subprocess_caps.interactive_mode,
                batch_processing=mcp_caps.batch_processing or subprocess_caps.batch_processing,
                custom_tools=mcp_caps.custom_tools or subprocess_caps.custom_tools,
                mcp_servers=mcp_caps.mcp_servers or subprocess_caps.mcp_servers
            )
            
            return combined_capabilities
        
        return active_capabilities
    
    async def set_model(self, model: str) -> None:
        """Set model on the active handler."""
        async def _set_model(handler):
            return await handler.set_model(model)
        
        await self._execute_with_fallback("set_model", _set_model)
    
    async def set_temperature(self, temperature: float) -> None:
        """Set temperature on the active handler."""
        async def _set_temperature(handler):
            return await handler.set_temperature(temperature)
        
        await self._execute_with_fallback("set_temperature", _set_temperature)
    
    async def cleanup(self) -> None:
        """Cleanup all handlers."""
        if self.mcp_handler:
            try:
                await self.mcp_handler.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up MCP handler: {e}")
        
        if self.subprocess_handler:
            try:
                await self.subprocess_handler.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up subprocess handler: {e}")
        
        self.active_handler = None
        self.active_handler_type = None
    
    def get_handler_status(self) -> Dict[str, Any]:
        """
        Get status of all handlers.
        
        Returns:
            Dictionary with handler status information
        """
        return {
            'active_handler': self.active_handler_type.value if self.active_handler_type else None,
            'available_handlers': {
                'mcp': {
                    'initialized': self.initialization_successful['mcp'],
                    'available': self.mcp_handler is not None
                },
                'subprocess': {
                    'initialized': self.initialization_successful['subprocess'],
                    'available': self.subprocess_handler is not None
                }
            },
            'configuration': {
                'prefer_mcp': self.prefer_mcp,
                'fallback_enabled': self.fallback_enabled,
                'fallback_cooldown': self.fallback_cooldown
            },
            'last_fallback_time': self.last_fallback_time.isoformat() if self.last_fallback_time else None
        }


# Register hybrid handler with factory when module is imported
try:
    from .handler_interface import HandlerFactory
    HandlerFactory.register_handler(HandlerType.HYBRID, HybridClaudeHandler)
except ImportError:
    pass  # Factory not available