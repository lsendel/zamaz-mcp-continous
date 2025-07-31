"""
Message streamer for handling communication between Slack and Claude.

This module provides real-time message streaming, interactive prompt handling,
and slash command processing for Claude CLI integration.
"""

import asyncio
import logging
import re
from typing import Optional, AsyncIterator, Callable, Dict, Any, List
from datetime import datetime

from ..models import SlackMessage, ClaudeSession
from ..exceptions import ClaudeProcessError
from ..utils import setup_logging, format_code_block
from .subprocess_handler import SubprocessClaudeHandler


class MessageStreamer:
    """
    Streamer for handling bidirectional communication between Slack and Claude.
    
    Manages message relay, interactive prompts, slash commands, and real-time
    response streaming from Claude to Slack.
    """
    
    def __init__(self, subprocess_handler: SubprocessClaudeHandler):
        """
        Initialize the message streamer.
        
        Args:
            subprocess_handler: Handler for Claude subprocess communication
        """
        self.subprocess_handler = subprocess_handler
        self.logger = setup_logging()
        
        # Streaming state
        self.is_streaming = False
        self.current_session: Optional[ClaudeSession] = None
        
        # Interactive prompt handling
        self.pending_prompts: Dict[str, str] = {}  # prompt_id -> prompt_text
        self.prompt_responses: Dict[str, str] = {}  # prompt_id -> response
        self.prompt_timeout = 300.0  # 5 minutes for user response
        
        # Slash command patterns
        self.slash_commands = {
            '/help': self._handle_help_command,
            '/exit': self._handle_exit_command,
            '/clear': self._handle_clear_command,
            '/save': self._handle_save_command,
            '/files': self._handle_files_command,
            '/status': self._handle_status_command,
        }
        
        # Response formatting
        self.max_chunk_size = 2000  # Max characters per Slack message
        self.response_buffer = ""
        self.last_response_time = datetime.now()
        
        # Callbacks for Slack communication
        self.slack_message_callback: Optional[Callable] = None
        self.slack_update_callback: Optional[Callable] = None
    
    def set_slack_callbacks(self, message_callback: Callable, update_callback: Callable) -> None:
        """
        Set callbacks for Slack communication.
        
        Args:
            message_callback: Function to send new messages to Slack
            update_callback: Function to update existing messages in Slack
        """
        self.slack_message_callback = message_callback
        self.slack_update_callback = update_callback
    
    async def start_streaming(self, session: ClaudeSession) -> None:
        """
        Start streaming for a Claude session.
        
        Args:
            session: Claude session to stream for
        
        Raises:
            ClaudeProcessError: If streaming cannot be started
        """
        if self.is_streaming:
            raise ClaudeProcessError("Already streaming for another session")
        
        self.current_session = session
        self.is_streaming = True
        
        self.logger.info(f"Started streaming for session: {session.session_id}")
        
        # Set up output handler for subprocess
        self.subprocess_handler.add_output_handler(self._handle_claude_output)
        self.subprocess_handler.add_error_handler(self._handle_claude_error)
    
    async def stop_streaming(self) -> None:
        """Stop streaming and clean up."""
        if not self.is_streaming:
            return
        
        self.is_streaming = False
        
        # Remove output handlers
        self.subprocess_handler.remove_output_handler(self._handle_claude_output)
        self.subprocess_handler.remove_error_handler(self._handle_claude_error)
        
        # Clear state
        self.current_session = None
        self.response_buffer = ""
        self.pending_prompts.clear()
        self.prompt_responses.clear()
        
        self.logger.info("Stopped streaming")
    
    async def send_message_to_claude(self, message: SlackMessage) -> None:
        """
        Send a message from Slack to Claude.
        
        Args:
            message: Slack message to send to Claude
        
        Raises:
            ClaudeProcessError: If message cannot be sent
        """
        if not self.is_streaming or not self.current_session:
            raise ClaudeProcessError("Not currently streaming")
        
        try:
            # Check if it's a slash command
            if message.text.startswith('/'):
                await self._handle_slash_command(message)
                return
            
            # Check if it's a response to a pending prompt
            if self.pending_prompts:
                await self._handle_prompt_response(message)
                return
            
            # Regular message - send to Claude
            await self.subprocess_handler.send_message(message.text)
            
            self.logger.debug(f"Sent message to Claude: {message.text[:100]}...")
        
        except Exception as e:
            raise ClaudeProcessError(f"Failed to send message to Claude: {str(e)}")
    
    async def _handle_claude_output(self, output: str) -> None:
        """
        Handle output from Claude subprocess.
        
        Args:
            output: Output chunk from Claude
        """
        if not self.is_streaming or not self.slack_message_callback:
            return
        
        try:
            # Add to response buffer
            self.response_buffer += output
            self.last_response_time = datetime.now()
            
            # Check for interactive prompts
            if self._detect_interactive_prompt(output):
                await self._handle_interactive_prompt(output)
                return
            
            # Check if we should send accumulated response
            if self._should_send_response():
                await self._send_accumulated_response()
        
        except Exception as e:
            self.logger.error(f"Error handling Claude output: {e}")
    
    async def _handle_claude_error(self, error: str) -> None:
        """
        Handle error output from Claude subprocess.
        
        Args:
            error: Error output from Claude
        """
        if not self.is_streaming or not self.slack_message_callback:
            return
        
        try:
            # Format error for Slack
            error_message = f"⚠️ **Claude Error:**\n```\n{error.strip()}\n```"
            
            # Send error to Slack
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=error_message
            )
        
        except Exception as e:
            self.logger.error(f"Error handling Claude error: {e}")
    
    def _detect_interactive_prompt(self, output: str) -> bool:
        """
        Detect if output contains an interactive prompt.
        
        Args:
            output: Output to check
        
        Returns:
            bool: True if interactive prompt detected
        """
        # Common prompt patterns
        prompt_patterns = [
            r'\[y/n\]',  # Yes/no prompts
            r'\[Y/n\]',  # Yes/no with default
            r'\[y/N\]',  # Yes/no with default
            r'Press Enter to continue',
            r'Enter your choice:',
            r'Please confirm:',
            r'Continue\? \(y/n\)',
            r'Proceed\? \(y/n\)',
        ]
        
        for pattern in prompt_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        
        return False
    
    async def _handle_interactive_prompt(self, output: str) -> None:
        """
        Handle interactive prompts from Claude.
        
        Args:
            output: Output containing the prompt
        """
        if not self.slack_message_callback:
            return
        
        try:
            # Generate prompt ID
            prompt_id = f"prompt_{datetime.now().timestamp()}"
            
            # Store the prompt
            self.pending_prompts[prompt_id] = output.strip()
            
            # Format prompt for Slack
            prompt_message = f"🤔 **Claude is asking for input:**\n```\n{output.strip()}\n```\n\n" \
                           f"Please respond with your choice. (Prompt ID: `{prompt_id}`)"
            
            # Send prompt to Slack
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=prompt_message
            )
            
            # Set timeout for prompt response
            asyncio.create_task(self._timeout_prompt(prompt_id))
        
        except Exception as e:
            self.logger.error(f"Error handling interactive prompt: {e}")
    
    async def _handle_prompt_response(self, message: SlackMessage) -> None:
        """
        Handle response to an interactive prompt.
        
        Args:
            message: Slack message containing the response
        """
        if not self.pending_prompts:
            # No pending prompts, treat as regular message
            await self.subprocess_handler.send_message(message.text)
            return
        
        try:
            # Use the most recent prompt (simple approach)
            prompt_id = list(self.pending_prompts.keys())[-1]
            
            # Send response to Claude
            await self.subprocess_handler.send_message(message.text)
            
            # Clean up prompt
            if prompt_id in self.pending_prompts:
                del self.pending_prompts[prompt_id]
            
            self.logger.debug(f"Handled prompt response: {message.text}")
        
        except Exception as e:
            self.logger.error(f"Error handling prompt response: {e}")
    
    async def _timeout_prompt(self, prompt_id: str) -> None:
        """
        Handle prompt timeout.
        
        Args:
            prompt_id: ID of the prompt that timed out
        """
        await asyncio.sleep(self.prompt_timeout)
        
        if prompt_id in self.pending_prompts:
            # Prompt timed out
            del self.pending_prompts[prompt_id]
            
            if self.slack_message_callback:
                timeout_message = f"⏰ **Prompt timed out** (ID: `{prompt_id}`)\n" \
                                f"Claude may be waiting for input. You can still respond to continue."
                
                await self.slack_message_callback(
                    channel=self.current_session.project_name if self.current_session else "unknown",
                    text=timeout_message
                )
    
    def _should_send_response(self) -> bool:
        """
        Determine if accumulated response should be sent.
        
        Returns:
            bool: True if response should be sent
        """
        # Send if buffer is getting large
        if len(self.response_buffer) > self.max_chunk_size:
            return True
        
        # Send if there's been a pause in output
        time_since_last = (datetime.now() - self.last_response_time).total_seconds()
        if time_since_last > 2.0 and self.response_buffer.strip():
            return True
        
        # Send if buffer ends with what looks like a complete response
        if self.response_buffer.strip().endswith(('>', '$', ':', '.')):
            return True
        
        return False
    
    async def _send_accumulated_response(self) -> None:
        """Send accumulated response to Slack."""
        if not self.response_buffer.strip() or not self.slack_message_callback:
            return
        
        try:
            # Format response
            formatted_response = self._format_response(self.response_buffer)
            
            # Send to Slack
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=formatted_response
            )
            
            # Clear buffer
            self.response_buffer = ""
        
        except Exception as e:
            self.logger.error(f"Error sending accumulated response: {e}")
    
    def _format_response(self, response: str) -> str:
        """
        Format Claude response for Slack display.
        
        Args:
            response: Raw response from Claude
        
        Returns:
            str: Formatted response
        """
        # Remove excessive whitespace
        formatted = response.strip()
        
        # Detect and format code blocks
        if self._contains_code(formatted):
            formatted = self._format_code_in_response(formatted)
        
        # Truncate if too long
        if len(formatted) > self.max_chunk_size:
            formatted = formatted[:self.max_chunk_size - 50] + "\n\n... (response truncated)"
        
        return formatted
    
    def _contains_code(self, text: str) -> bool:
        """
        Check if text contains code that should be formatted.
        
        Args:
            text: Text to check
        
        Returns:
            bool: True if text contains code
        """
        code_indicators = [
            'def ', 'class ', 'import ', 'from ',
            '= ', '== ', '!= ', '-> ',
            'if __name__', 'print(', 'return ',
            '#!/', '<?', '<html', '<div',
            'function ', 'var ', 'const ', 'let ',
            'SELECT ', 'INSERT ', 'UPDATE ', 'DELETE '
        ]
        
        return any(indicator in text for indicator in code_indicators)
    
    def _format_code_in_response(self, text: str) -> str:
        """
        Format code sections in response text.
        
        Args:
            text: Text containing code
        
        Returns:
            str: Text with formatted code blocks
        """
        lines = text.split('\n')
        formatted_lines = []
        in_code_block = False
        code_lines = []
        
        for line in lines:
            # Simple heuristic for code detection
            is_code = (
                line.startswith('    ') or
                line.startswith('\t') or
                any(indicator in line for indicator in ['def ', 'class ', 'import ', '= '])
            )
            
            if is_code and not in_code_block:
                in_code_block = True
                code_lines = [line]
            elif is_code and in_code_block:
                code_lines.append(line)
            elif not is_code and in_code_block:
                in_code_block = False
                if code_lines:
                    formatted_lines.append(format_code_block('\n'.join(code_lines)))
                formatted_lines.append(line)
                code_lines = []
            else:
                formatted_lines.append(line)
        
        # Handle case where text ends with code
        if in_code_block and code_lines:
            formatted_lines.append(format_code_block('\n'.join(code_lines)))
        
        return '\n'.join(formatted_lines)
    
    async def _handle_slash_command(self, message: SlackMessage) -> None:
        """
        Handle slash commands from Slack.
        
        Args:
            message: Slack message containing slash command
        """
        command_parts = message.text.split()
        command = command_parts[0].lower()
        args = command_parts[1:] if len(command_parts) > 1 else []
        
        if command in self.slash_commands:
            try:
                await self.slash_commands[command](args)
            except Exception as e:
                self.logger.error(f"Error executing slash command {command}: {e}")
                if self.slack_message_callback:
                    await self.slack_message_callback(
                        channel=self.current_session.project_name if self.current_session else "unknown",
                        text=f"❌ Error executing command `{command}`: {str(e)}"
                    )
        else:
            # Unknown slash command - send to Claude anyway
            await self.subprocess_handler.send_message(message.text)
    
    # Slash command handlers
    
    async def _handle_help_command(self, args: List[str]) -> None:
        """Handle /help command."""
        help_text = """
🔧 **Available Slash Commands:**

• `/help` - Show this help message
• `/exit` - Exit current Claude session
• `/clear` - Clear conversation history
• `/save [filename]` - Save conversation to file
• `/files` - List files in current directory
• `/status` - Show session status

**Note:** These commands are sent directly to Claude CLI.
        """
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=help_text.strip()
            )
    
    async def _handle_exit_command(self, args: List[str]) -> None:
        """Handle /exit command."""
        # Send exit command to Claude
        await self.subprocess_handler.send_message("/exit")
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text="👋 Exiting Claude session..."
            )
    
    async def _handle_clear_command(self, args: List[str]) -> None:
        """Handle /clear command."""
        # Send clear command to Claude
        await self.subprocess_handler.send_message("/clear")
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text="🧹 Clearing conversation history..."
            )
    
    async def _handle_save_command(self, args: List[str]) -> None:
        """Handle /save command."""
        filename = args[0] if args else "conversation.txt"
        
        # Send save command to Claude
        await self.subprocess_handler.send_message(f"/save {filename}")
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=f"💾 Saving conversation to `{filename}`..."
            )
    
    async def _handle_files_command(self, args: List[str]) -> None:
        """Handle /files command."""
        # Send files command to Claude
        await self.subprocess_handler.send_message("/files")
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text="📁 Listing files..."
            )
    
    async def _handle_status_command(self, args: List[str]) -> None:
        """Handle /status command."""
        if not self.current_session:
            status_text = "❌ No active session"
        else:
            process_info = self.subprocess_handler.get_process_info()
            status_text = f"""
📊 **Session Status:**

• **Session ID:** `{self.current_session.session_id}`
• **Project:** `{self.current_session.project_name}`
• **Status:** `{self.current_session.status.value}`
• **Process ID:** `{process_info.get('pid', 'N/A')}`
• **Running:** `{process_info.get('is_running', False)}`
• **Started:** `{process_info.get('start_time', 'N/A')}`
• **Last Activity:** `{process_info.get('last_activity', 'N/A')}`
            """
        
        if self.slack_message_callback:
            await self.slack_message_callback(
                channel=self.current_session.project_name if self.current_session else "unknown",
                text=status_text.strip()
            )
    
    def get_streaming_stats(self) -> Dict[str, Any]:
        """
        Get statistics about message streaming.
        
        Returns:
            Dict[str, Any]: Streaming statistics
        """
        return {
            "is_streaming": self.is_streaming,
            "current_session_id": self.current_session.session_id if self.current_session else None,
            "pending_prompts": len(self.pending_prompts),
            "response_buffer_size": len(self.response_buffer),
            "last_response_time": self.last_response_time.isoformat(),
            "available_slash_commands": list(self.slash_commands.keys())
        }