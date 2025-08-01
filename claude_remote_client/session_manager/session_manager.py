"""
Session manager for handling multiple Claude sessions.

This module manages the lifecycle of Claude sessions including creation,
switching, status reporting, and cleanup.
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import aiofiles

from ..models import ClaudeSession, SessionStatus
from ..config import Config, ClaudeConfig
from ..exceptions import SessionError, ClaudeProcessError
from ..utils import setup_logging, ensure_directory_exists, validate_project_path
from ..claude_client.subprocess_handler import SubprocessClaudeHandler
from ..claude_client.message_streamer import MessageStreamer
from ..resource_limits import with_session_limit, get_resource_limiter


class SessionManager:
    """
    Manager for multiple Claude sessions with lifecycle management.
    
    Handles session creation, switching, status tracking, and cleanup
    for multiple concurrent Claude sessions across different projects.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the session manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = setup_logging()
        
        # Session storage
        self.sessions: Dict[str, ClaudeSession] = {}
        self.subprocess_handlers: Dict[str, SubprocessClaudeHandler] = {}
        self.message_streamers: Dict[str, MessageStreamer] = {}
        
        # Current active session
        self.active_session_id: Optional[str] = None
        
        # Session persistence
        self.sessions_file = Path(config.data_dir) / "sessions.json"
        
        # Limits and settings
        self.max_sessions = config.max_sessions
        self.session_timeout = 3600  # 1 hour of inactivity
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Ensure data directory exists
        ensure_directory_exists(config.data_dir)
    
    async def start(self) -> None:
        """Start the session manager and background tasks."""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info("Starting session manager...")
        
        # Load existing sessions
        await self._load_sessions()
        
        # Start background cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Session manager started")
    
    async def stop(self) -> None:
        """Stop the session manager and cleanup resources."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("Stopping session manager...")
        
        # Cancel background tasks
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Terminate all active sessions
        await self._terminate_all_sessions()
        
        # Save session state
        await self._save_sessions()
        
        self.logger.info("Session manager stopped")
    
    @with_session_limit
    async def create_session(self, project_path: str, session_id: Optional[str] = None) -> ClaudeSession:
        """
        Create a new Claude session for a project.
        
        Args:
            project_path: Path to the project directory
            session_id: Optional custom session ID
        
        Returns:
            ClaudeSession: Created session
        
        Raises:
            SessionError: If session creation fails
        """
        if not validate_project_path(project_path):
            raise SessionError(f"Invalid project path: {project_path}")
        
        if len(self.sessions) >= self.max_sessions:
            raise SessionError(f"Maximum number of sessions ({self.max_sessions}) reached")
        
        session_id = session_id or str(uuid.uuid4())
        if session_id in self.sessions:
            raise SessionError(f"Session with ID {session_id} already exists")

        session = ClaudeSession(
            session_id=session_id,
            project_path=project_path,
            project_name=Path(project_path).name
        )
        subprocess_handler = SubprocessClaudeHandler(self.config.claude) # Initialize to a mock object
        message_streamer = MessageStreamer(subprocess_handler) # Initialize to a mock object

        try:
            subprocess_handler = await self._create_subprocess_handler(session)
            message_streamer = await self._create_message_streamer(session, subprocess_handler)

            self.sessions[session.session_id] = session
            self.subprocess_handlers[session.session_id] = subprocess_handler
            self.message_streamers[session.session_id] = message_streamer

            if self.active_session_id:
                # Set previous active session to inactive
                if self.active_session_id in self.sessions:
                    self.sessions[self.active_session_id].status = SessionStatus.INACTIVE
                
            self.active_session_id = session.session_id

            self.logger.info(f"Created session {session.session_id} for project: {project_path}")
            await self._save_sessions()

            return session
        except Exception as e:
            # Cleanup partially created resources
            self.logger.error(f"Failed to create session: {e}", exc_info=True)
            
            # Clean up message streamer
            if session.session_id in self.message_streamers:
                try:
                    await self.message_streamers[session.session_id].stop_streaming()
                except Exception as cleanup_error:
                    self.logger.warning(f"Error stopping message streamer during cleanup: {cleanup_error}")
                finally:
                    del self.message_streamers[session.session_id]
            
            # Clean up subprocess handler
            if session.session_id in self.subprocess_handlers:
                try:
                    await self.subprocess_handlers[session.session_id].terminate_process()
                except Exception as cleanup_error:
                    self.logger.warning(f"Error terminating subprocess during cleanup: {cleanup_error}")
                finally:
                    del self.subprocess_handlers[session.session_id]

            # Remove session from tracking
            if session.session_id in self.sessions:
                del self.sessions[session.session_id]
            
            raise SessionError(f"Failed to create session: {str(e)}") from e

    async def _create_subprocess_handler(self, session: ClaudeSession) -> SubprocessClaudeHandler:
        subprocess_handler = SubprocessClaudeHandler(self.config.claude)
        # Check if we have a Claude session ID to resume
        resume_session = session.claude_session_id if session.claude_session_id else None
        await subprocess_handler.start_process(session, resume_claude_session=resume_session)
        # Store the Claude session ID
        if subprocess_handler.get_claude_session_id():
            session.claude_session_id = subprocess_handler.get_claude_session_id()
        return subprocess_handler

    async def _create_message_streamer(self, session: ClaudeSession, subprocess_handler: SubprocessClaudeHandler) -> MessageStreamer:
        message_streamer = MessageStreamer(subprocess_handler)
        await message_streamer.start_streaming(session)
        return message_streamer
    
    async def switch_session(self, session_id: str) -> ClaudeSession:
        """
        Switch to an existing session.
        
        Args:
            session_id: ID of session to switch to
        
        Returns:
            ClaudeSession: The switched-to session
        
        Raises:
            SessionError: If session doesn't exist or switch fails
        """
        if session_id not in self.sessions:
            raise SessionError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        # Check if session is still active
        if session.status not in [SessionStatus.ACTIVE, SessionStatus.INACTIVE]:
            raise SessionError(f"Cannot switch to session in {session.status.value} state")
        
        # Set as active session
        old_active = self.active_session_id
        self.active_session_id = session_id
        
        # Update activity timestamp
        session.update_activity()
        
        self.logger.info(f"Switched from session {old_active} to {session_id}")
        
        return session
    
    async def get_active_session(self) -> Optional[ClaudeSession]:
        """
        Get the currently active session.
        
        Returns:
            Optional[ClaudeSession]: Active session or None if no active session
        """
        if not self.active_session_id or self.active_session_id not in self.sessions:
            return None
        
        return self.sessions[self.active_session_id]
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all sessions with their status information.
        
        Returns:
            List[Dict[str, Any]]: List of session information
        """
        session_list = []
        
        for session_id, session in self.sessions.items():
            # Get process info if available
            process_info = {}
            if session_id in self.subprocess_handlers:
                process_info = self.subprocess_handlers[session_id].get_process_info()
            
            # Get streaming info if available
            streaming_info = {}
            if session_id in self.message_streamers:
                streaming_info = self.message_streamers[session_id].get_streaming_stats()
            
            session_info = {
                "session_id": session.session_id,
                "project_name": session.project_name,
                "project_path": session.project_path,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_active": session_id == self.active_session_id,
                "process_info": process_info,
                "streaming_info": streaming_info
            }
            
            session_list.append(session_info)
        
        # Sort by last activity (most recent first)
        session_list.sort(key=lambda x: x["last_activity"], reverse=True)
        
        return session_list
    
    async def terminate_session(self, session_id: str) -> None:
        """
        Terminate a specific session.
        
        Args:
            session_id: ID of session to terminate
        
        Raises:
            SessionError: If session doesn't exist or termination fails
        """
        if session_id not in self.sessions:
            raise SessionError(f"Session {session_id} not found")
        
        try:
            session = self.sessions[session_id]
            
            # Stop message streaming
            if session_id in self.message_streamers:
                await self.message_streamers[session_id].stop_streaming()
                del self.message_streamers[session_id]
            
            # Terminate subprocess
            if session_id in self.subprocess_handlers:
                await self.subprocess_handlers[session_id].terminate_process()
                del self.subprocess_handlers[session_id]
            
            # Update session status
            session.status = SessionStatus.INACTIVE
            session.process_id = None
            
            # Remove from active session if it was active
            if self.active_session_id == session_id:
                self.active_session_id = None
                
                # Try to switch to another active session
                # Find the most recently active session that is not the one being terminated
                candidate_session_id = None
                latest_activity = datetime.min

                for other_id, other_session in self.sessions.items():
                    if (other_id != session_id and 
                        other_session.status == SessionStatus.ACTIVE and 
                        other_session.last_activity > latest_activity):
                        candidate_session_id = other_id
                        latest_activity = other_session.last_activity
                
                if candidate_session_id:
                    self.active_session_id = candidate_session_id

            # Update session status
            session.status = SessionStatus.INACTIVE
            session.process_id = None

            # Remove session
            del self.sessions[session_id]
            
            self.logger.info(f"Terminated session {session_id}")
            
            # Save sessions
            await self._save_sessions()
        
        except Exception as e:
            raise SessionError(f"Failed to terminate session {session_id}: {str(e)}")
    
    async def get_session_handler(self, session_id: str) -> Optional[SubprocessClaudeHandler]:
        """
        Get the subprocess handler for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Optional[SubprocessClaudeHandler]: Handler or None if not found
        """
        return self.subprocess_handlers.get(session_id)
    
    async def get_session_streamer(self, session_id: str) -> Optional[MessageStreamer]:
        """
        Get the message streamer for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Optional[MessageStreamer]: Streamer or None if not found
        """
        return self.message_streamers.get(session_id)
    
    async def health_check_sessions(self) -> Dict[str, bool]:
        """
        Perform health check on all sessions.
        
        Returns:
            Dict[str, bool]: Session ID to health status mapping
        """
        health_status = {}
        
        for session_id, session in self.sessions.items():
            try:
                # Check subprocess health
                if session_id in self.subprocess_handlers:
                    handler = self.subprocess_handlers[session_id]
                    is_healthy = await handler.health_check()
                    health_status[session_id] = is_healthy
                    
                    # Update session status based on health
                    if not is_healthy and session.status == SessionStatus.ACTIVE:
                        session.status = SessionStatus.ERROR
                        self.logger.warning(f"Session {session_id} marked as unhealthy")
                else:
                    health_status[session_id] = False
            
            except Exception as e:
                self.logger.error(f"Error checking health of session {session_id}: {e}")
                health_status[session_id] = False
        
        return health_status
    
    async def _load_sessions(self) -> None:
        """Load sessions from persistent storage."""
        if not self.sessions_file.exists():
            return
        
        try:
            async with aiofiles.open(self.sessions_file, 'r') as f:
                content = await f.read()
                session_data = json.loads(content)
            
            for session_dict in session_data.get('sessions', []):
                try:
                    # Recreate session object
                    session = ClaudeSession(
                        session_id=session_dict['session_id'],
                        project_path=session_dict['project_path'],
                        project_name=session_dict['project_name'],
                        status=SessionStatus(session_dict['status']),
                        created_at=datetime.fromisoformat(session_dict['created_at']),
                        last_activity=datetime.fromisoformat(session_dict['last_activity'])
                    )
                    
                    # Only load sessions that were recently active
                    time_since_activity = (datetime.now() - session.last_activity).total_seconds()
                    if time_since_activity < self.session_timeout:
                        # Mark as inactive (will need to be restarted)
                        session.status = SessionStatus.INACTIVE
                        self.sessions[session.session_id] = session
                        
                        self.logger.info(f"Loaded session {session.session_id} from storage")
                    else:
                        self.logger.info(f"Skipped expired session {session.session_id}")
                
                except Exception as e:
                    self.logger.error(f"Error loading session: {e}")
            
            # Restore active session
            active_session_id = session_data.get('active_session_id')
            if active_session_id and active_session_id in self.sessions:
                self.active_session_id = active_session_id
        
        except Exception as e:
            self.logger.error(f"Error loading sessions from {self.sessions_file}: {e}")
    
    async def _save_sessions(self) -> None:
        """Save sessions to persistent storage."""
        try:
            session_data = {
                'active_session_id': self.active_session_id,
                'sessions': []
            }
            
            for session in self.sessions.values():
                session_dict = {
                    'session_id': session.session_id,
                    'project_path': session.project_path,
                    'project_name': session.project_name,
                    'status': session.status.value,
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat()
                }
                session_data['sessions'].append(session_dict)
            
            async with aiofiles.open(self.sessions_file, 'w') as f:
                await f.write(json.dumps(session_data, indent=2))
        
        except Exception as e:
            self.logger.error(f"Error saving sessions to {self.sessions_file}: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background task for session cleanup."""
        while self.is_running:
            try:
                # Create a task for each session that will sleep until it times out
                timeout_tasks = []
                for session in self.sessions.values():
                    if session.status in [SessionStatus.INACTIVE, SessionStatus.ERROR]:
                        inactive_time = (datetime.now() - session.last_activity).total_seconds()
                        sleep_time = self.session_timeout - inactive_time
                        if sleep_time > 0:
                            timeout_tasks.append(asyncio.create_task(asyncio.sleep(sleep_time)))

                # Wait for any session to time out, or for 60 seconds
                if timeout_tasks:
                    try:
                        done, pending = await asyncio.wait(timeout_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=60)
                        # Cancel remaining tasks
                        for task in pending:
                            task.cancel()
                        # Wait for cancellation to complete
                        if pending:
                            try:
                                await asyncio.gather(*pending, return_exceptions=True)
                            except Exception as e:
                                self.logger.warning(f"Error during task cancellation: {e}")
                    except Exception as e:
                        self.logger.error(f"Error in session timeout monitoring: {e}")
                        # Cancel all tasks on error
                        for task in timeout_tasks:
                            if not task.done():
                                task.cancel()
                else:
                    await asyncio.sleep(60)

                # Health check all sessions
                await self.health_check_sessions()
                
                # Clean up inactive sessions
                await self._cleanup_inactive_sessions()
                
                # Save session state periodically
                await self._save_sessions()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_inactive_sessions(self) -> None:
        """Clean up sessions that have been inactive for too long."""
        current_time = datetime.now()
        sessions_to_remove = []
        
        for session_id, session in self.sessions.items():
            # Check if session has been inactive for too long
            time_since_activity = (current_time - session.last_activity).total_seconds()
            
            if time_since_activity > self.session_timeout:
                if session.status in [SessionStatus.INACTIVE, SessionStatus.ERROR]:
                    sessions_to_remove.append(session_id)
                    self.logger.info(f"Marking session {session_id} for cleanup (inactive for {time_since_activity}s)")
        
        # Remove inactive sessions
        for session_id in sessions_to_remove:
            try:
                await self.terminate_session(session_id)
            except Exception as e:
                self.logger.error(f"Error cleaning up session {session_id}: {e}")
    
    async def _terminate_all_sessions(self) -> None:
        """Terminate all active sessions."""
        session_ids = list(self.sessions.keys())
        
        for session_id in session_ids:
            try:
                await self.terminate_session(session_id)
            except Exception as e:
                self.logger.error(f"Error terminating session {session_id}: {e}")
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the session manager.
        
        Returns:
            Dict[str, Any]: Manager statistics
        """
        return {
            "is_running": self.is_running,
            "total_sessions": len(self.sessions),
            "active_session_id": self.active_session_id,
            "max_sessions": self.max_sessions,
            "session_timeout": self.session_timeout,
            "sessions_file": str(self.sessions_file),
            "session_statuses": {
                status.value: sum(1 for s in self.sessions.values() if s.status == status)
                for status in SessionStatus
            }
        }
    
    async def execute_non_interactive(self, command: str, project_path: str, 
                                      output_format: str = "text", timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute a command in non-interactive mode using Claude Code CLI.
        
        Args:
            command: Command to execute
            project_path: Project directory path
            output_format: Output format (text, json)
            timeout: Optional timeout
        
        Returns:
            Dict containing command response
        
        Raises:
            SessionError: If execution fails
        """
        try:
            # Create a temporary handler for non-interactive execution
            handler = SubprocessClaudeHandler(self.config.claude)
            handler.output_format = output_format
            
            # Create a minimal session for the project path
            temp_session = ClaudeSession(
                session_id=str(uuid.uuid4()),
                project_path=project_path
            )
            handler.session = temp_session
            
            # Execute command
            result = await handler.execute_command(command, timeout)
            
            self.logger.info(f"Executed non-interactive command in {project_path}")
            return result
            
        except Exception as e:
            raise SessionError(f"Failed to execute command: {str(e)}")
    
    async def continue_claude_session(self, session_id: str) -> ClaudeSession:
        """
        Continue the most recent Claude Code session for a given session.
        
        Args:
            session_id: Session ID to continue
        
        Returns:
            ClaudeSession: The continued session
        
        Raises:
            SessionError: If continuation fails
        """
        if session_id not in self.sessions:
            raise SessionError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        handler = self.subprocess_handlers.get(session_id)
        
        if not handler:
            raise SessionError(f"No handler found for session {session_id}")
        
        try:
            await handler.continue_session()
            session.update_activity()
            
            # Update Claude session ID if changed
            if handler.get_claude_session_id():
                session.claude_session_id = handler.get_claude_session_id()
            
            self.logger.info(f"Continued Claude session {session_id}")
            return session
            
        except Exception as e:
            raise SessionError(f"Failed to continue session: {str(e)}")
    
    def get_claude_session_mapping(self) -> Dict[str, Optional[str]]:
        """
        Get mapping of internal session IDs to Claude Code session IDs.
        
        Returns:
            Dict mapping internal session IDs to Claude session IDs
        """
        mapping = {}
        for session_id, session in self.sessions.items():
            mapping[session_id] = session.claude_session_id
        return mapping