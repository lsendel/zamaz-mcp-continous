"""
Unit tests for queue manager.
"""

import pytest
import asyncio
import tempfile
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from claude_remote_client.task_queue.queue_manager import QueueManager
from claude_remote_client.config import Config, ClaudeConfig, SlackConfig
from claude_remote_client.models import QueuedTask, TaskStatus
from claude_remote_client.exceptions import TaskQueueError


@pytest.fixture
def temp_config():
    """Create a test configuration with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            data_dir=temp_dir,
            task_queue_size=10,
            claude=ClaudeConfig(),
            slack=SlackConfig()
        )
        yield config


@pytest.fixture
def queue_manager(temp_config):
    """Create a queue manager with test configuration."""
    return QueueManager(temp_config)


class TestQueueManager:
    """Test cases for QueueManager."""
    
    def test_manager_initialization(self, temp_config):
        """Test queue manager initialization."""
        manager = QueueManager(temp_config)
        
        assert manager.config == temp_config
        assert manager.queues == {}
        assert manager.executing_tasks == {}
        assert manager.is_running is False
        assert manager.max_concurrent_tasks == 3
        assert manager.claude_execution_callback is None
        assert manager.slack_notification_callback is None
    
    @pytest.mark.asyncio
    async def test_start_stop_manager(self, queue_manager):
        """Test starting and stopping the queue manager."""
        # Start manager
        await queue_manager.start()
        
        assert queue_manager.is_running is True
        assert queue_manager.execution_task is not None
        
        # Stop manager
        await queue_manager.stop()
        
        assert queue_manager.is_running is False
    
    def test_set_callbacks(self, queue_manager):
        """Test setting callbacks."""
        claude_callback = AsyncMock()
        slack_callback = AsyncMock()
        
        queue_manager.set_claude_callback(claude_callback)
        queue_manager.set_slack_callback(slack_callback)
        
        assert queue_manager.claude_execution_callback == claude_callback
        assert queue_manager.slack_notification_callback == slack_callback
    
    @pytest.mark.asyncio
    async def test_add_task(self, queue_manager):
        """Test adding a task to queue."""
        # Set up Slack callback
        slack_callback = AsyncMock()
        queue_manager.set_slack_callback(slack_callback)
        
        # Add task
        task_id = await queue_manager.add_task(
            queue_name="test-queue",
            description="Test task",
            command="echo 'hello'",
            project_path="/test/path",
            priority=1
        )
        
        # Verify task was added
        assert isinstance(task_id, str)
        assert "test-queue" in queue_manager.queues
        assert len(queue_manager.queues["test-queue"]) == 1
        
        task = queue_manager.queues["test-queue"][0]
        assert task.task_id == task_id
        assert task.description == "Test task"
        assert task.command == "echo 'hello'"
        assert task.priority == 1
        assert task.status == TaskStatus.PENDING
        
        # Verify Slack notification was sent
        slack_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_task_queue_full(self, queue_manager):
        """Test adding task when queue is full."""
        # Set small queue size
        queue_manager.config.task_queue_size = 1
        
        # Add first task
        await queue_manager.add_task("test-queue", "Task 1")
        
        # Try to add second task (should fail)
        with pytest.raises(TaskQueueError) as exc_info:
            await queue_manager.add_task("test-queue", "Task 2")
        
        assert "is full" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_queue_no_callback(self, queue_manager):
        """Test processing queue without Claude callback."""
        # Add task
        await queue_manager.add_task("test-queue", "Test task")
        
        # Try to process without callback
        with pytest.raises(TaskQueueError) as exc_info:
            async for result in queue_manager.process_queue("test-queue"):
                pass
        
        assert "callback not configured" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_queue_success(self, queue_manager):
        """Test successful queue processing."""
        # Set up callbacks
        claude_callback = AsyncMock(return_value="Task completed successfully")
        slack_callback = AsyncMock()
        queue_manager.set_claude_callback(claude_callback)
        queue_manager.set_slack_callback(slack_callback)
        
        # Add tasks
        task_id1 = await queue_manager.add_task("test-queue", "Task 1", priority=1)
        task_id2 = await queue_manager.add_task("test-queue", "Task 2", priority=2)
        
        # Process queue
        results = []
        async for result in queue_manager.process_queue("test-queue"):
            results.append(result)
        
        # Verify results
        assert len(results) == 2
        assert all(r["status"] == "completed" for r in results)
        
        # Higher priority task should be processed first
        assert results[0]["result"] == "Task completed successfully"
        
        # Verify Claude callback was called for each task
        assert claude_callback.call_count == 2
        
        # Verify queue is empty
        assert len(queue_manager.queues["test-queue"]) == 0
    
    @pytest.mark.asyncio
    async def test_process_queue_with_failure(self, queue_manager):
        """Test queue processing with task failure."""
        # Set up callbacks
        claude_callback = AsyncMock(side_effect=Exception("Task failed"))
        slack_callback = AsyncMock()
        queue_manager.set_claude_callback(claude_callback)
        queue_manager.set_slack_callback(slack_callback)
        
        # Add task
        await queue_manager.add_task("test-queue", "Failing task")
        
        # Process queue
        results = []
        async for result in queue_manager.process_queue("test-queue"):
            results.append(result)
        
        # Verify failure result
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "Task failed" in results[0]["error"]
        assert "can_retry" in results[0]
    
    @pytest.mark.asyncio
    async def test_process_queue_not_found(self, queue_manager):
        """Test processing non-existent queue."""
        with pytest.raises(TaskQueueError) as exc_info:
            async for result in queue_manager.process_queue("nonexistent-queue"):
                pass
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_queue_status_specific(self, queue_manager):
        """Test getting status of specific queue."""
        # Add tasks with different statuses
        await queue_manager.add_task("test-queue", "Task 1")
        await queue_manager.add_task("test-queue", "Task 2")
        
        # Manually set one task as failed for testing
        queue_manager.queues["test-queue"][0].status = TaskStatus.FAILED
        
        # Get status
        status = await queue_manager.get_queue_status("test-queue")
        
        assert status["queue_name"] == "test-queue"
        assert status["total_tasks"] == 2
        assert status["pending_tasks"] == 1
        assert status["failed_tasks"] == 1
        assert len(status["tasks"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_queue_status_all(self, queue_manager):
        """Test getting status of all queues."""
        # Add tasks to multiple queues
        await queue_manager.add_task("queue1", "Task 1")
        await queue_manager.add_task("queue2", "Task 2")
        
        # Get status
        status = await queue_manager.get_queue_status()
        
        assert status["total_queues"] == 2
        assert status["executing_tasks"] == 0
        assert "queue1" in status["queues"]
        assert "queue2" in status["queues"]
        assert status["queues"]["queue1"]["total_tasks"] == 1
        assert status["queues"]["queue2"]["total_tasks"] == 1
    
    @pytest.mark.asyncio
    async def test_get_queue_status_not_found(self, queue_manager):
        """Test getting status of non-existent queue."""
        status = await queue_manager.get_queue_status("nonexistent")
        
        assert "error" in status
        assert "not found" in status["error"]
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, queue_manager):
        """Test clearing a queue."""
        # Set up Slack callback
        slack_callback = AsyncMock()
        queue_manager.set_slack_callback(slack_callback)
        
        # Add tasks
        await queue_manager.add_task("test-queue", "Task 1")
        await queue_manager.add_task("test-queue", "Task 2")
        
        # Verify tasks exist
        assert len(queue_manager.queues["test-queue"]) == 2
        
        # Clear queue
        cleared_count = await queue_manager.clear_queue("test-queue")
        
        # Verify queue is empty
        assert cleared_count == 2
        assert len(queue_manager.queues["test-queue"]) == 0
        
        # Verify Slack notification
        slack_callback.assert_called()
    
    @pytest.mark.asyncio
    async def test_clear_queue_not_found(self, queue_manager):
        """Test clearing non-existent queue."""
        with pytest.raises(TaskQueueError) as exc_info:
            await queue_manager.clear_queue("nonexistent")
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_remove_task(self, queue_manager):
        """Test removing a specific task."""
        # Add tasks
        task_id1 = await queue_manager.add_task("test-queue", "Task 1")
        task_id2 = await queue_manager.add_task("test-queue", "Task 2")
        
        # Verify tasks exist
        assert len(queue_manager.queues["test-queue"]) == 2
        
        # Remove one task
        removed = await queue_manager.remove_task(task_id1)
        
        assert removed is True
        assert len(queue_manager.queues["test-queue"]) == 1
        assert queue_manager.queues["test-queue"][0].task_id == task_id2
    
    @pytest.mark.asyncio
    async def test_remove_task_not_found(self, queue_manager):
        """Test removing non-existent task."""
        removed = await queue_manager.remove_task("nonexistent-task-id")
        assert removed is False
    
    @pytest.mark.asyncio
    async def test_get_task(self, queue_manager):
        """Test getting a specific task."""
        # Add task
        task_id = await queue_manager.add_task("test-queue", "Test task")
        
        # Get task
        task = await queue_manager.get_task(task_id)
        
        assert task is not None
        assert task.task_id == task_id
        assert task.description == "Test task"
    
    @pytest.mark.asyncio
    async def test_get_task_not_found(self, queue_manager):
        """Test getting non-existent task."""
        task = await queue_manager.get_task("nonexistent-task-id")
        assert task is None
    
    @pytest.mark.asyncio
    async def test_save_load_queues(self, queue_manager):
        """Test saving and loading queues."""
        # Add tasks
        task_id1 = await queue_manager.add_task("queue1", "Task 1", priority=1)
        task_id2 = await queue_manager.add_task("queue2", "Task 2", priority=2)
        
        # Save queues
        queue_manager._save_queues()
        
        # Verify file exists
        assert queue_manager.queues_file.exists()
        
        # Clear queues and reload
        queue_manager.queues.clear()
        queue_manager._load_queues()
        
        # Verify queues were loaded
        assert len(queue_manager.queues) == 2
        assert "queue1" in queue_manager.queues
        assert "queue2" in queue_manager.queues
        assert len(queue_manager.queues["queue1"]) == 1
        assert len(queue_manager.queues["queue2"]) == 1
        
        # Verify task details
        task1 = queue_manager.queues["queue1"][0]
        task2 = queue_manager.queues["queue2"][0]
        assert task1.task_id == task_id1
        assert task2.task_id == task_id2
        assert task1.description == "Task 1"
        assert task2.description == "Task 2"
    
    def test_get_manager_stats(self, queue_manager):
        """Test getting manager statistics."""
        # Add some tasks
        asyncio.run(queue_manager.add_task("queue1", "Task 1"))
        asyncio.run(queue_manager.add_task("queue2", "Task 2"))
        
        # Set callbacks
        queue_manager.set_claude_callback(AsyncMock())
        queue_manager.set_slack_callback(AsyncMock())
        
        stats = queue_manager.get_manager_stats()
        
        assert stats["is_running"] is False
        assert stats["total_queues"] == 2
        assert stats["total_tasks"] == 2
        assert stats["pending_tasks"] == 2
        assert stats["executing_tasks"] == 0
        assert stats["max_concurrent_tasks"] == 3
        assert stats["claude_callback_configured"] is True
        assert stats["slack_callback_configured"] is True