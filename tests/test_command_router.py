"""
Unit tests for command router.
"""

import pytest
from claude_remote_client.slack_client.command_router import (
    CommandRouter, CommandType, CommandResult, ParsedCommand
)
from claude_remote_client.models import SlackMessage


class TestCommandRouter:
    """Test cases for CommandRouter."""
    
    def test_router_initialization(self):
        """Test router initialization."""
        router = CommandRouter()
        
        assert router.command_handlers is not None
        assert len(router.command_handlers) > 0
        assert CommandType.HELP in router.command_handlers
    
    def test_is_command_detection(self):
        """Test command detection."""
        router = CommandRouter()
        
        # Command message
        command_msg = SlackMessage(text="@@projects")
        assert router.is_command(command_msg) is True
        
        # Regular message
        regular_msg = SlackMessage(text="Hello Claude!")
        assert router.is_command(regular_msg) is False
        
        # Message with @@ in middle (not a command)
        not_command_msg = SlackMessage(text="This has @@something in middle")
        assert router.is_command(not_command_msg) is False
    
    def test_parse_command_valid(self):
        """Test parsing valid commands."""
        router = CommandRouter()
        
        # Simple command
        message = SlackMessage(text="@@projects")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.PROJECTS
        assert parsed.command_name == "projects"
        assert parsed.arguments == []
        assert parsed.raw_text == "@@projects"
        
        # Command with arguments
        message = SlackMessage(text="@@switch my-project")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.SWITCH
        assert parsed.command_name == "switch"
        assert parsed.arguments == ["my-project"]
        
        # Command with multiple arguments
        message = SlackMessage(text="@@queue_add feature-queue 'Implement user auth'")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.QUEUE_ADD
        assert parsed.command_name == "queue_add"
        assert parsed.arguments == ["feature-queue", "'Implement", "user", "auth'"]
    
    def test_parse_command_unknown(self):
        """Test parsing unknown commands."""
        router = CommandRouter()
        
        message = SlackMessage(text="@@unknown_command")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.UNKNOWN
        assert parsed.command_name == "unknown_command"
        assert parsed.arguments == []
    
    def test_parse_command_aliases(self):
        """Test parsing command aliases."""
        router = CommandRouter()
        
        # Test 'q' alias for quit
        message = SlackMessage(text="@@q")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.QUIT
        assert parsed.command_name == "q"
    
    def test_parse_non_command(self):
        """Test parsing non-command messages."""
        router = CommandRouter()
        
        message = SlackMessage(text="Hello Claude!")
        parsed = router.parse_command(message)
        
        assert parsed.command_type == CommandType.UNKNOWN
        assert parsed.command_name == ""
        assert parsed.arguments == []
        assert parsed.raw_text == "Hello Claude!"
    
    @pytest.mark.asyncio
    async def test_route_regular_message(self):
        """Test routing regular messages."""
        router = CommandRouter()
        
        message = SlackMessage(text="Hello Claude!")
        result = await router.route_message(message)
        
        assert result.success is True
        assert result.should_forward_to_claude is True
        assert result.message == "Forward to Claude"
    
    @pytest.mark.asyncio
    async def test_route_help_command(self):
        """Test routing help command."""
        router = CommandRouter()
        
        message = SlackMessage(text="@@help")
        result = await router.route_message(message)
        
        assert result.success is True
        assert result.should_forward_to_claude is False
        assert "Claude Remote Client Commands" in result.message
    
    @pytest.mark.asyncio
    async def test_route_unknown_command(self):
        """Test routing unknown command."""
        router = CommandRouter()
        
        message = SlackMessage(text="@@unknown")
        result = await router.route_message(message)
        
        assert result.success is False
        assert result.should_forward_to_claude is False
        assert "Unknown command" in result.message
    
    @pytest.mark.asyncio
    async def test_route_placeholder_commands(self):
        """Test routing placeholder commands."""
        router = CommandRouter()
        
        # Test projects command
        message = SlackMessage(text="@@projects")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "not yet implemented" in result.message
        
        # Test switch command with argument
        message = SlackMessage(text="@@switch my-project")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "my-project" in result.message
        assert "not yet implemented" in result.message
    
    @pytest.mark.asyncio
    async def test_route_switch_command_no_args(self):
        """Test switch command without arguments."""
        router = CommandRouter()
        
        message = SlackMessage(text="@@switch")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "Usage: `@@switch <project_name>`" in result.message
    
    @pytest.mark.asyncio
    async def test_route_queue_add_command(self):
        """Test queue_add command."""
        router = CommandRouter()
        
        # Valid queue_add command
        message = SlackMessage(text="@@queue_add feature-queue 'Implement user auth'")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "feature-queue" in result.message
        assert "not yet implemented" in result.message
        
        # Invalid queue_add command (missing arguments)
        message = SlackMessage(text="@@queue_add feature-queue")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "Usage:" in result.message
    
    @pytest.mark.asyncio
    async def test_route_cron_command(self):
        """Test cron command."""
        router = CommandRouter()
        
        # Valid cron command (note: simple space-based parsing doesn't handle quotes perfectly)
        message = SlackMessage(text='@@cron "0 */2 * * *" clean_code,run_tests')
        result = await router.route_message(message)
        
        assert result.success is False
        assert '"0' in result.message  # First part of quoted pattern
        assert "not yet implemented" in result.message
        
        # Invalid cron command (missing arguments)
        message = SlackMessage(text="@@cron")
        result = await router.route_message(message)
        
        assert result.success is False
        assert "Usage:" in result.message
    
    def test_register_custom_handler(self):
        """Test registering custom command handler."""
        router = CommandRouter()
        
        async def custom_handler(command):
            return CommandResult(success=True, message="Custom handler executed")
        
        router.register_handler(CommandType.PROJECTS, custom_handler)
        
        assert router.command_handlers[CommandType.PROJECTS] == custom_handler
    
    def test_unregister_handler(self):
        """Test unregistering command handler."""
        router = CommandRouter()
        
        # Unregister existing handler
        router.unregister_handler(CommandType.HELP)
        
        assert CommandType.HELP not in router.command_handlers
    
    def test_get_available_commands(self):
        """Test getting available commands."""
        router = CommandRouter()
        
        commands = router.get_available_commands()
        
        assert isinstance(commands, list)
        assert len(commands) > 0
        assert "projects" in commands
        assert "switch" in commands
        assert "help" in commands
        assert "q" in commands  # Alias
        assert commands == sorted(commands)  # Should be sorted
    
    def test_validate_command_syntax(self):
        """Test command syntax validation."""
        router = CommandRouter()
        
        # Valid commands
        valid_switch = ParsedCommand(
            command_type=CommandType.SWITCH,
            command_name="switch",
            arguments=["my-project"],
            raw_text="@@switch my-project"
        )
        assert router.validate_command_syntax(valid_switch) is None
        
        # Invalid commands
        invalid_switch = ParsedCommand(
            command_type=CommandType.SWITCH,
            command_name="switch",
            arguments=[],
            raw_text="@@switch"
        )
        error = router.validate_command_syntax(invalid_switch)
        assert error is not None
        assert "Usage:" in error
        
        # Unknown command
        unknown_command = ParsedCommand(
            command_type=CommandType.UNKNOWN,
            command_name="unknown",
            arguments=[],
            raw_text="@@unknown"
        )
        error = router.validate_command_syntax(unknown_command)
        assert error is not None
        assert "Unknown command" in error