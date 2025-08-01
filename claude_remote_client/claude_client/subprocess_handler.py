"""
Claude Code CLI subprocess handler.

This module manages Claude Code CLI processes with async subprocess management,
stdin/stdout communication, and process lifecycle management.
"""

import asyncio
import logging
import os
import signal
from typing import Optional, AsyncIterator, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from .handler_interface import (
    ClaudeHandlerInterface, 
    HandlerType, 
    HandlerCapabilities, 
    SessionInfo
)
from ..models import ClaudeSession, SessionStatus
from ..config import ClaudeConfig
from ..exceptions import ClaudeProcessError
from ..utils import setup_logging, validate_project_path


class SubprocessClaudeHandler(ClaudeHandlerInterface):
    """
    Handler for managing Claude Code CLI subprocess with async communication.
    
    Provides process lifecycle management, stdin/stdout communication,
    and proper cleanup for Claude Code CLI processes. Supports both interactive
    and non-interactive modes, JSON output, and session management.
    """
    
    def __init__(self, config: ClaudeConfig):
        """
        Initialize the subprocess handler.
        
        Args:
            config: Claude configuration containing CLI path and settings
        """
        self.config = config
        self.logger = setup_logging()
        
        # Process management
        self.process: Optional[asyncio.subprocess.Process] = None
        self.session: Optional[ClaudeSession] = None
        
        # Communication buffers
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        
        # Process monitoring
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        
        # Communication settings
        self.read_timeout = 1.0  # Timeout for reading output
        self.write_timeout = 5.0  # Timeout for writing input
        self.startup_timeout = 30.0  # Timeout for process startup
        self.startup_event = asyncio.Event()
        
        # Output handling
        self.output_handlers = []
        self.error_handlers = []
        
        # Claude Code CLI specific settings
        self.output_format = "text"  # text, json, stream-json
        self.model: Optional[str] = None
        self.claude_session_id: Optional[str] = None  # Claude Code's internal session ID
        self.is_interactive = True  # Whether to use interactive mode
        
        # Handler capabilities
        self.capabilities = HandlerCapabilities(
            streaming=True,
            context_window=200000,
            file_upload=True,
            models=["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
            session_persistence=True,
            concurrent_sessions=True,
            interactive_mode=True,
            batch_processing=False,
            custom_tools=False,
            mcp_servers=False
        )
    
    async def start_process(self, session: ClaudeSession, resume_claude_session: Optional[str] = None) -> None:
        """
        Start a Claude Code CLI process for the given session.
        
        Args:
            session: Claude session to start process for
            resume_claude_session: Optional Claude Code session ID to resume
        
        Raises:
            ClaudeProcessError: If process fails to start
        """
        if self.is_running:
            raise ClaudeProcessError("Claude process is already running")
        
        if not validate_project_path(session.project_path):
            raise ClaudeProcessError(f"Invalid project path: {session.project_path}")
        
        self.session = session
        
        try:
            self.logger.info(f"Starting Claude process for project: {session.project_path}")
            
            # Build command arguments
            cmd_args = [self.config.cli_path]
            
            # Add Claude Code specific arguments
            if self.output_format != "text":
                cmd_args.extend(["--output-format", self.output_format])
            
            if self.model:
                cmd_args.extend(["--model", self.model])
            
            if resume_claude_session:
                cmd_args.extend(["--resume", resume_claude_session])
                self.claude_session_id = resume_claude_session
            
            # Add any default arguments
            cmd_args.extend(self.config.default_args)
            
            # Set working directory to project path
            working_dir = Path(session.project_path).resolve()
            
            # Start the process
            self.process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=os.environ.copy()
            )
            
            # Update session status
            session.status = SessionStatus.STARTING
            session.process_id = self.process.pid
            
            # Wait for process to be ready
            await self._wait_for_startup()
            
            # Update status and timing
            self.is_running = True
            self.start_time = datetime.now()
            self.last_activity = datetime.now()
            session.status = SessionStatus.ACTIVE
            
            self.logger.info(f"Claude process started successfully (PID: {self.process.pid})")
            
            # Start background tasks for output handling
            asyncio.create_task(self._handle_stdout())
            asyncio.create_task(self._handle_stderr())
            asyncio.create_task(self._monitor_process())
        
        except Exception as e:
            session.status = SessionStatus.ERROR
            self.is_running = False
            
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except Exception:
                    pass
                self.process = None
            
            raise ClaudeProcessError(f"Failed to start Claude process: {str(e)}")
    
    async def execute_command(self, command: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute a single command in non-interactive mode using Claude Code CLI.
        
        Args:
            command: Command to execute
            timeout: Optional timeout for command execution
        
        Returns:
            Dict containing response data
        
        Raises:
            ClaudeProcessError: If execution fails
        """
        try:
            # Validate command input
            if not command or not isinstance(command, str):
                raise ClaudeProcessError("Invalid command: must be a non-empty string")
            
            # Sanitize command to prevent injection
            command = command.strip()
            if any(char in command for char in ['&', '|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r']):
                raise ClaudeProcessError("Invalid command: contains potentially dangerous characters")
            
            # Build command for non-interactive mode
            cmd_args = [self.config.cli_path, "-p", command]
            
            if self.output_format == "json":
                cmd_args.extend(["--output-format", "json"])
            
            if self.model:
                cmd_args.extend(["--model", self.model])
            
            # Set timeout
            exec_timeout = timeout or self.config.timeout
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.session.project_path if self.session else None,
                env=os.environ.copy()
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=exec_timeout
            )
            
            # Parse response based on format
            if self.output_format == "json":
                try:
                    response_data = json.loads(stdout.decode('utf-8'))
                    return {
                        "success": process.returncode == 0,
                        "data": response_data,
                        "error": stderr.decode('utf-8') if stderr else None
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "data": stdout.decode('utf-8'),
                        "error": "Failed to parse JSON response"
                    }
            else:
                return {
                    "success": process.returncode == 0,
                    "data": stdout.decode('utf-8'),
                    "error": stderr.decode('utf-8') if stderr else None
                }
        
        except asyncio.TimeoutError:
            raise ClaudeProcessError(f"Command execution timed out after {exec_timeout}s")
        except Exception as e:
            raise ClaudeProcessError(f"Failed to execute command: {str(e)}")
    
    async def _wait_for_startup(self) -> None:
        """
        Wait for Claude process to be ready for input.
        
        Raises:
            ClaudeProcessError: If startup times out or fails
        """
        try:
            await asyncio.wait_for(self.startup_event.wait(), timeout=self.startup_timeout)
        except asyncio.TimeoutError:
            raise ClaudeProcessError("Claude process startup timeout")
    
    async def send_message_to_process(self, message: str) -> None:
        """
        Send a message to the Claude process.
        
        Args:
            message: Message to send to Claude
        
        Raises:
            ClaudeProcessError: If sending fails or process is not running
        """
        if not self.is_running or not self.process or not self.process.stdin:
            raise ClaudeProcessError("Claude process is not running")
        
        try:
            # Ensure message ends with newline
            if not message.endswith('\n'):
                message += '\n'
            
            # Write to stdin
            self.process.stdin.write(message.encode('utf-8'))
            await asyncio.wait_for(
                self.process.stdin.drain(),
                timeout=self.write_timeout
            )
            
            # Update activity timestamp
            self.last_activity = datetime.now()
            
            # Add to session history
            if self.session:
                self.session.add_message("user", message.strip())
            
            self.logger.debug(f"Sent message to Claude: {message[:100]}...")
        
        except Exception as e:
            raise ClaudeProcessError(f"Failed to send message to Claude: {str(e)}")
    
    async def _handle_stdout(self) -> None:
        """Background task to handle stdout from Claude process."""
        if not self.process or not self.process.stdout:
            return
        
        try:
            while self.is_running and self.process.returncode is None:
                try:
                    output = await asyncio.wait_for(
                        self.process.stdout.read(1024),
                        timeout=1.0
                    )
                    
                    if output:
                        decoded_output = output.decode('utf-8', errors='replace')
                        self.stdout_buffer += decoded_output
                        self.last_activity = datetime.now()

                        # If startup event is not set, check for prompt
                        if not self.startup_event.is_set():
                            if any(indicator in self.stdout_buffer.lower() for indicator in ['>', 'claude>', 'ready']):
                                self.startup_event.set()
                        
                        # Parse JSON output if in JSON mode
                        if self.output_format in ["json", "stream-json"]:
                            self._parse_json_output(decoded_output)
                        
                        # Notify output handlers
                        for handler in self.output_handlers:
                            try:
                                await handler(decoded_output)
                            except Exception as e:
                                self.logger.error(f"Error in output handler: {e}")
                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Error handling stdout: {e}")
                    break
        
        except Exception as e:
            self.logger.error(f"Fatal error in stdout handler: {e}")
    
    def _parse_json_output(self, output: str) -> None:
        """
        Parse JSON output from Claude Code CLI.
        
        Args:
            output: Raw output string to parse
        """
        try:
            # Handle stream-json format (newline-delimited JSON)
            if self.output_format == "stream-json":
                for line in output.strip().split('\n'):
                    if line:
                        data = json.loads(line)
                        # Extract Claude session ID if present
                        if 'session_id' in data:
                            self.claude_session_id = data['session_id']
                        # Store parsed data
                        if hasattr(self, 'json_responses'):
                            self.json_responses.append(data)
                        else:
                            self.json_responses = [data]
            else:
                # Regular JSON format
                data = json.loads(output)
                if 'session_id' in data:
                    self.claude_session_id = data['session_id']
                self.json_response = data
        except json.JSONDecodeError:
            # Not valid JSON, ignore
            pass
    
    async def _handle_stderr(self) -> None:
        """Background task to handle stderr from Claude process."""
        if not self.process or not self.process.stderr:
            return
        
        try:
            while self.is_running and self.process.returncode is None:
                try:
                    error_output = await asyncio.wait_for(
                        self.process.stderr.read(1024),
                        timeout=1.0
                    )
                    
                    if error_output:
                        decoded_error = error_output.decode('utf-8', errors='replace')
                        self.stderr_buffer += decoded_error
                        
                        self.logger.warning(f"Claude stderr: {decoded_error.strip()}")
                        
                        # Notify error handlers
                        for handler in self.error_handlers:
                            try:
                                await handler(decoded_error)
                            except Exception as e:
                                self.logger.error(f"Error in error handler: {e}")
                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Error handling stderr: {e}")
                    break
        
        except Exception as e:
            self.logger.error(f"Fatal error in stderr handler: {e}")
    
    async def _monitor_process(self) -> None:
        """Background task to monitor process health."""
        if not self.process:
            return
        
        try:
            # Wait for process to exit
            return_code = await self.process.wait()
            
            self.logger.info(f"Claude process exited with code: {return_code}")
            
            # Update status
            self.is_running = False
            if self.session:
                if return_code == 0:
                    self.session.status = SessionStatus.INACTIVE
                else:
                    self.session.status = SessionStatus.ERROR
        
        except Exception as e:
            self.logger.error(f"Error monitoring process: {e}")
            self.is_running = False
            if self.session:
                self.session.status = SessionStatus.ERROR
    
    async def terminate_process(self, timeout: float = 10.0) -> None:
        """
        Terminate the Claude process gracefully.
        
        Args:
            timeout: Timeout for graceful termination
        
        Raises:
            ClaudeProcessError: If termination fails
        """
        if not self.process:
            return
        
        try:
            self.logger.info("Terminating Claude process...")
            
            # Update status
            self.is_running = False
            if self.session:
                self.session.status = SessionStatus.STOPPING
            
            # Try graceful termination first
            if self.process.returncode is None:
                self.process.terminate()
                
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=timeout)
                    self.logger.info("Claude process terminated gracefully")
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    self.logger.warning("Graceful termination timed out, force killing...")
                    self.process.kill()
                    await self.process.wait()
                    self.logger.info("Claude process force killed")
            
            # Update final status
            if self.session:
                self.session.status = SessionStatus.INACTIVE
                self.session.process_id = None
            
            # Clean up
            self.process = None
            self.stdout_buffer = ""
            self.stderr_buffer = ""
        
        except Exception as e:
            raise ClaudeProcessError(f"Failed to terminate Claude process: {str(e)}")
    
    def add_output_handler(self, handler) -> None:
        """
        Add a handler for Claude output.
        
        Args:
            handler: Async function that takes output string
        """
        self.output_handlers.append(handler)
    
    def remove_output_handler(self, handler) -> None:
        """
        Remove an output handler.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self.output_handlers:
            self.output_handlers.remove(handler)
    
    def add_error_handler(self, handler) -> None:
        """
        Add a handler for Claude errors.
        
        Args:
            handler: Async function that takes error string
        """
        self.error_handlers.append(handler)
    
    def remove_error_handler(self, handler) -> None:
        """
        Remove an error handler.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self.error_handlers:
            self.error_handlers.remove(handler)
    
    def get_process_info(self) -> Dict[str, Any]:
        """
        Get information about the current process.
        
        Returns:
            Dict[str, Any]: Process information
        """
        return {
            "is_running": self.is_running,
            "pid": self.process.pid if self.process else None,
            "return_code": self.process.returncode if self.process else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "session_id": self.session.session_id if self.session else None,
            "claude_session_id": self.claude_session_id,
            "project_path": self.session.project_path if self.session else None,
            "stdout_buffer_size": len(self.stdout_buffer),
            "stderr_buffer_size": len(self.stderr_buffer),
            "output_format": self.output_format,
            "model": self.model
        }
    
    def get_recent_output(self, lines: int = 50) -> str:
        """
        Get recent output from Claude.
        
        Args:
            lines: Number of recent lines to return
        
        Returns:
            str: Recent output
        """
        if not self.stdout_buffer:
            return ""
        
        output_lines = self.stdout_buffer.split('\n')
        recent_lines = output_lines[-lines:] if len(output_lines) > lines else output_lines
        return '\n'.join(recent_lines)
    
    def get_recent_errors(self, lines: int = 20) -> str:
        """
        Get recent errors from Claude.
        
        Args:
            lines: Number of recent error lines to return
        
        Returns:
            str: Recent errors
        """
        if not self.stderr_buffer:
            return ""
        
        error_lines = self.stderr_buffer.split('\n')
        recent_lines = error_lines[-lines:] if len(error_lines) > lines else error_lines
        return '\n'.join(recent_lines)
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the Claude process.
        
        Returns:
            bool: True if process is healthy, False otherwise
        """
        if not self.is_running or not self.process:
            return False
        
        # Check if process is still alive
        if self.process.returncode is not None:
            return False
        
        # Check if we've had recent activity (within last 5 minutes)
        if self.last_activity:
            inactive_time = (datetime.now() - self.last_activity).total_seconds()
            if inactive_time > 300:  # 5 minutes
                self.logger.warning(f"Claude process has been inactive for {inactive_time} seconds")
        
        return True
    
    def get_claude_session_id(self) -> Optional[str]:
        """
        Get the Claude Code internal session ID if available.
        
        Returns:
            Optional[str]: Claude Code session ID
        """
        return self.claude_session_id
    
    async def continue_session(self) -> None:
        """
        Continue the most recent Claude Code session.
        
        Raises:
            ClaudeProcessError: If continuation fails
        """
        if not self.session:
            raise ClaudeProcessError("No session to continue")
        
        # Terminate current process if running
        if self.is_running:
            await self.terminate_process()
        
        # Start new process with --continue flag
        cmd_args = [self.config.cli_path, "--continue"]
        
        if self.output_format != "text":
            cmd_args.extend(["--output-format", self.output_format])
        
        if self.model:
            cmd_args.extend(["--model", self.model])
        
        cmd_args.extend(self.config.default_args)
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(self.session.project_path).resolve()),
                env=os.environ.copy()
            )
            
            self.is_running = True
            self.session.status = SessionStatus.ACTIVE
            self.session.process_id = self.process.pid
            
            # Start background tasks
            asyncio.create_task(self._handle_stdout())
            asyncio.create_task(self._handle_stderr())
            asyncio.create_task(self._monitor_process())
            
            self.logger.info(f"Continued Claude session (PID: {self.process.pid})")
        
        except Exception as e:
            raise ClaudeProcessError(f"Failed to continue session: {str(e)}")
    
    # Interface implementation methods
    
    async def initialize(self) -> None:
        """Initialize the subprocess handler."""
        # Subprocess handler doesn't need explicit initialization
        pass
    
    async def start_session(
        self,
        project_path: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Start a new Claude session."""
        # Create a session object
        session = ClaudeSession(
            session_id=session_id or f"subprocess_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            project_path=project_path,
            status=SessionStatus.STARTING
        )
        
        await self.start_process(session)
        return session.session_id
    
    async def send_message(self, message: str, **kwargs) -> str:
        """Send a message and get response (interface implementation)."""
        if not self.is_running:
            raise ClaudeProcessError("No active session")
        
        await self.send_message_to_process(message)
        
        # Wait for response (simplified implementation)
        await asyncio.sleep(0.1)
        return self.get_recent_output(10)
    
    async def stream_message(
        self,
        message: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Send a message and stream the response."""
        if not self.is_running:
            raise ClaudeProcessError("No active session")
        
        await self.send_message_to_process(message)
        
        # Simplified streaming implementation
        # In a real implementation, this would stream actual output
        response_parts = ["Subprocess ", "streaming ", "response"]
        for part in response_parts:
            await asyncio.sleep(0.1)
            yield part
    
    async def end_session(self) -> None:
        """End the current session."""
        await self.terminate_process()
    
    async def get_session_info(self) -> SessionInfo:
        """Get session information."""
        if not self.session:
            raise ClaudeProcessError("No active session")
        
        return SessionInfo(
            session_id=self.session.session_id,
            handler_type=HandlerType.SUBPROCESS,
            status=self.session.status,
            created_at=self.start_time or datetime.now(),
            last_activity=self.last_activity or datetime.now(),
            message_count=len(self.session.conversation_history),
            context_size=sum(len(msg.content) for msg in self.session.conversation_history),
            project_path=self.session.project_path,
            model=self.model,
            metadata={
                'process_id': self.process.pid if self.process else None,
                'output_format': self.output_format,
                'claude_session_id': self.claude_session_id
            }
        )
    
    async def is_healthy(self) -> bool:
        """Check if handler is healthy."""
        return await self.health_check()
    
    async def get_context_info(self) -> Dict[str, Any]:
        """Get context information."""
        return {
            'total_tokens': sum(len(msg.content) for msg in self.session.conversation_history) if self.session else 0,
            'max_tokens': self.capabilities.context_window,
            'message_count': len(self.session.conversation_history) if self.session else 0,
            'session_id': self.session.session_id if self.session else None,
            'model': self.model,
            'process_id': self.process.pid if self.process else None
        }
    
    async def clear_context(self) -> None:
        """Clear context while maintaining session."""
        if self.session:
            self.session.conversation_history.clear()
    
    async def add_context_file(self, file_path: str, content: str) -> None:
        """Add a file to context."""
        # For subprocess, we could send a command to load the file
        command = f"Please consider this file: {file_path}\n\n{content}"
        await self.send_message_to_process(command)
    
    async def get_capabilities(self) -> HandlerCapabilities:
        """Get handler capabilities."""
        return self.capabilities
    
    async def set_model(self, model: str) -> None:
        """Set the model."""
        if model not in self.capabilities.models:
            raise ValueError(f"Model {model} not supported")
        self.model = model
    
    async def set_temperature(self, temperature: float) -> None:
        """Set temperature."""
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")
        # Store temperature setting (would be used in actual implementation)
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.terminate_process()