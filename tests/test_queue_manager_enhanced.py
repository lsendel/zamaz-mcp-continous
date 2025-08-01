"""
Enhanced unit tests for queue manager and task processing.

These tests provide comprehensive coverage of task queue operations,
including concurrent processing, error handling, and persistence.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

from claude_remote_client.task_queue.queue_manager import QueueManager
from claude_remote_client.task_queue.cron_scheduler import CronScheduler
from claude_remote_client.config import Config
from claude_remote_client.models import QueuedTask, CronSchedule, TaskStatus
from claude_remote_client.exceptions import QueueError
from tests.test_utilities import TestDataGenerator, MockFactory, AssertionHelpers


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration with temporary directory."""
    return Config(
        data_dir=temp_dir,
        task_queue_size=100,
        max_concurrent_tasks=5
    )


class TestQueueManager:
    """Enhanced tests for QueueManager."""
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, test_config):
        """Test queue manager initialization."""
        manager = QueueManager(test_config)
        
        assert manager.config == test_config
        assert manager.queues == {}
        assert manager.max_queue_size == test_config.task_queue_size
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, test_config):
        """Test queue manager start/stop lifecycle."""
        manager = QueueManager(test_config)
        
        # Initially not running
        assert not manager.is_running
        
        # Start the manager
        await manager.start()
        assert manager.is_running
        
        # Stop the manager
        await manager.stop()
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_add_task_to_queue(self, test_config):
        """Test adding tasks to queue."""
        manager = QueueManager(test_config)
        await manager.start()
        
        task = QueuedTask(
            queue_name="test-queue",
            description="Test task",
            command="echo 'hello'",
            project_path="/test/project"
        )
        
        task_id = await manager.add_task(task)
        
        assert task_id == task.task_id
        assert "test-queue" in manager.queues
        assert len(manager.queues["test-queue"]) == 1
        assert manager.queues["test-queue"][0] == task
    
    @pytest.mark.asyncio
    async def test_add_task_queue_size_limit(self, test_config):
        """Test queue size limit enforcement."""
        test_config.task_queue_size = 2
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks up to limit
        for i in range(2):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
        
        # Adding one more should fail
        overflow_task = QueuedTask(queue_name="test-queue", description="Overflow task")
        with pytest.raises(QueueError, match="Queue size limit exceeded"):
            await manager.add_task(overflow_task)
    
    @pytest.mark.asyncio
    async def test_get_queue_tasks(self, test_config):
        """Test retrieving tasks from queue."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add multiple tasks
        tasks = []
        for i in range(3):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
            tasks.append(task)
        
        # Get queue tasks
        queue_tasks = await manager.get_queue("test-queue")
        
        assert len(queue_tasks) == 3
        for i, task in enumerate(queue_tasks):
            assert task.description == f"Task {i}"
    
    @pytest.mark.asyncio
    async def test_process_queue_sequential(self, test_config):
        """Test sequential queue processing."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks
        tasks = []
        for i in range(3):
            task = QueuedTask(
                queue_name="test-queue",
                description=f"Task {i}",
                command=f"echo 'Task {i}'"
            )
            await manager.add_task(task)
            tasks.append(task)
        
        # Mock task execution
        with patch.object(manager, 'execute_task') as mock_execute:
            mock_execute.return_value = AsyncMock(return_value="Task completed")
            
            # Process queue
            results = []
            async for result in manager.process_queue("test-queue"):
                results.append(result)
            
            assert len(results) == 3
            assert mock_execute.call_count == 3
            
            # Verify tasks were processed in order
            for i, result in enumerate(results):
                assert result.task.description == f"Task {i}"
                assert result.status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_process_queue_with_failures(self, test_config):
        """Test queue processing with task failures."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks
        for i in range(3):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
        
        # Mock task execution with failures
        with patch.object(manager, 'execute_task') as mock_execute:
            # First task succeeds, second fails, third succeeds
            mock_execute.side_effect = [
                AsyncMock(return_value="Success"),
                Exception("Task failed"),
                AsyncMock(return_value="Success")
            ]
            
            results = []
            async for result in manager.process_queue("test-queue"):
                results.append(result)
            
            assert len(results) == 3
            assert results[0].status == TaskStatus.COMPLETED
            assert results[1].status == TaskStatus.FAILED
            assert results[2].status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_concurrent_queue_processing(self, test_config):
        """Test concurrent processing of multiple queues."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks to different queues
        for queue_name in ["queue1", "queue2", "queue3"]:
            for i in range(2):
                task = QueuedTask(queue_name=queue_name, description=f"Task {i}")
                await manager.add_task(task)
        
        # Mock task execution
        with patch.object(manager, 'execute_task') as mock_execute:
            mock_execute.return_value = AsyncMock(return_value="Completed")
            
            # Process queues concurrently
            tasks = [
                manager.process_queue("queue1"),
                manager.process_queue("queue2"),
                manager.process_queue("queue3")
            ]
            
            # Collect all results
            all_results = []
            for queue_processor in tasks:
                queue_results = []
                async for result in queue_processor:
                    queue_results.append(result)
                all_results.append(queue_results)
            
            # Verify all tasks processed
            assert len(all_results) == 3
            for queue_results in all_results:
                assert len(queue_results) == 2
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, test_config):
        """Test clearing queue."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks
        for i in range(3):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
        
        # Verify tasks added
        assert len(manager.queues["test-queue"]) == 3
        
        # Clear queue
        await manager.clear_queue("test-queue")
        
        # Verify queue cleared
        assert len(manager.queues["test-queue"]) == 0
    
    @pytest.mark.asyncio
    async def test_queue_persistence(self, test_config):
        """Test queue state persistence."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks
        tasks = []
        for i in range(3):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
            tasks.append(task)
        
        # Save queue state
        await manager.save_queue_state("test-queue")
        
        # Verify state file exists
        state_file = Path(test_config.data_dir) / "queues" / "test-queue.json"
        assert state_file.exists()
        
        # Load state and verify
        loaded_tasks = await manager.load_queue_state("test-queue")
        assert len(loaded_tasks) == 3
        for i, task in enumerate(loaded_tasks):
            assert task.description == f"Task {i}"
    
    @pytest.mark.asyncio
    async def test_task_retry_logic(self, test_config):
        """Test task retry logic."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add task with retry capability
        task = QueuedTask(
            queue_name="test-queue",
            description="Failing task",
            max_retries=2
        )
        await manager.add_task(task)
        
        # Mock task execution to fail initially, then succeed
        with patch.object(manager, 'execute_task') as mock_execute:
            mock_execute.side_effect = [
                Exception("First failure"),
                Exception("Second failure"),
                AsyncMock(return_value="Success on retry")
            ]
            
            results = []
            async for result in manager.process_queue("test-queue"):
                results.append(result)
            
            # Should have retried and eventually succeeded
            assert len(results) == 1
            assert results[0].status == TaskStatus.COMPLETED
            assert results[0].task.retry_count == 2
    
    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, test_config):
        """Test priority-based queue ordering."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks with different priorities
        priorities = [1, 5, 3, 2, 4]
        for i, priority in enumerate(priorities):
            task = QueuedTask(
                queue_name="test-queue",
                description=f"Task {i}",
                priority=priority
            )
            await manager.add_task(task)
        
        # Get queue and verify ordering (higher priority first)
        queue_tasks = await manager.get_queue("test-queue")
        
        # Should be ordered by priority (descending)
        expected_order = [5, 4, 3, 2, 1]
        actual_priorities = [task.priority for task in queue_tasks]
        assert actual_priorities == expected_order


class TestCronScheduler:
    """Enhanced tests for CronScheduler."""
    
    @pytest.mark.asyncio
    async def test_scheduler_initialization(self, test_config):
        """Test cron scheduler initialization."""
        scheduler = CronScheduler(test_config)
        
        assert scheduler.config == test_config
        assert scheduler.schedules == {}
        assert not scheduler.is_running
    
    @pytest.mark.asyncio
    async def test_add_cron_schedule(self, test_config):
        """Test adding cron schedule."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(
            name="daily-cleanup",
            cron_pattern="0 2 * * *",
            tasks=["clean_code", "run_tests"],
            project_path="/test/project"
        )
        
        await scheduler.add_schedule(schedule)
        
        assert schedule.schedule_id in scheduler.schedules
        assert scheduler.schedules[schedule.schedule_id] == schedule
    
    @pytest.mark.asyncio
    async def test_remove_cron_schedule(self, test_config):
        """Test removing cron schedule."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(name="test-schedule", cron_pattern="0 * * * *")
        await scheduler.add_schedule(schedule)
        
        # Verify schedule added
        assert schedule.schedule_id in scheduler.schedules
        
        # Remove schedule
        await scheduler.remove_schedule(schedule.schedule_id)
        
        # Verify schedule removed
        assert schedule.schedule_id not in scheduler.schedules
    
    @pytest.mark.asyncio
    async def test_check_due_schedules(self, test_config):
        """Test checking for due schedules."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        # Create schedule that should run now
        past_schedule = CronSchedule(
            name="past-schedule",
            cron_pattern="0 * * * *",
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        # Create schedule that should not run yet
        future_schedule = CronSchedule(
            name="future-schedule",
            cron_pattern="0 * * * *",
            next_run=datetime.now() + timedelta(hours=1)
        )
        
        await scheduler.add_schedule(past_schedule)
        await scheduler.add_schedule(future_schedule)
        
        # Check due schedules
        due_schedules = await scheduler.get_due_schedules()
        
        assert len(due_schedules) == 1
        assert due_schedules[0].name == "past-schedule"
    
    @pytest.mark.asyncio
    async def test_execute_scheduled_tasks(self, test_config):
        """Test execution of scheduled tasks."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(
            name="test-schedule",
            cron_pattern="0 * * * *",
            tasks=["clean_code", "run_tests"],
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        await scheduler.add_schedule(schedule)
        
        # Mock task execution
        with patch.object(scheduler, 'execute_predefined_task') as mock_execute:
            mock_execute.return_value = AsyncMock(return_value="Task completed")
            
            # Execute due schedules
            await scheduler.execute_due_schedules()
            
            # Should have executed both tasks
            assert mock_execute.call_count == 2
            mock_execute.assert_any_call("clean_code", schedule.project_path)
            mock_execute.assert_any_call("run_tests", schedule.project_path)
    
    @pytest.mark.asyncio
    async def test_schedule_persistence(self, test_config):
        """Test schedule persistence."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(
            name="persistent-schedule",
            cron_pattern="0 2 * * *",
            tasks=["daily_task"]
        )
        
        await scheduler.add_schedule(schedule)
        
        # Save schedules
        await scheduler.save_schedules()
        
        # Verify state file exists
        state_file = Path(test_config.data_dir) / "schedules.json"
        assert state_file.exists()
        
        # Load schedules and verify
        await scheduler.load_schedules()
        assert schedule.schedule_id in scheduler.schedules
    
    @pytest.mark.asyncio
    async def test_disabled_schedule_not_executed(self, test_config):
        """Test that disabled schedules are not executed."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(
            name="disabled-schedule",
            cron_pattern="0 * * * *",
            tasks=["test_task"],
            enabled=False,
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        await scheduler.add_schedule(schedule)
        
        # Check due schedules
        due_schedules = await scheduler.get_due_schedules()
        
        # Should not include disabled schedule
        assert len(due_schedules) == 0
    
    @pytest.mark.asyncio
    async def test_schedule_execution_updates_next_run(self, test_config):
        """Test that schedule execution updates next run time."""
        scheduler = CronScheduler(test_config)
        await scheduler.start()
        
        schedule = CronSchedule(
            name="test-schedule",
            cron_pattern="0 */2 * * *",  # Every 2 hours
            tasks=["test_task"],
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        original_next_run = schedule.next_run
        await scheduler.add_schedule(schedule)
        
        # Mock task execution
        with patch.object(scheduler, 'execute_predefined_task') as mock_execute:
            mock_execute.return_value = AsyncMock(return_value="Completed")
            
            # Execute due schedules
            await scheduler.execute_due_schedules()
            
            # Next run should be updated
            assert schedule.next_run > original_next_run
            assert schedule.run_count == 1
            AssertionHelpers.assert_datetime_recent(schedule.last_run)


class TestTaskQueueIntegration:
    """Integration tests for task queue components."""
    
    @pytest.mark.asyncio
    async def test_queue_and_cron_integration(self, test_config):
        """Test integration between queue manager and cron scheduler."""
        queue_manager = QueueManager(test_config)
        cron_scheduler = CronScheduler(test_config)
        
        await queue_manager.start()
        await cron_scheduler.start()
        
        # Create cron schedule that adds tasks to queue
        schedule = CronSchedule(
            name="queue-feeder",
            cron_pattern="0 * * * *",
            tasks=["add_to_queue"],
            next_run=datetime.now() - timedelta(minutes=1)
        )
        
        await cron_scheduler.add_schedule(schedule)
        
        # Mock the predefined task to add to queue
        async def mock_add_to_queue(task_name, project_path):
            task = QueuedTask(
                queue_name="cron-queue",
                description=f"Task from cron: {task_name}",
                project_path=project_path
            )
            await queue_manager.add_task(task)
            return "Task added to queue"
        
        with patch.object(cron_scheduler, 'execute_predefined_task', mock_add_to_queue):
            # Execute cron schedules
            await cron_scheduler.execute_due_schedules()
            
            # Verify task was added to queue
            queue_tasks = await queue_manager.get_queue("cron-queue")
            assert len(queue_tasks) == 1
            assert "Task from cron" in queue_tasks[0].description
    
    @pytest.mark.asyncio
    async def test_high_volume_task_processing(self, test_config):
        """Test processing high volume of tasks."""
        test_config.task_queue_size = 1000
        manager = QueueManager(test_config)
        await manager.start()
        
        # Generate large number of tasks
        tasks = TestDataGenerator.generate_task_queue(size=100)
        
        # Add all tasks
        for task in tasks:
            await manager.add_task(task)
        
        # Mock fast task execution
        with patch.object(manager, 'execute_task') as mock_execute:
            mock_execute.return_value = AsyncMock(return_value="Completed")
            
            # Process queue
            results = []
            async for result in manager.process_queue("test-queue"):
                results.append(result)
            
            # Verify all tasks processed
            assert len(results) == 100
            assert all(r.status == TaskStatus.COMPLETED for r in results)
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_queue_processing(self, test_config):
        """Test error recovery during queue processing."""
        manager = QueueManager(test_config)
        await manager.start()
        
        # Add tasks
        for i in range(5):
            task = QueuedTask(queue_name="test-queue", description=f"Task {i}")
            await manager.add_task(task)
        
        # Mock execution with intermittent failures
        execution_results = [
            AsyncMock(return_value="Success"),
            Exception("Network error"),
            AsyncMock(return_value="Success"),
            Exception("Timeout"),
            AsyncMock(return_value="Success")
        ]
        
        with patch.object(manager, 'execute_task', side_effect=execution_results):
            results = []
            async for result in manager.process_queue("test-queue"):
                results.append(result)
            
            # Should have processed all tasks despite failures
            assert len(results) == 5
            
            # Check success/failure distribution
            successful = [r for r in results if r.status == TaskStatus.COMPLETED]
            failed = [r for r in results if r.status == TaskStatus.FAILED]
            
            assert len(successful) == 3
            assert len(failed) == 2