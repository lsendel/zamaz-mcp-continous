"""
Tests for MCP evolution design and handler architecture.

This module tests the abstract interface, handler factory, and
migration capabilities for the MCP evolution.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from claude_remote_client.claude_client.handler_interface import (
    ClaudeHandlerInterface,
    HandlerType,
    HandlerFactory,
    HandlerCapabilities,
    SessionInfo
)
from claude_remote_client.claude_client.handler_factory import (
    ClaudeHandlerFactory,
    create_claude_handler,
    get_handler_recommendations
)
from claude_remote_client.config import Config, ClaudeConfig
from claude_remote_client.models import SessionStatus
from claude_remote_client.exceptions import ConfigurationError, ClaudeProcessError


class MockHandler(ClaudeHandlerInterface):
    """Mock handler for testing."""
    
    def __init__(self, config):
        self.config = config
        self.initialized = False
        self.session_active = False
        self.session_id = None
        
    async def initialize(self) -> None:
        self.initialized = True
        
    async def start_session(self, project_path: str, session_id: str = None, **kwargs) -> str:
        self.session_id = session_id or "mock_session_123"
        self.session_active = True
        return self.session_id
        
    async def send_message(self, message: str, **kwargs) -> str:
        if not self.session_active:
            raise ClaudeProcessError("No active session")
        return f"Mock response to: {message}"
        
    async def stream_message(self, message: str, **kwargs):
        if not self.session_active:
            raise ClaudeProcessError("No active session")
        for chunk in ["Mock ", "streaming ", "response"]:
            yield chunk
            
    async def end_session(self) -> None:
        self.session_active = False
        self.session_id = None
        
    async def get_session_info(self) -> SessionInfo:
        if not self.session_active:
            raise ClaudeProcessError("No active session")
        return SessionInfo(
            session_id=self.session_id,
            handler_type=HandlerType.SUBPROCESS,
            status=SessionStatus.ACTIVE,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=1,
            context_size=100
        )
        
    async def is_healthy(self) -> bool:
        return self.initialized
        
    async def get_context_info(self) -> dict:
        return {"total_tokens": 100, "max_tokens": 200000}
        
    async def clear_context(self) -> None:
        pass
        
    async def add_context_file(self, file_path: str, content: str) -> None:
        pass
        
    async def execute_command(self, command: str, timeout: float = None) -> dict:
        return {"success": True, "output": f"Executed: {command}"}
        
    async def get_capabilities(self) -> HandlerCapabilities:
        return HandlerCapabilities(
            streaming=True,
            context_window=200000,
            file_upload=True,
            models=["claude-3-5-sonnet-20241022"]
        )


class TestHandlerInterface:
    """Test the abstract handler interface."""
    
    def test_handler_type_enum(self):
        """Test handler type enumeration."""
        assert HandlerType.SUBPROCESS.value == "subprocess"
        assert HandlerType.MCP.value == "mcp"
        assert HandlerType.HYBRID.value == "hybrid"
    
    def test_handler_capabilities_dataclass(self):
        """Test handler capabilities dataclass."""
        caps = HandlerCapabilities()
        assert caps.streaming is True
        assert caps.context_window == 200000
        assert caps.models == ["claude-3-5-sonnet-20241022"]
    
    def test_session_info_dataclass(self):
        """Test session info dataclass."""
        info = SessionInfo(
            session_id="test_123",
            handler_type=HandlerType.SUBPROCESS,
            status=SessionStatus.ACTIVE,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=5,
            context_size=1000
        )
        assert info.session_id == "test_123"
        assert info.handler_type == HandlerType.SUBPROCESS
        assert info.metadata == {}


class TestHandlerFactory:
    """Test the handler factory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear factory registry
        HandlerFactory._handlers.clear()
        
    def test_register_handler(self):
        """Test handler registration."""
        HandlerFactory.register_handler(HandlerType.SUBPROCESS, MockHandler)
        
        available = HandlerFactory.get_available_handlers()
        assert HandlerType.SUBPROCESS in available
    
    def test_register_invalid_handler(self):
        """Test registering invalid handler raises error."""
        class InvalidHandler:
            pass
            
        with pytest.raises(TypeError):
            HandlerFactory.register_handler(HandlerType.SUBPROCESS, InvalidHandler)
    
    def test_create_handler(self):
        """Test handler creation."""
        HandlerFactory.register_handler(HandlerType.SUBPROCESS, MockHandler)
        
        config = Config()
        handler = HandlerFactory.create_handler(HandlerType.SUBPROCESS, config)
        
        assert isinstance(handler, MockHandler)
        assert handler.config == config
    
    def test_create_unregistered_handler(self):
        """Test creating unregistered handler raises error."""
        config = Config()
        
        with pytest.raises(ValueError):
            HandlerFactory.create_handler(HandlerType.MCP, config)


class TestClaudeHandlerFactory:
    """Test the Claude handler factory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = ClaudeHandlerFactory()
        # Clear factory registry
        HandlerFactory._handlers.clear()
        # Register mock handler
        HandlerFactory.register_handler(HandlerType.SUBPROCESS, MockHandler)
    
    def test_create_handler_subprocess(self):
        """Test creating subprocess handler."""
        config = Config(claude=ClaudeConfig(handler_type="subprocess"))
        
        handler = self.factory.create_handler(config)
        assert isinstance(handler, MockHandler)
    
    def test_create_handler_invalid_type(self):
        """Test creating handler with invalid type."""
        config = Config(claude=ClaudeConfig(handler_type="invalid"))
        
        with pytest.raises(ConfigurationError):
            self.factory.create_handler(config)
    
    def test_create_handler_unavailable_type(self):
        """Test creating unavailable handler type."""
        config = Config(claude=ClaudeConfig(handler_type="mcp"))
        
        with pytest.raises(ConfigurationError):
            self.factory.create_handler(config)
    
    def test_get_available_handler_types(self):
        """Test getting available handler types."""
        available = self.factory.get_available_handler_types()
        
        assert "subprocess" in available
        assert available["subprocess"]["name"] == "subprocess"
        assert "description" in available["subprocess"]
    
    def test_validate_handler_config(self):
        """Test handler configuration validation."""
        config = Config(claude=ClaudeConfig(handler_type="subprocess"))
        
        with patch.object(config, 'validate_claude_cli', return_value=True):
            result = self.factory.validate_handler_config(config)
            
            assert result["valid"] is True
            assert result["handler_type"] == "subprocess"
            assert result["requirements_met"]["claude_cli"] is True
    
    def test_recommend_handler_type(self):
        """Test handler type recommendation."""
        config = Config(claude=ClaudeConfig())
        
        with patch.object(config, 'validate_claude_cli', return_value=True):
            recommendation = self.factory.recommend_handler_type(config)
            
            assert "recommended" in recommendation
            assert "reason" in recommendation
            assert "validation_results" in recommendation


class TestMockHandler:
    """Test the mock handler implementation."""
    
    @pytest.fixture
    def handler(self):
        """Create a mock handler for testing."""
        config = Config()
        handler = MockHandler(config)
        return handler
    
    @pytest.mark.asyncio
    async def test_handler_lifecycle(self, handler):
        """Test complete handler lifecycle."""
        # Initialize handler
        await handler.initialize()
        # Test initialization
        assert handler.initialized is True
        assert await handler.is_healthy() is True
        
        # Test session management
        session_id = await handler.start_session("/test/project")
        assert session_id == "mock_session_123"
        assert handler.session_active is True
        
        # Test messaging
        response = await handler.send_message("Hello")
        assert response == "Mock response to: Hello"
        
        # Test streaming
        chunks = []
        async for chunk in handler.stream_message("Stream test"):
            chunks.append(chunk)
        assert chunks == ["Mock ", "streaming ", "response"]
        
        # Test session info
        info = await handler.get_session_info()
        assert info.session_id == session_id
        assert info.handler_type == HandlerType.SUBPROCESS
        
        # Test capabilities
        caps = await handler.get_capabilities()
        assert caps.streaming is True
        assert caps.context_window == 200000
        
        # Test command execution
        result = await handler.execute_command("test command")
        assert result["success"] is True
        assert "Executed: test command" in result["output"]
        
        # Test session end
        await handler.end_session()
        assert handler.session_active is False
    
    @pytest.mark.asyncio
    async def test_handler_error_conditions(self, handler):
        """Test handler error conditions."""
        # Test operations without active session
        with pytest.raises(ClaudeProcessError):
            await handler.send_message("test")
        
        with pytest.raises(ClaudeProcessError):
            async for chunk in handler.stream_message("test"):
                pass
        
        with pytest.raises(ClaudeProcessError):
            await handler.get_session_info()


class TestIntegrationFunctions:
    """Test integration functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        HandlerFactory._handlers.clear()
        HandlerFactory.register_handler(HandlerType.SUBPROCESS, MockHandler)
    
    def test_create_claude_handler(self):
        """Test create_claude_handler convenience function."""
        config = Config(claude=ClaudeConfig(handler_type="subprocess"))
        
        handler = create_claude_handler(config)
        assert isinstance(handler, MockHandler)
    
    def test_get_handler_recommendations(self):
        """Test get_handler_recommendations convenience function."""
        config = Config(claude=ClaudeConfig())
        
        with patch.object(config, 'validate_claude_cli', return_value=True):
            recommendations = get_handler_recommendations(config)
            
            assert "recommended" in recommendations
            assert "validation_results" in recommendations


class TestConfigurationIntegration:
    """Test configuration integration with handlers."""
    
    def test_subprocess_config(self):
        """Test subprocess handler configuration."""
        config = Config(claude=ClaudeConfig(
            handler_type="subprocess",
            cli_path="claude",
            timeout=300
        ))
        
        assert config.claude.handler_type == "subprocess"
        assert config.claude.cli_path == "claude"
        assert config.claude.timeout == 300
    
    def test_mcp_config(self):
        """Test MCP handler configuration."""
        config = Config(claude=ClaudeConfig(
            handler_type="mcp",
            mcp_server_uri="mcp://localhost:8000",
            mcp_timeout=30
        ))
        
        assert config.claude.handler_type == "mcp"
        assert config.claude.mcp_server_uri == "mcp://localhost:8000"
        assert config.claude.mcp_timeout == 30
    
    def test_hybrid_config(self):
        """Test hybrid handler configuration."""
        config = Config(claude=ClaudeConfig(
            handler_type="hybrid",
            prefer_mcp=True,
            fallback_to_subprocess=True
        ))
        
        assert config.claude.handler_type == "hybrid"
        assert config.claude.prefer_mcp is True
        assert config.claude.fallback_to_subprocess is True


if __name__ == "__main__":
    pytest.main([__file__])