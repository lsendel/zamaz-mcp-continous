"""
MCP (Model Context Protocol) handler for Claude communication.

This module implements the MCP protocol for native Claude integration,
providing enhanced capabilities and performance compared to subprocess.

This is a future implementation that will replace subprocess when MCP
becomes the primary integration method.
"""

import asyncio
import json
import logging
from typing import Optional, AsyncIterator, Dict, Any, List
from datetime import datetime
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None  # type: ignore
    StdioServerParameters = None  # type: ignore
    stdio_client = None  # type: ignore

from .handler_interface import (
    ClaudeHandlerInterface, 
    HandlerType, 
    HandlerCapabilities, 
    SessionInfo
)
from ..models import SessionStatus
from ..config import Config
from ..exceptions import ClaudeProcessError, SessionError


class MCPClaudeHandler(ClaudeHandlerInterface):
    """
    MCP-based Claude handler for native protocol communication.
    
    This handler implements the Model Context Protocol for direct
    communication with Claude, providing enhanced capabilities
    compared to subprocess-based communication.
    
    Note: This is a future implementation. The actual MCP protocol
    integration will be implemented when MCP becomes available.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the MCP handler.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # MCP connection state
        self.mcp_client = None
        self.mcp_session: Optional[ClientSession] = None
        self.session_id: Optional[str] = None
        self.is_connected = False
        
        # Session management
        self.current_session: Optional[SessionInfo] = None
        self.message_count = 0
        self.context_size = 0
        
        # MCP-specific settings
        self.server_uri = getattr(config, 'mcp_server_uri', 'mcp://localhost:8000')
        self.protocol_version = "1.0"
        self.supported_models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
        self.current_model = self.supported_models[0]
        
        # Capabilities
        self.capabilities = HandlerCapabilities(
            streaming=True,
            context_window=200000,
            file_upload=True,
            models=self.supported_models,
            session_persistence=True,
            concurrent_sessions=True,
            interactive_mode=True,
            batch_processing=True,
            custom_tools=True,
            mcp_servers=True
        )
    
    async def initialize(self) -> None:
        """
        Initialize the MCP handler and establish connection.
        
        Raises:
            ClaudeProcessError: If initialization fails
        """
        try:
            self.logger.info("Initializing MCP handler...")
            
            if not MCP_AVAILABLE:
                raise ClaudeProcessError("MCP SDK not available. Install with: pip install 'mcp[cli]'")
            
            # Initialize MCP connection
            await self._connect_to_mcp_server()
            
            self.is_connected = True
            self.logger.info("MCP handler initialized successfully")
            
        except Exception as e:
            raise ClaudeProcessError(f"Failed to initialize MCP handler: {str(e)}")
    
    async def _connect_to_mcp_server(self) -> None:
        """
        Establish connection to MCP server.
        """
        self.logger.info(f"Connecting to MCP server at {self.server_uri}")
        
        try:
            # Parse server URI to get command and args
            # For now, assume it's a command like "claude"
            server_command = self.config.claude_path if hasattr(self.config, 'claude_path') else "claude"
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_command,
                args=[],
                env=None
            )
            
            # Create MCP client session
            async with stdio_client(server_params) as (session, client):
                self.mcp_session = session
                self.mcp_client = client
                
                # Initialize the session
                if self.mcp_session:
                    await self.mcp_session.initialize()
                
                # Keep the session open by not exiting the context
                # This is a simplified approach - in production, you'd manage this differently
            
            self.logger.info("MCP connection established successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server: {e}")
            raise ClaudeProcessError(f"MCP connection failed: {str(e)}")
    
    async def start_session(
        self,
        project_path: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Start a new Claude session via MCP.
        
        Args:
            project_path: Path to the project directory
            session_id: Optional session ID to resume
            **kwargs: Additional MCP-specific arguments
        
        Returns:
            Session identifier
        
        Raises:
            SessionError: If session creation fails
        """
        if not self.is_connected:
            await self.initialize()
        
        try:
            # Generate or use provided session ID
            new_session_id = session_id or f"mcp_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # For MCP, sessions are managed by the client
            # The actual session is already created during connection
            
            # Create session info
            self.current_session = SessionInfo(
                session_id=new_session_id,
                handler_type=HandlerType.MCP,
                status=SessionStatus.ACTIVE,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=0,
                context_size=0,
                project_path=project_path,
                model=self.current_model,
                metadata={
                    'mcp_server': self.server_uri,
                    'protocol_version': self.protocol_version
                }
            )
            
            self.session_id = new_session_id
            self.message_count = 0
            self.context_size = 0
            
            self.logger.info(f"Started MCP session: {new_session_id}")
            return new_session_id
            
        except Exception as e:
            raise SessionError(f"Failed to start MCP session: {str(e)}")
    
    async def send_message(self, message: str, **kwargs) -> str:
        """
        Send a message to Claude via MCP and get response.
        
        Args:
            message: The message to send
            **kwargs: Additional MCP-specific arguments
        
        Returns:
            Claude's response
        
        Raises:
            ClaudeProcessError: If message sending fails
        """
        if not self.current_session:
            raise ClaudeProcessError("No active session")
        
        try:
            # Send message via MCP
            if not self.mcp_session:
                raise ClaudeProcessError("MCP session not initialized")
            
            # Create a prompt request
            prompt_response = await self.mcp_session.list_prompts()
            
            # For now, use a simple text completion approach
            # In a real implementation, this would use the appropriate MCP method
            response = f"MCP Response to: {message[:50]}..."
            
            # If MCP has tools available, we could call them
            tools_response = await self.mcp_session.list_tools()
            if tools_response.tools:
                self.logger.info(f"Available MCP tools: {[tool.name for tool in tools_response.tools]}")
            
            # Update session state
            self.message_count += 1
            self.context_size += len(message) + len(response)
            self.current_session.message_count = self.message_count
            self.current_session.context_size = self.context_size
            self.current_session.last_activity = datetime.now()
            
            return response
            
        except Exception as e:
            raise ClaudeProcessError(f"Failed to send MCP message: {str(e)}")
    
    async def stream_message(
        self,
        message: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Send a message and stream the response via MCP.
        
        Args:
            message: The message to send
            **kwargs: Additional MCP-specific arguments
        
        Yields:
            Response chunks as they arrive
        
        Raises:
            ClaudeProcessError: If streaming fails
        """
        if not self.current_session:
            raise ClaudeProcessError("No active session")
        
        try:
            # Send streaming message via MCP
            if not self.mcp_session:
                raise ClaudeProcessError("MCP session not initialized")
            
            # For streaming, we would need to use the appropriate MCP streaming method
            # Since MCP client interface may not directly support streaming in the same way,
            # we'll implement a basic version
            response_parts = [
                "MCP streaming: ",
                "Processing request... ",
                "Response complete."
            ]
            
            for part in response_parts:
                await asyncio.sleep(0.05)
                yield part
            
            # Update session state
            self.message_count += 1
            full_response = "".join(response_parts)
            self.context_size += len(message) + len(full_response)
            self.current_session.message_count = self.message_count
            self.current_session.context_size = self.context_size
            self.current_session.last_activity = datetime.now()
            
        except Exception as e:
            raise ClaudeProcessError(f"Failed to stream MCP message: {str(e)}")
    
    async def end_session(self) -> None:
        """End the current session and cleanup resources."""
        if self.current_session:
            try:
                # Close MCP session properly
                if self.mcp_session:
                    try:
                        # MCP sessions are managed by the context manager
                        # Just clear our reference
                        pass
                    except Exception as e:
                        self.logger.error(f"Error during session cleanup: {e}")
                
                self.current_session.status = SessionStatus.INACTIVE
                self.logger.info(f"Ended MCP session: {self.session_id}")
                
            except Exception as e:
                self.logger.error(f"Error ending MCP session: {e}")
            finally:
                self.current_session = None
                self.session_id = None
                self.message_count = 0
                self.context_size = 0
    
    async def get_session_info(self) -> SessionInfo:
        """
        Get information about the current session.
        
        Returns:
            SessionInfo object containing session details
        """
        if not self.current_session:
            raise SessionError("No active session")
        
        # Update last activity
        self.current_session.last_activity = datetime.now()
        return self.current_session
    
    async def is_healthy(self) -> bool:
        """
        Check if the MCP handler is healthy and operational.
        
        Returns:
            True if handler is healthy, False otherwise
        """
        try:
            # Check MCP connection
            if not self.is_connected or not self.mcp_client:
                return False
            
            # Check MCP session health
            if self.mcp_session:
                try:
                    # Try to list resources as a health check
                    await self.mcp_session.list_resources()
                    return True
                except Exception:
                    return False
            
            return True
            
        except Exception:
            return False
    
    async def get_context_info(self) -> Dict[str, Any]:
        """
        Get information about the current context.
        
        Returns:
            Dictionary containing context information
        """
        return {
            'total_tokens': self.context_size,
            'max_tokens': self.capabilities.context_window,
            'message_count': self.message_count,
            'session_id': self.session_id,
            'model': self.current_model,
            'mcp_server': self.server_uri
        }
    
    async def clear_context(self) -> None:
        """Clear the current context while maintaining session."""
        if self.current_session:
            # MCP doesn't have a direct context clear method
            # This is handled at the application level
            
            self.context_size = 0
            self.current_session.context_size = 0
            self.logger.info("Cleared MCP session context")
    
    async def add_context_file(self, file_path: str, content: str) -> None:
        """
        Add a file to the session context via MCP.
        
        Args:
            file_path: Path of the file
            content: Content of the file
        """
        if not self.current_session:
            raise SessionError("No active session")
        
        try:
            # Add file as a resource via MCP
            if self.mcp_session:
                # MCP handles resources differently - they are exposed by servers
                # For client-side, we track the context ourselves
                self.logger.info(f"Added file to context tracking: {file_path}")
            
            # Update context size
            self.context_size += len(content)
            self.current_session.context_size = self.context_size
            
            self.logger.info(f"Added file to MCP context: {file_path}")
            
        except Exception as e:
            raise ClaudeProcessError(f"Failed to add file to MCP context: {str(e)}")
    
    async def execute_command(
        self,
        command: str,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a command via MCP and return structured result.
        
        Args:
            command: Command to execute
            timeout: Optional timeout in seconds
        
        Returns:
            Dictionary containing execution result
        """
        if not self.current_session:
            raise SessionError("No active session")
        
        try:
            # Execute command via MCP tools if available
            if self.mcp_session:
                tools = await self.mcp_session.list_tools()
                
                # Look for a command execution tool
                exec_tool = next((t for t in tools.tools if 'exec' in t.name.lower() or 'command' in t.name.lower()), None)
                
                if exec_tool:
                    # Call the tool
                    tool_result = await self.mcp_session.call_tool(
                        name=exec_tool.name,
                        arguments={"command": command}
                    )
                    
                    # Extract output from result
                    output = ""
                    if hasattr(tool_result, 'content'):
                        if isinstance(tool_result.content, list):
                            output = "".join(str(item) for item in tool_result.content)
                        else:
                            output = str(tool_result.content)
                    else:
                        output = str(tool_result)
                    
                    return {
                        'success': True,
                        'output': output,
                        'error': None,
                        'metadata': {
                            'tool_used': exec_tool.name,
                            'session_id': self.session_id
                        }
                    }
                else:
                    # No command execution tool available
                    return {
                        'success': False,
                        'output': None,
                        'error': "No command execution tool available in MCP server",
                        'metadata': {}
                    }
            
            # Placeholder result
            result = {
                'success': True,
                'output': f"MCP executed: {command}",
                'error': None,
                'metadata': {
                    'execution_time': 0.1,
                    'model': self.current_model,
                    'session_id': self.session_id
                }
            }
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'output': None,
                'error': str(e),
                'metadata': {}
            }
    
    async def get_capabilities(self) -> HandlerCapabilities:
        """
        Get MCP handler capabilities.
        
        Returns:
            HandlerCapabilities object describing MCP capabilities
        """
        return self.capabilities
    
    async def set_model(self, model: str) -> None:
        """
        Change the model being used.
        
        Args:
            model: Model identifier
        
        Raises:
            ValueError: If model is not supported
        """
        if model not in self.supported_models:
            raise ValueError(f"Model {model} not supported. Available: {self.supported_models}")
        
        # MCP doesn't directly control models - this is handled by the server
        # We just track it locally
        
        self.current_model = model
        if self.current_session:
            self.current_session.model = model
        
        self.logger.info(f"Changed MCP model to: {model}")
    
    async def set_temperature(self, temperature: float) -> None:
        """
        Set the temperature parameter.
        
        Args:
            temperature: Temperature value (0.0 to 1.0)
        """
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")
        
        # MCP doesn't directly control temperature - this is server-specific
        # We just track it locally
        
        self.logger.info(f"Set MCP temperature to: {temperature}")
    
    async def cleanup(self) -> None:
        """
        Cleanup MCP handler resources.
        """
        try:
            await self.end_session()
            
            if self.mcp_client:
                # Close MCP connection
                if self.mcp_session:
                    # MCP sessions are managed by the context manager
                    pass
                self.mcp_client = None
                self.mcp_session = None
            
            self.is_connected = False
            self.logger.info("MCP handler cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during MCP cleanup: {e}")


# Register MCP handler with factory when module is imported
try:
    from .handler_interface import HandlerFactory
    HandlerFactory.register_handler(HandlerType.MCP, MCPClaudeHandler)
except ImportError:
    pass  # Factory not available