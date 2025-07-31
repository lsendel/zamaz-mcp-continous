"""
Claude CLI subprocess handler.

This module manages Claude CLI processes with async subprocess management,
stdin/stdout communication, and process lifecycle management.
"""

import asyncio
import logging
import os
import signal
from typing import Optional, AsyncIterator, Dict, Any
from datetime import datetime
from pathlib import Path

from ..models import ClaudeSession, SessionStatus
from ..config import ClaudeConfig
from ..exceptions import ClaudeProcessError
from ..utils import setup_logging, validate_project_path


class SubprocessClaudeHandler:
    """
    Handler for managing Claude CLI subprocess with async communication.
    
    Provides process lifecycle management, stdin/stdout communication,
    and proper cleanup for Claude CLI processes.
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
        
        # Output handling
        self.output_handlers = []
        self.error_handlers = []
    
    async def start_process(self, session: ClaudeSession) -> None:
        """
        Start a Claude CLI process for the given session.
        
        Args:
            session: Claude session to start process for
        
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
            cmd_args = [self.config.cli_path] + self.config.default_args
            
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
    
    async def _wait_for_startup(self) -> None:
        """
        Wait for Claude process to be ready for input.
        
        Raises:
            ClaudeProcessError: If startup times out or fails
        """
        if not self.process:
            raise ClaudeProcessError("No process to wait for")
        
        try:
            # Wait for initial output or timeout
            startup_complete = False
            start_time = datetime.now()
            
            while not startup_complete:
                if (datetime.now() - start_time).total_seconds() > self.startup_timeout:
                    raise ClaudeProcessError("Claude process startup timeout")
                
                # Check if process is still running
                if self.process.returncode is not None:
                    raise ClaudeProcessError(f"Claude process exited during startup with code {self.process.returncode}")
                
                # Try to read some initial output
                try:
                    output = await asyncio.wait_for(
                        self.process.stdout.read(1024),
                        timeout=0.5
                    )
                    
                    if output:
                        self.stdout_buffer += output.decode('utf-8', errors='replace')
                        # Look for Claude prompt or ready indicator
                        if any(indicator in self.stdout_buffer.lower() for indicator in ['>', '$', 'claude', 'ready']):
                            startup_complete = True
                    
                except asyncio.TimeoutError:
                    # No output yet, continue waiting
                    await asyncio.sleep(0.1)
        
        except Exception as e:
            raise ClaudeProcessError(f"Error during startup: {str(e)}")
    
    async def send_message(self, message: str) -> None:
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
    
    async def read_output(self, timeout: Optional[float] = None) -> AsyncIterator[str]:
        """
        Read output from Claude process as it becomes available.
        
        Args:
            timeout: Optional timeout for reading
        
        Yields:
            str: Output chunks from Claude
        
        Raises:
            ClaudeProcessError: If reading fails or process is not running
        """
        if not self.is_running or not self.process:
            raise ClaudeProcessError("Claude process is not running")
        
        read_timeout = timeout or self.read_timeout
        
        try:
            while self.is_running and self.process.returncode is None:
                try:
                    # Read available output
                    output = await asyncio.wait_for(
                        self.process.stdout.read(1024),
                        timeout=read_timeout
                    )
                    
                    if output:
                        decoded_output = output.decode('utf-8', errors='replace')
                        self.stdout_buffer += decoded_output
                        self.last_activity = datetime.now()
                        
                        # Add to session history
                        if self.session:
                            self.session.add_message("assistant", decoded_output)
                        
                        yield decoded_output
                    else:
                        # No more output available
                        break
                
                except asyncio.TimeoutError:
                    # No output available right now
                    yield ""
                    await asyncio.sleep(0.1)
        
        except Exception as e:
            raise ClaudeProcessError(f"Error reading Claude output: {str(e)}")
    
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
            "project_path": self.session.project_path if self.session else None,
            "stdout_buffer_size": len(self.stdout_buffer),
            "stderr_buffer_size": len(self.stderr_buffer)
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