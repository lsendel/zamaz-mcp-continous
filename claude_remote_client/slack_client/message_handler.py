"""
Message handler for processing Slack messages.

This module handles message formatting, threading, and coordination
between Slack and Claude.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..models import SlackMessage
from ..exceptions import SlackConnectionError
from ..utils import (
    setup_logging, format_error_for_slack, format_success_for_slack,
    format_info_for_slack, format_code_block, truncate_message
)
from .command_router import CommandRouter, CommandResult


class MessageHandler:
    """
    Handler for processing Slack messages and coordinating responses.
    
    Manages message formatting, threading, code block handling,
    and coordination between command processing and Claude forwarding.
    """
    
    def __init__(self, slack_client, command_router: Optional[CommandRouter] = None):
        """
        Initialize the message handler.
        
        Args:
            slack_client: SlackBotClient instance for sending messages
            command_router: CommandRouter for handling commands (optional)
        """
        self.slack_client = slack_client
        self.command_router = command_router or CommandRouter()
        self.logger = setup_logging()
        
        # Message threading support
        self.active_threads: Dict[str, str] = {}  # user_id -> thread_ts
        
        # Message formatting settings
        self.max_message_length = 3000
        self.code_block_threshold = 100  # Lines of code to trigger code block
        
        # Claude forwarding callback (to be set by main application)
        self.claude_message_callback = None
    
    def set_claude_callback(self, callback):
        """
        Set callback function for forwarding messages to Claude.
        
        Args:
            callback: Async function that takes (message, session_id) and handles Claude communication
        """
        self.claude_message_callback = callback
    
    async def handle_message(self, message: SlackMessage) -> None:
        """
        Main message handling entry point.
        
        Args:
            message: Incoming Slack message to process
        """
        try:
            self.logger.info(f"Processing message from user {message.user_id}: {message.text[:100]}...")
            
            # Route the message through command router
            result = await self.command_router.route_message(message)
            
            if result.should_forward_to_claude:
                # Forward to Claude
                await self._forward_to_claude(message)
            else:
                # Handle as command result
                await self._send_command_response(message, result)
        
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            await self._send_error_response(message, e)
    
    async def _forward_to_claude(self, message: SlackMessage) -> None:
        """
        Forward message to Claude for processing.
        
        Args:
            message: Message to forward to Claude
        """
        if not self.claude_message_callback:
            await self._send_error_response(
                message,
                Exception("Claude integration not configured")
            )
            return
        
        try:
            # Send typing indicator
            typing_ts = await self.slack_client.send_typing_indicator(message.channel_id)
            
            # Forward to Claude (callback should handle the response)
            await self.claude_message_callback(message)
            
            # Clean up typing indicator if it was sent
            if typing_ts:
                await self.slack_client.delete_message(message.channel_id, typing_ts)
        
        except Exception as e:
            self.logger.error(f"Error forwarding to Claude: {e}")
            await self._send_error_response(message, e)
    
    async def _send_command_response(self, original_message: SlackMessage, result: CommandResult) -> None:
        """
        Send response for command execution.
        
        Args:
            original_message: Original message that triggered the command
            result: Result of command execution
        """
        try:
            # Format the response message
            if result.success:
                response_text = result.message
            else:
                response_text = result.message
            
            # Truncate if too long
            response_text = truncate_message(response_text, self.max_message_length)
            
            # Send response (in thread if applicable)
            thread_ts = self._get_thread_ts(original_message)
            
            await self.slack_client.send_message(
                channel=original_message.channel_id,
                text=response_text,
                thread_ts=thread_ts
            )
        
        except Exception as e:
            self.logger.error(f"Error sending command response: {e}")
            await self._send_error_response(original_message, e)
    
    async def _send_error_response(self, original_message: SlackMessage, error: Exception) -> None:
        """
        Send error response to Slack.
        
        Args:
            original_message: Original message that caused the error
            error: Exception that occurred
        """
        try:
            error_text = format_error_for_slack(error)
            error_text = truncate_message(error_text, self.max_message_length)
            
            thread_ts = self._get_thread_ts(original_message)
            
            await self.slack_client.send_message(
                channel=original_message.channel_id,
                text=error_text,
                thread_ts=thread_ts
            )
        
        except Exception as e:
            self.logger.error(f"Failed to send error response: {e}")
    
    def _get_thread_ts(self, message: SlackMessage) -> Optional[str]:
        """
        Get thread timestamp for response.
        
        Args:
            message: Original message
        
        Returns:
            Optional[str]: Thread timestamp if threading is enabled
        """
        # If the original message was in a thread, continue the thread
        if message.thread_ts:
            return message.thread_ts
        
        # For command messages, we might want to start a new thread
        # This can be configured based on preferences
        return None
    
    async def stream_response(self, channel: str, response_stream, thread_ts: Optional[str] = None) -> None:
        """
        Stream a response from Claude to Slack with real-time updates.
        
        Args:
            channel: Slack channel ID
            response_stream: Async iterator of response chunks from Claude
            thread_ts: Optional thread timestamp
        """
        try:
            # Send initial message
            response = await self.slack_client.send_message(
                channel=channel,
                text="⏳ Claude is thinking...",
                thread_ts=thread_ts
            )
            
            message_ts = response.get("ts")
            if not message_ts:
                self.logger.error("Failed to get message timestamp for streaming")
                return
            
            # Accumulate response chunks
            accumulated_response = ""
            last_update_time = datetime.now()
            update_interval = 2.0  # Update every 2 seconds
            
            async for chunk in response_stream:
                accumulated_response += chunk
                
                # Update message periodically or when response is complete
                now = datetime.now()
                if (now - last_update_time).total_seconds() >= update_interval:
                    formatted_response = self._format_claude_response(accumulated_response)
                    formatted_response = truncate_message(formatted_response, self.max_message_length)
                    
                    await self.slack_client.update_message(
                        channel=channel,
                        ts=message_ts,
                        text=formatted_response
                    )
                    
                    last_update_time = now
            
            # Final update with complete response
            final_response = self._format_claude_response(accumulated_response)
            final_response = truncate_message(final_response, self.max_message_length)
            
            await self.slack_client.update_message(
                channel=channel,
                ts=message_ts,
                text=final_response
            )
        
        except Exception as e:
            self.logger.error(f"Error streaming response: {e}")
            # Try to send error message
            error_text = format_error_for_slack(e)
            await self.slack_client.send_message(
                channel=channel,
                text=error_text,
                thread_ts=thread_ts
            )
    
    def _format_claude_response(self, response: str) -> str:
        """
        Format Claude's response for Slack display.
        
        Args:
            response: Raw response from Claude
        
        Returns:
            str: Formatted response for Slack
        """
        if not response.strip():
            return "⏳ Claude is thinking..."
        
        # Detect and format code blocks
        formatted_response = self._format_code_blocks(response)
        
        return formatted_response
    
    def _format_code_blocks(self, text: str) -> str:
        """
        Format code blocks in text for better Slack display.
        
        Args:
            text: Text that may contain code
        
        Returns:
            str: Text with properly formatted code blocks
        """
        # This is a simplified implementation
        # In a real implementation, you might want more sophisticated code detection
        
        lines = text.split('\n')
        formatted_lines = []
        in_code_block = False
        code_block_lines = []
        
        for line in lines:
            # Simple heuristic: lines that start with spaces and contain code-like patterns
            is_code_line = (
                line.startswith('    ') or  # Indented
                line.startswith('\t') or    # Tab indented
                any(keyword in line for keyword in ['def ', 'class ', 'import ', 'from ', '= ', '== ', '!= ']) or
                line.strip().startswith(('if ', 'for ', 'while ', 'try:', 'except:', 'finally:'))
            )
            
            if is_code_line and not in_code_block:
                # Start of code block
                in_code_block = True
                code_block_lines = [line]
            elif is_code_line and in_code_block:
                # Continue code block
                code_block_lines.append(line)
            elif not is_code_line and in_code_block:
                # End of code block
                in_code_block = False
                if len(code_block_lines) > 1:  # Only format multi-line code blocks
                    formatted_lines.append(format_code_block('\n'.join(code_block_lines)))
                else:
                    formatted_lines.extend(code_block_lines)
                formatted_lines.append(line)
                code_block_lines = []
            else:
                # Regular line
                formatted_lines.append(line)
        
        # Handle case where text ends with code block
        if in_code_block and code_block_lines:
            if len(code_block_lines) > 1:
                formatted_lines.append(format_code_block('\n'.join(code_block_lines)))
            else:
                formatted_lines.extend(code_block_lines)
        
        return '\n'.join(formatted_lines)
    
    async def send_status_update(self, channel: str, status: str, thread_ts: Optional[str] = None) -> None:
        """
        Send a status update message.
        
        Args:
            channel: Slack channel ID
            status: Status message to send
            thread_ts: Optional thread timestamp
        """
        try:
            formatted_status = format_info_for_slack(status)
            await self.slack_client.send_message(
                channel=channel,
                text=formatted_status,
                thread_ts=thread_ts
            )
        except Exception as e:
            self.logger.error(f"Error sending status update: {e}")
    
    async def send_success_message(self, channel: str, message: str, details: Optional[str] = None, 
                                 thread_ts: Optional[str] = None) -> None:
        """
        Send a success message.
        
        Args:
            channel: Slack channel ID
            message: Success message
            details: Optional additional details
            thread_ts: Optional thread timestamp
        """
        try:
            formatted_message = format_success_for_slack(message, details)
            await self.slack_client.send_message(
                channel=channel,
                text=formatted_message,
                thread_ts=thread_ts
            )
        except Exception as e:
            self.logger.error(f"Error sending success message: {e}")
    
    def enable_threading_for_user(self, user_id: str, thread_ts: str) -> None:
        """
        Enable threading for a specific user.
        
        Args:
            user_id: Slack user ID
            thread_ts: Thread timestamp to use for this user's messages
        """
        self.active_threads[user_id] = thread_ts
    
    def disable_threading_for_user(self, user_id: str) -> None:
        """
        Disable threading for a specific user.
        
        Args:
            user_id: Slack user ID
        """
        if user_id in self.active_threads:
            del self.active_threads[user_id]
    
    def get_message_stats(self) -> Dict[str, Any]:
        """
        Get statistics about message handling.
        
        Returns:
            Dict[str, Any]: Message handling statistics
        """
        return {
            "active_threads": len(self.active_threads),
            "max_message_length": self.max_message_length,
            "code_block_threshold": self.code_block_threshold,
            "claude_callback_configured": self.claude_message_callback is not None
        }