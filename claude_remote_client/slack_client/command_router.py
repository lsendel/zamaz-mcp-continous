"""
Command router for parsing and routing Slack commands.

This module handles parsing @@commands from Slack messages and routing them
to appropriate handlers.
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from ..models import SlackMessage
from ..exceptions import ClaudeRemoteClientError
from ..utils import setup_logging, format_error_for_slack, format_info_for_slack


class CommandType(Enum):
    """Types of supported commands."""
    PROJECTS = "projects"
    SWITCH = "switch"
    NEW = "new"
    SESSIONS = "sessions"
    QUIT = "quit"
    QUEUE_ADD = "queue_add"
    QUEUE = "queue"
    QUEUE_STATUS = "queue_status"
    QUEUE_CLEAR = "queue_clear"
    CRON = "cron"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    should_forward_to_claude: bool = False


@dataclass
class ParsedCommand:
    """Parsed command with arguments."""
    command_type: CommandType
    command_name: str
    arguments: List[str]
    raw_text: str


class CommandRouter:
    """
    Router for parsing and executing Slack commands.
    
    Handles @@commands and distinguishes them from regular messages
    that should be forwarded to Claude.
    """
    
    def __init__(self):
        """Initialize the command router."""
        self.logger = setup_logging()
        self.command_handlers: Dict[CommandType, Callable] = {}
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Set up default command handlers."""
        self.command_handlers = {
            CommandType.HELP: self._handle_help,
            CommandType.PROJECTS: self._handle_projects_placeholder,
            CommandType.SWITCH: self._handle_switch_placeholder,
            CommandType.NEW: self._handle_new_placeholder,
            CommandType.SESSIONS: self._handle_sessions_placeholder,
            CommandType.QUIT: self._handle_quit_placeholder,
            CommandType.QUEUE_ADD: self._handle_queue_add_placeholder,
            CommandType.QUEUE: self._handle_queue_placeholder,
            CommandType.QUEUE_STATUS: self._handle_queue_status_placeholder,
            CommandType.QUEUE_CLEAR: self._handle_queue_clear_placeholder,
            CommandType.CRON: self._handle_cron_placeholder,
        }
    
    def is_command(self, message: SlackMessage) -> bool:
        """
        Check if a message is a command.
        
        Args:
            message: Slack message to check
        
        Returns:
            bool: True if message is a command, False otherwise
        """
        return message.is_command
    
    def parse_command(self, message: SlackMessage) -> ParsedCommand:
        """
        Parse a command message into structured format.
        
        Args:
            message: Slack message containing command
        
        Returns:
            ParsedCommand: Parsed command structure
        """
        if not self.is_command(message):
            return ParsedCommand(
                command_type=CommandType.UNKNOWN,
                command_name="",
                arguments=[],
                raw_text=message.text
            )
        
        # Extract command and arguments
        command_name = message.get_command() or ""
        arguments = message.get_command_args()
        
        # Map command name to type
        command_type = self._get_command_type(command_name)
        
        return ParsedCommand(
            command_type=command_type,
            command_name=command_name,
            arguments=arguments,
            raw_text=message.text
        )
    
    def _get_command_type(self, command_name: str) -> CommandType:
        """
        Map command name to CommandType enum.
        
        Args:
            command_name: Name of the command
        
        Returns:
            CommandType: Corresponding command type
        """
        command_mapping = {
            "projects": CommandType.PROJECTS,
            "switch": CommandType.SWITCH,
            "new": CommandType.NEW,
            "sessions": CommandType.SESSIONS,
            "quit": CommandType.QUIT,
            "q": CommandType.QUIT,  # Alias for quit
            "queue_add": CommandType.QUEUE_ADD,
            "queue": CommandType.QUEUE,
            "queue_status": CommandType.QUEUE_STATUS,
            "queue_clear": CommandType.QUEUE_CLEAR,
            "cron": CommandType.CRON,
            "help": CommandType.HELP,
        }
        
        return command_mapping.get(command_name.lower(), CommandType.UNKNOWN)
    
    async def route_message(self, message: SlackMessage) -> CommandResult:
        """
        Route a message to appropriate handler.
        
        Args:
            message: Slack message to route
        
        Returns:
            CommandResult: Result of command execution or indication to forward to Claude
        """
        try:
            if not self.is_command(message):
                # Regular message - should be forwarded to Claude
                return CommandResult(
                    success=True,
                    message="Forward to Claude",
                    should_forward_to_claude=True
                )
            
            # Parse the command
            parsed_command = self.parse_command(message)
            
            # Handle unknown commands
            if parsed_command.command_type == CommandType.UNKNOWN:
                return CommandResult(
                    success=False,
                    message=f"Unknown command: `{parsed_command.command_name}`. Type `@@help` for available commands."
                )
            
            # Execute the command
            handler = self.command_handlers.get(parsed_command.command_type)
            if handler:
                return await handler(parsed_command)
            else:
                return CommandResult(
                    success=False,
                    message=f"No handler found for command: `{parsed_command.command_name}`"
                )
        
        except Exception as e:
            self.logger.error(f"Error routing message: {e}")
            return CommandResult(
                success=False,
                message=format_error_for_slack(e)
            )
    
    def register_handler(self, command_type: CommandType, handler: Callable) -> None:
        """
        Register a custom command handler.
        
        Args:
            command_type: Type of command to handle
            handler: Async function that takes ParsedCommand and returns CommandResult
        """
        self.command_handlers[command_type] = handler
    
    def unregister_handler(self, command_type: CommandType) -> None:
        """
        Unregister a command handler.
        
        Args:
            command_type: Type of command to unregister
        """
        if command_type in self.command_handlers:
            del self.command_handlers[command_type]
    
    # Default command handlers (placeholders for now)
    
    async def _handle_help(self, command: ParsedCommand) -> CommandResult:
        """Handle help command."""
        help_text = """
🤖 **Claude Remote Client Commands**

**Session Management:**
• `@@projects` - List available projects
• `@@switch <project>` - Switch to a project
• `@@new <project>` - Create new session for project
• `@@sessions` - List active sessions
• `@@quit` or `@@q` - Quit current session

**Task Queue:**
• `@@queue_add <queue> <description>` - Add task to queue
• `@@queue <queue>` - Process queue tasks
• `@@queue_status [queue]` - Show queue status
• `@@queue_clear <queue>` - Clear queue

**Automation:**
• `@@cron <pattern> <tasks>` - Schedule recurring tasks

**General:**
• `@@help` - Show this help message

**Examples:**
```
@@projects
@@switch my-project
@@queue_add feature-dev "Implement user auth"
@@cron "0 */2 * * *" clean_code,run_tests
```

💡 Any message not starting with `@@` will be sent directly to Claude!
        """
        
        return CommandResult(
            success=True,
            message=help_text.strip()
        )
    
    async def _handle_projects_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for projects command."""
        return CommandResult(
            success=False,
            message="📋 Projects command not yet implemented. This will show available projects."
        )
    
    async def _handle_switch_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for switch command."""
        if not command.arguments:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@switch <project_name>`"
            )
        
        project_name = command.arguments[0]
        return CommandResult(
            success=False,
            message=f"🔄 Switch to project '{project_name}' not yet implemented."
        )
    
    async def _handle_new_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for new session command."""
        if not command.arguments:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@new <project_name>`"
            )
        
        project_name = command.arguments[0]
        return CommandResult(
            success=False,
            message=f"➕ New session for project '{project_name}' not yet implemented."
        )
    
    async def _handle_sessions_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for sessions command."""
        return CommandResult(
            success=False,
            message="📊 Sessions listing not yet implemented. This will show active sessions."
        )
    
    async def _handle_quit_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for quit command."""
        return CommandResult(
            success=False,
            message="👋 Quit session not yet implemented. This will terminate the current Claude session."
        )
    
    async def _handle_queue_add_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for queue add command."""
        if len(command.arguments) < 2:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@queue_add <queue_name> <task_description>`"
            )
        
        queue_name = command.arguments[0]
        task_description = " ".join(command.arguments[1:])
        
        return CommandResult(
            success=False,
            message=f"📝 Add task '{task_description}' to queue '{queue_name}' not yet implemented."
        )
    
    async def _handle_queue_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for queue processing command."""
        if not command.arguments:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@queue <queue_name>`"
            )
        
        queue_name = command.arguments[0]
        return CommandResult(
            success=False,
            message=f"⚡ Process queue '{queue_name}' not yet implemented."
        )
    
    async def _handle_queue_status_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for queue status command."""
        queue_name = command.arguments[0] if command.arguments else "all"
        return CommandResult(
            success=False,
            message=f"📈 Queue status for '{queue_name}' not yet implemented."
        )
    
    async def _handle_queue_clear_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for queue clear command."""
        if not command.arguments:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@queue_clear <queue_name>`"
            )
        
        queue_name = command.arguments[0]
        return CommandResult(
            success=False,
            message=f"🗑️ Clear queue '{queue_name}' not yet implemented."
        )
    
    async def _handle_cron_placeholder(self, command: ParsedCommand) -> CommandResult:
        """Placeholder for cron command."""
        if len(command.arguments) < 2:
            return CommandResult(
                success=False,
                message="❌ Usage: `@@cron \"<cron_pattern>\" <task1,task2,...>`\\n"
                       "Example: `@@cron \"0 */2 * * *\" clean_code,run_tests`"
            )
        
        cron_pattern = command.arguments[0]
        tasks = " ".join(command.arguments[1:])  # Join remaining arguments
        
        return CommandResult(
            success=False,
            message=f"⏰ Cron schedule '{cron_pattern}' for tasks '{tasks}' not yet implemented."
        )
    
    def get_available_commands(self) -> List[str]:
        """
        Get list of available command names.
        
        Returns:
            List[str]: List of command names
        """
        commands = []
        for command_type in CommandType:
            if command_type != CommandType.UNKNOWN:
                commands.append(command_type.value)
        
        # Add aliases
        commands.append("q")  # Alias for quit
        
        return sorted(commands)
    
    def validate_command_syntax(self, command: ParsedCommand) -> Optional[str]:
        """
        Validate command syntax and return error message if invalid.
        
        Args:
            command: Parsed command to validate
        
        Returns:
            Optional[str]: Error message if invalid, None if valid
        """
        if command.command_type == CommandType.UNKNOWN:
            return f"Unknown command: {command.command_name}"
        
        # Validate argument counts for specific commands
        validation_rules = {
            CommandType.SWITCH: (1, "Usage: @@switch <project_name>"),
            CommandType.NEW: (1, "Usage: @@new <project_name>"),
            CommandType.QUEUE_ADD: (2, "Usage: @@queue_add <queue_name> <task_description>"),
            CommandType.QUEUE: (1, "Usage: @@queue <queue_name>"),
            CommandType.QUEUE_CLEAR: (1, "Usage: @@queue_clear <queue_name>"),
            CommandType.CRON: (2, "Usage: @@cron \"<cron_pattern>\" <task1,task2,...>"),
        }
        
        if command.command_type in validation_rules:
            min_args, usage_msg = validation_rules[command.command_type]
            if len(command.arguments) < min_args:
                return usage_msg
        
        return None