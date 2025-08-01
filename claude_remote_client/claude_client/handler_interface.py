"""
Abstract interface for Claude interaction handlers.

This module defines the interface that both subprocess and future MCP
implementations must satisfy, enabling seamless migration between handlers.

The design supports a plugin architecture where different Claude communication
methods can be swapped without changing the core application logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from ..models import SessionStatus


class HandlerType(Enum):
    """Types of Claude handlers available."""
    SUBPROCESS = "subprocess"
    MCP = "mcp"  # Model Context Protocol
    HYBRID = "hybrid"  # Hybrid mode supporting both


@dataclass
class HandlerCapabilities:
    """Describes the capabilities of a Claude handler."""
    streaming: bool = True
    context_window: int = 200000  # Default context window size
    file_upload: bool = True
    models: List[str] = None
    session_persistence: bool = True
    concurrent_sessions: bool = True
    interactive_mode: bool = True
    batch_processing: bool = False
    custom_tools: bool = False
    mcp_servers: bool = False
    
    def __post_init__(self):
        if self.models is None:
            self.models = ["claude-3-5-sonnet-20241022"]


@dataclass
class SessionInfo:
    """Information about a Claude session."""
    session_id: str
    handler_type: HandlerType
    status: SessionStatus
    created_at: datetime
    last_activity: datetime
    message_count: int
    context_size: int
    project_path: Optional[str] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ClaudeHandlerInterface(ABC):
    """
    Abstract interface for Claude interaction handlers.
    
    This interface defines the contract that all Claude handlers must implement,
    whether they use subprocess CLI or future MCP API.
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the handler.
        
        This method should set up any required resources, connections,
        or configurations needed for the handler to operate.
        """
        pass
    
    @abstractmethod
    async def start_session(
        self,
        project_path: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Start a new Claude session.
        
        Args:
            project_path: Path to the project directory
            session_id: Optional session ID to resume
            **kwargs: Additional handler-specific arguments
        
        Returns:
            Session identifier
        """
        pass
    
    @abstractmethod
    async def send_message(self, message: str, **kwargs) -> str:
        """
        Send a message to Claude and get response.
        
        Args:
            message: The message to send
            **kwargs: Additional handler-specific arguments
        
        Returns:
            Claude's response
        """
        pass
    
    @abstractmethod
    async def stream_message(
        self,
        message: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Send a message and stream the response.
        
        Args:
            message: The message to send
            **kwargs: Additional handler-specific arguments
        
        Yields:
            Response chunks as they arrive
        """
        pass
    
    @abstractmethod
    async def end_session(self) -> None:
        """End the current session and cleanup resources."""
        pass
    
    @abstractmethod
    async def get_session_info(self) -> SessionInfo:
        """
        Get information about the current session.
        
        Returns:
            SessionInfo object containing session details
        """
        pass
    
    @abstractmethod
    async def is_healthy(self) -> bool:
        """
        Check if the handler is healthy and operational.
        
        Returns:
            True if handler is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_context_info(self) -> Dict[str, Any]:
        """
        Get information about the current context.
        
        Returns:
            Dictionary containing context information:
            - total_tokens: Total tokens in context
            - max_tokens: Maximum allowed tokens
            - files_loaded: Number of files in context
            - Additional handler-specific context info
        """
        pass
    
    @abstractmethod
    async def clear_context(self) -> None:
        """Clear the current context while maintaining session."""
        pass
    
    @abstractmethod
    async def add_context_file(self, file_path: str, content: str) -> None:
        """
        Add a file to the session context.
        
        Args:
            file_path: Path of the file
            content: Content of the file
        """
        pass
    
    @abstractmethod
    async def execute_command(
        self,
        command: str,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a command/prompt and return structured result.
        
        Args:
            command: Command to execute
            timeout: Optional timeout in seconds
        
        Returns:
            Dictionary containing:
            - success: Whether command executed successfully
            - output: Command output/response
            - error: Any error message
            - metadata: Additional metadata
        """
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> HandlerCapabilities:
        """
        Get handler capabilities and limitations.
        
        Returns:
            HandlerCapabilities object describing what this handler supports
        """
        pass
    
    # Optional methods with default implementations
    
    async def pause_session(self) -> None:
        """Pause the current session (if supported)."""
        pass
    
    async def resume_session(self, session_id: str) -> None:
        """Resume a paused session (if supported)."""
        pass
    
    async def export_conversation(self) -> List[Dict[str, str]]:
        """
        Export the conversation history.
        
        Returns:
            List of message dictionaries with 'role' and 'content'
        """
        return []
    
    async def set_model(self, model: str) -> None:
        """
        Change the model being used (if supported).
        
        Args:
            model: Model identifier
        """
        pass
    
    async def set_temperature(self, temperature: float) -> None:
        """
        Set the temperature parameter (if supported).
        
        Args:
            temperature: Temperature value (0.0 to 1.0)
        """
        pass
    
    async def cleanup(self) -> None:
        """
        Cleanup handler resources.
        
        This is called when the handler is being disposed of.
        Subclasses should override to perform cleanup.
        """
        await self.end_session()


class HandlerFactory:
    """Factory for creating Claude handlers."""
    
    _handlers: Dict[HandlerType, type] = {}
    
    @classmethod
    def register_handler(
        cls,
        handler_type: HandlerType,
        handler_class: type
    ) -> None:
        """
        Register a handler implementation.
        
        Args:
            handler_type: Type of handler
            handler_class: Handler class implementing ClaudeHandlerInterface
        """
        if not issubclass(handler_class, ClaudeHandlerInterface):
            raise TypeError(
                f"{handler_class} must implement ClaudeHandlerInterface"
            )
        cls._handlers[handler_type] = handler_class
    
    @classmethod
    def create_handler(
        cls,
        handler_type: HandlerType,
        config: Any
    ) -> ClaudeHandlerInterface:
        """
        Create a handler instance.
        
        Args:
            handler_type: Type of handler to create
            config: Configuration for the handler
        
        Returns:
            Handler instance
        
        Raises:
            ValueError: If handler type is not registered
        """
        if handler_type not in cls._handlers:
            raise ValueError(
                f"Handler type {handler_type} not registered. "
                f"Available types: {list(cls._handlers.keys())}"
            )
        
        handler_class = cls._handlers[handler_type]
        return handler_class(config)
    
    @classmethod
    def get_available_handlers(cls) -> List[HandlerType]:
        """Get list of available handler types."""
        return list(cls._handlers.keys())


# Auto-register handlers when available
def _register_available_handlers():
    """Register all available handlers with the factory."""
    try:
        from .subprocess_handler import SubprocessClaudeHandler
        HandlerFactory.register_handler(HandlerType.SUBPROCESS, SubprocessClaudeHandler)
    except ImportError:
        pass  # Subprocess handler not available
    
    try:
        from .mcp_handler import MCPClaudeHandler
        HandlerFactory.register_handler(HandlerType.MCP, MCPClaudeHandler)
    except ImportError:
        pass  # MCP handler not available
    
    try:
        from .hybrid_handler import HybridClaudeHandler
        HandlerFactory.register_handler(HandlerType.HYBRID, HybridClaudeHandler)
    except ImportError:
        pass  # Hybrid handler not available

# Register handlers on module import
_register_available_handlers()