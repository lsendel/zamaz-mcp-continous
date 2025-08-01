"""
Core data models for the Claude Remote Client.

This module defines the primary data structures used throughout the application
for managing sessions, tasks, schedules, and messages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid
from croniter import croniter

class TaskStatus(Enum):
    """Status enumeration for tasks and sessions."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionStatus(Enum):
    """Status enumeration for Claude sessions."""
    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ClaudeSession:
    """
    Represents an active Claude CLI session with project context.
    
    Manages the state and metadata for a Claude session including conversation
    history, project context, and process information.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: str = ""
    project_name: str = ""
    status: SessionStatus = SessionStatus.INACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    process_id: Optional[int] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    claude_session_id: Optional[str] = None  # Claude Code's internal session ID
    
    def __post_init__(self):
        """Post-initialization to set project name from path."""
        if self.project_path and not self.project_name:
            self.project_name = self.project_path.split('/')[-1]
    
    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()
    
    def add_message(self, role: str, content: str, timestamp: Optional[datetime] = None):
        """Add a message to the conversation history."""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": timestamp.isoformat()
        })
        self.update_activity()
    
    def is_active(self) -> bool:
        """Check if the session is currently active."""
        return self.status == SessionStatus.ACTIVE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "project_name": self.project_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "process_id": self.process_id,
            "conversation_history": self.conversation_history,
            "claude_session_id": self.claude_session_id
        }


@dataclass
class QueuedTask:
    """
    Represents a task in the execution queue.
    
    Contains task metadata, execution parameters, and status tracking
    for automated task processing.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = "default"
    description: str = ""
    command: str = ""
    project_path: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # Higher numbers = higher priority
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def start_execution(self):
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
    
    def complete_execution(self, result: str):
        """Mark task as completed with result."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result
    
    def fail_execution(self, error_message: str):
        """Mark task as failed with error message."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.retry_count += 1
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "queue_name": self.queue_name,
            "description": self.description,
            "command": self.command,
            "project_path": self.project_path,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }


@dataclass
class CronSchedule:
    """
    Represents a cron-based scheduled task.
    
    Manages cron pattern parsing, next execution calculation,
    and scheduled task metadata.
    """
    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cron_pattern: str = ""  # e.g., "0 */2 * * *" (every 2 hours)
    tasks: List[str] = field(default_factory=list)  # List of predefined task names
    project_path: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    
    def __post_init__(self):
        """Post-initialization to calculate next run time."""
        if self.cron_pattern and not self.next_run:
            self.calculate_next_run()
    
    def calculate_next_run(self):
        """Calculate the next execution time based on cron pattern."""
        if not self.cron_pattern or not croniter.is_valid(self.cron_pattern):
            self.next_run = None
            return
        
        now = datetime.now()
        iterator = croniter(self.cron_pattern, now)
        self.next_run = iterator.get_next(datetime)
    
    def should_run(self) -> bool:
        """Check if the schedule should run now."""
        if not self.enabled or not self.next_run:
            return False
        return datetime.now() >= self.next_run
    
    def mark_executed(self):
        """Mark the schedule as executed and calculate next run."""
        self.last_run = datetime.now()
        self.run_count += 1
        self.calculate_next_run()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary for serialization."""
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "cron_pattern": self.cron_pattern,
            "tasks": self.tasks,
            "project_path": self.project_path,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count
        }


@dataclass
class SlackMessage:
    """
    Represents a Slack message with metadata.
    
    Contains message content, channel information, and formatting
    utilities for Slack-specific features.
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str = ""
    user_id: str = ""
    text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    thread_ts: Optional[str] = None
    is_bot_message: bool = False
    is_command: bool = False
    
    def __post_init__(self):
        """Post-initialization to detect command messages."""
        self.is_command = self.text.strip().startswith('@@')
    
    def get_command(self) -> Optional[str]:
        """Extract command from message text if it's a command."""
        if not self.is_command:
            return None
        
        parts = self.text.strip().split()
        if parts:
            return parts[0][2:]  # Remove @@ prefix
        return None
    
    def get_command_args(self) -> List[str]:
        """Extract command arguments from message text."""
        if not self.is_command:
            return []
        
        parts = self.text.strip().split()
        return parts[1:] if len(parts) > 1 else []
    
    def format_code_block(self, code: str, language: str = "") -> str:
        """Format code as Slack code block."""
        return f"```{language}\n{code}\n```"
    
    def format_inline_code(self, code: str) -> str:
        """Format code as inline Slack code."""
        return f"`{code}`"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "thread_ts": self.thread_ts,
            "is_bot_message": self.is_bot_message,
            "is_command": self.is_command
        }