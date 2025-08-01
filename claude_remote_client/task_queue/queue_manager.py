"""
Task queue manager for handling queued tasks and execution.

This module manages task queues, execution, status tracking,
and integration with Claude for automated task processing.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
from pathlib import Path
import uuid
import aiofiles
import aiofiles.os

from ..models import QueuedTask, TaskStatus
from ..config import Config
from ..exceptions import TaskQueueError
from ..utils import setup_logging, ensure_directory_exists


class QueueManager:
    """
    Manager for task queues with execution and status tracking.
    
    Handles multiple named queues, task execution, progress tracking,
    and integration with Claude sessions for automated processing.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the queue manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = setup_logging()
        
        # Queue storage
        self.queues: Dict[str, List[QueuedTask]] = {}
        self.executing_tasks: Dict[str, QueuedTask] = {}  # task_id -> task
        
        # Queue persistence
        self.queues_file = Path(config.data_dir) / "task_queues.json"
        
        # Execution settings
        self.max_concurrent_tasks = 3
        self.task_timeout = 1800  # 30 minutes
        
        # Background execution
        self.is_running = False
        self.execution_task: Optional[asyncio.Task] = None
        
        # Callbacks for Claude integration
        self.claude_execution_callback = None
        self.slack_notification_callback = None
        
        # Ensure data directory exists
        ensure_directory_exists(config.data_dir)
        
        # Load existing queues
        self._load_queues()
    
    async def start(self) -> None:
        """Start the queue manager and background execution."""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info("Starting queue manager...")
        
        # Start background execution task
        self.execution_task = asyncio.create_task(self._execution_loop())
        
        self.logger.info("Queue manager started")
    
    async def stop(self) -> None:
        """Stop the queue manager and cleanup."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("Stopping queue manager...")
        
        # Cancel background task
        if self.execution_task:
            self.execution_task.cancel()
            try:
                await self.execution_task
            except asyncio.CancelledError:
                pass
        
        # Save queue state
        self._save_queues()
        
        self.logger.info("Queue manager stopped")
    
    def set_claude_callback(self, callback) -> None:
        """
        Set callback for Claude task execution.
        
        Args:
            callback: Async function that takes (task, session_id) and executes with Claude
        """
        self.claude_execution_callback = callback
    
    def set_slack_callback(self, callback) -> None:
        """
        Set callback for Slack notifications.
        
        Args:
            callback: Async function that takes (channel, message) and sends to Slack
        """
        self.slack_notification_callback = callback   
 
    async def add_task(self, queue_name: str, description: str, command: str = "", 
                      project_path: str = "", priority: int = 0) -> str:
        """
        Add a task to a queue.
        
        Args:
            queue_name: Name of the queue to add task to
            description: Task description
            command: Optional command to execute
            project_path: Optional project path for task context
            priority: Task priority (higher = more important)
        
        Returns:
            str: Task ID
        
        Raises:
            TaskQueueError: If task cannot be added
        """
        try:
            # Create task
            task = QueuedTask(
                queue_name=queue_name,
                description=description,
                command=command or description,
                project_path=project_path,
                priority=priority
            )
            
            # Create queue if it doesn't exist
            if queue_name not in self.queues:
                self.queues[queue_name] = []
            
            # Check queue size limit
            if len(self.queues[queue_name]) >= self.config.task_queue_size:
                raise TaskQueueError(f"Queue '{queue_name}' is full (max {self.config.task_queue_size} tasks)")
            
            # Add task to queue (sorted by priority)
            self.queues[queue_name].append(task)
            self.queues[queue_name].sort(key=lambda t: t.priority, reverse=True)
            
            # Save queues
            self._save_queues()
            
            self.logger.info(f"Added task {task.task_id} to queue '{queue_name}': {description}")
            
            # Notify via Slack if callback is set
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"📝 **Task Added to Queue**\n"
                    f"• **Queue:** `{queue_name}`\n"
                    f"• **Task:** {description}\n"
                    f"• **ID:** `{task.task_id}`"
                )
            
            return task.task_id
        
        except Exception as e:
            raise TaskQueueError(f"Failed to add task to queue: {str(e)}")
    
    async def process_queue(self, queue_name: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Process all tasks in a queue iteratively.
        
        Args:
            queue_name: Name of queue to process
        
        Yields:
            Dict[str, Any]: Task execution results
        
        Raises:
            TaskQueueError: If queue processing fails
        """
        if queue_name not in self.queues:
            raise TaskQueueError(f"Queue '{queue_name}' not found")
        
        if not self.claude_execution_callback:
            raise TaskQueueError("Claude execution callback not configured")
        
        queue = self.queues[queue_name]
        
        # Notify start of processing
        if self.slack_notification_callback:
            await self.slack_notification_callback(
                "general",
                f"⚡ **Starting Queue Processing**\n"
                f"• **Queue:** `{queue_name}`\n"
                f"• **Tasks:** {len(queue)} pending"
            )
        
        try:
            while queue:
                # Get next task (highest priority first)
                task = queue.pop(0)
                
                # Execute task
                result = await self._execute_task(task)
                
                yield result
                
                # Save queue state after each task
                self._save_queues()
        
        except Exception as e:
            raise TaskQueueError(f"Error processing queue '{queue_name}': {str(e)}")
        
        finally:
            # Notify completion
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"✅ **Queue Processing Complete**\n"
                    f"• **Queue:** `{queue_name}`\n"
                    f"• **Remaining:** {len(queue)} tasks"
                )  
  
    async def get_queue_status(self, queue_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of queues.
        
        Args:
            queue_name: Optional specific queue name, or None for all queues
        
        Returns:
            Dict[str, Any]: Queue status information
        """
        if queue_name:
            if queue_name not in self.queues:
                return {"error": f"Queue '{queue_name}' not found"}
            
            queue = self.queues[queue_name]
            return {
                "queue_name": queue_name,
                "total_tasks": len(queue),
                "pending_tasks": len([t for t in queue if t.status == TaskStatus.PENDING]),
                "failed_tasks": len([t for t in queue if t.status == TaskStatus.FAILED]),
                "tasks": [self._task_to_dict(task) for task in queue]
            }
        else:
            # All queues
            status = {
                "total_queues": len(self.queues),
                "executing_tasks": len(self.executing_tasks),
                "queues": {}
            }
            
            for name, queue in self.queues.items():
                status["queues"][name] = {
                    "total_tasks": len(queue),
                    "pending_tasks": len([t for t in queue if t.status == TaskStatus.PENDING]),
                    "failed_tasks": len([t for t in queue if t.status == TaskStatus.FAILED])
                }
            
            return status
    
    async def clear_queue(self, queue_name: str) -> int:
        """
        Clear all tasks from a queue.
        
        Args:
            queue_name: Name of queue to clear
        
        Returns:
            int: Number of tasks cleared
        
        Raises:
            TaskQueueError: If queue doesn't exist
        """
        if queue_name not in self.queues:
            raise TaskQueueError(f"Queue '{queue_name}' not found")
        
        task_count = len(self.queues[queue_name])
        self.queues[queue_name].clear()
        
        # Save queues
        self._save_queues()
        
        self.logger.info(f"Cleared {task_count} tasks from queue '{queue_name}'")
        
        # Notify via Slack
        if self.slack_notification_callback:
            await self.slack_notification_callback(
                "general",
                f"🗑️ **Queue Cleared**\n"
                f"• **Queue:** `{queue_name}`\n"
                f"• **Tasks Removed:** {task_count}"
            )
        
        return task_count
    
    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a specific task from its queue.
        
        Args:
            task_id: ID of task to remove
        
        Returns:
            bool: True if task was removed, False if not found
        """
        for queue_name, queue in self.queues.items():
            for i, task in enumerate(queue):
                if task.task_id == task_id:
                    removed_task = queue.pop(i)
                    self._save_queues()
                    
                    self.logger.info(f"Removed task {task_id} from queue '{queue_name}'")
                    return True
        
        return False
    
    async def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """
        Get a specific task by ID.
        
        Args:
            task_id: Task ID to search for
        
        Returns:
            Optional[QueuedTask]: Task if found, None otherwise
        """
        # Check executing tasks first
        if task_id in self.executing_tasks:
            return self.executing_tasks[task_id]
        
        # Check all queues
        for queue in self.queues.values():
            for task in queue:
                if task.task_id == task_id:
                    return task
        
        return None  
  
    async def _execute_task(self, task: QueuedTask) -> Dict[str, Any]:
        """
        Execute a single task.
        
        Args:
            task: Task to execute
        
        Returns:
            Dict[str, Any]: Execution result
        """
        try:
            # Mark task as running
            task.start_execution()
            self.executing_tasks[task.task_id] = task
            
            self.logger.info(f"Executing task {task.task_id}: {task.description}")
            
            # Notify start
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"⚡ **Task Started**\n"
                    f"• **ID:** `{task.task_id}`\n"
                    f"• **Description:** {task.description}\n"
                    f"• **Queue:** `{task.queue_name}`"
                )
            
            # Execute with Claude
            result = await self.claude_execution_callback(task)
            
            # Mark as completed
            task.complete_execution(str(result))
            
            # Remove from executing tasks
            if task.task_id in self.executing_tasks:
                del self.executing_tasks[task.task_id]
            
            self.logger.info(f"Task {task.task_id} completed successfully")
            
            # Notify completion
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"✅ **Task Completed**\n"
                    f"• **ID:** `{task.task_id}`\n"
                    f"• **Description:** {task.description}\n"
                    f"• **Result:** {str(result)[:200]}..."
                )
            
            return {
                "task_id": task.task_id,
                "status": "completed",
                "result": result,
                "execution_time": (task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else 0
            }
        
        except Exception as e:
            # Mark as failed
            task.fail_execution(str(e))
            
            # Remove from executing tasks
            if task.task_id in self.executing_tasks:
                del self.executing_tasks[task.task_id]
            
            self.logger.error(f"Task {task.task_id} failed: {e}")
            
            # Notify failure
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"❌ **Task Failed**\n"
                    f"• **ID:** `{task.task_id}`\n"
                    f"• **Description:** {task.description}\n"
                    f"• **Error:** {str(e)[:200]}..."
                )
            
            return {
                "task_id": task.task_id,
                "status": "failed",
                "error": str(e),
                "can_retry": task.can_retry()
            }
    
    async def _execution_loop(self) -> None:
        """Background task execution loop."""
        while self.is_running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                # Process any pending tasks if we have capacity
                if len(self.executing_tasks) < self.max_concurrent_tasks:
                    await self._process_pending_tasks()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in execution loop: {e}")
    
    async def _process_pending_tasks(self) -> None:
        """Process pending tasks from all queues."""
        # Collect all pending tasks across queues
        pending_tasks = []
        
        for queue_name, queue in self.queues.items():
            for task in queue:
                if task.status == TaskStatus.PENDING:
                    pending_tasks.append(task)
        
        # Sort by priority
        pending_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        # Execute tasks up to capacity
        tasks_to_execute = pending_tasks[:self.max_concurrent_tasks - len(self.executing_tasks)]
        
        for task in tasks_to_execute:
            if self.claude_execution_callback:
                # Remove from queue and execute
                self.queues[task.queue_name].remove(task)
                asyncio.create_task(self._execute_task(task))
    
    def _task_to_dict(self, task: QueuedTask) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return task.to_dict()
    
    async def _load_queues(self) -> None:
        """Load queues from persistent storage."""
        if not await aiofiles.os.path.exists(self.queues_file):
            return
        
        try:
            async with aiofiles.open(self.queues_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)
            
            for queue_name, tasks_data in data.get('queues', {}).items():
                self.queues[queue_name] = []
                
                for task_data in tasks_data:
                    task = QueuedTask(
                        task_id=task_data['task_id'],
                        queue_name=task_data['queue_name'],
                        description=task_data['description'],
                        command=task_data['command'],
                        project_path=task_data['project_path'],
                        status=TaskStatus(task_data['status']),
                        priority=task_data['priority'],
                        created_at=datetime.fromisoformat(task_data['created_at']),
                        retry_count=task_data.get('retry_count', 0),
                        max_retries=task_data.get('max_retries', 3)
                    )
                    
                    # Restore timestamps if available
                    if task_data.get('started_at'):
                        task.started_at = datetime.fromisoformat(task_data['started_at'])
                    if task_data.get('completed_at'):
                        task.completed_at = datetime.fromisoformat(task_data['completed_at'])
                    
                    task.result = task_data.get('result')
                    task.error_message = task_data.get('error_message')
                    
                    self.queues[queue_name].append(task)
            
            self.logger.info(f"Loaded {len(self.queues)} queues from storage")
        
        except Exception as e:
            self.logger.error(f"Error loading queues: {e}")
    
    async def _save_queues(self) -> None:
        """Save queues to persistent storage."""
        try:
            data = {
                'queues': {},
                'last_updated': datetime.now().isoformat()
            }
            
            for queue_name, queue in self.queues.items():
                data['queues'][queue_name] = [
                    self._task_to_dict(task) for task in queue
                ]
            
            async with aiofiles.open(self.queues_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        
        except Exception as e:
            self.logger.error(f"Error saving queues: {e}")
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the queue manager.
        
        Returns:
            Dict[str, Any]: Manager statistics
        """
        total_tasks = sum(len(queue) for queue in self.queues.values())
        pending_tasks = sum(
            len([t for t in queue if t.status == TaskStatus.PENDING])
            for queue in self.queues.values()
        )
        
        return {
            "is_running": self.is_running,
            "total_queues": len(self.queues),
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "executing_tasks": len(self.executing_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "task_timeout": self.task_timeout,
            "queues_file": str(self.queues_file),
            "claude_callback_configured": self.claude_execution_callback is not None,
            "slack_callback_configured": self.slack_notification_callback is not None
        }