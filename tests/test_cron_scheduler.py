"""
Unit tests for cron scheduler.
"""

import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from claude_remote_client.task_queue.cron_scheduler import CronScheduler
from claude_remote_client.config import Config, ClaudeConfig, SlackConfig
from claude_remote_client.models import CronSchedule
from claude_remote_client.exceptions import CronScheduleError


@pytest.fixture
def temp_config():
    """Create a test configuration with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            data_dir=temp_dir,
            claude=ClaudeConfig(),
            slack=SlackConfig()
        )
        yield config


@pytest.fixture
def cron_scheduler(temp_config):
    """Create a cron scheduler with test configuration."""
    return CronScheduler(temp_config)


class TestCronScheduler:
    """Test cases for CronScheduler."""
    
    def test_scheduler_initialization(self, temp_config):
        """Test cron scheduler initialization."""
        scheduler = CronScheduler(temp_config)
        
        assert scheduler.config == temp_config
        assert scheduler.schedules == {}
        assert scheduler.is_running is False
        assert len(scheduler.predefined_tasks) > 0
        assert "clean_code" in scheduler.predefined_tasks
        assert "run_tests" in scheduler.predefined_tasks
        assert scheduler.task_execution_callback is None
        assert scheduler.slack_notification_callback is None
    
    @pytest.mark.asyncio
    async def test_start_stop_scheduler(self, cron_scheduler):
        """Test starting and stopping the scheduler."""
        # Start scheduler
        await cron_scheduler.start()
        
        assert cron_scheduler.is_running is True
        assert cron_scheduler.scheduler_task is not None
        
        # Stop scheduler
        await cron_scheduler.stop()
        
        assert cron_scheduler.is_running is False
    
    def test_set_callbacks(self, cron_scheduler):
        """Test setting callbacks."""
        task_callback = AsyncMock()
        slack_callback = AsyncMock()
        
        cron_scheduler.set_task_callback(task_callback)
        cron_scheduler.set_slack_callback(slack_callback)
        
        assert cron_scheduler.task_execution_callback == task_callback
        assert cron_scheduler.slack_notification_callback == slack_callback
    
    @pytest.mark.asyncio
    async def test_add_schedule_success(self, cron_scheduler):
        """Test successfully adding a cron schedule."""
        # Set up Slack callback
        slack_callback = AsyncMock()
        cron_scheduler.set_slack_callback(slack_callback)
        
        # Add schedule
        schedule_id = await cron_scheduler.add_schedule(
            name="test-schedule",
            cron_pattern="0 */2 * * *",
            tasks=["clean_code", "run_tests"],
            project_path="/test/path"
        )
        
        # Verify schedule was added
        assert isinstance(schedule_id, str)
        assert schedule_id in cron_scheduler.schedules
        
        schedule = cron_scheduler.schedules[schedule_id]
        assert schedule.name == "test-schedule"
        assert schedule.cron_pattern == "0 */2 * * *"
        assert schedule.tasks == ["clean_code", "run_tests"]
        assert schedule.project_path == "/test/path"
        assert schedule.enabled is True
        
        # Verify Slack notification was sent
        slack_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_schedule_invalid_pattern(self, cron_scheduler):
        """Test adding schedule with invalid cron pattern."""
        with pytest.raises(CronScheduleError) as exc_info:
            await cron_scheduler.add_schedule(
                name="invalid-schedule",
                cron_pattern="invalid pattern",
                tasks=["clean_code"]
            )
        
        assert "Invalid cron pattern" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_schedule_invalid_tasks(self, cron_scheduler):
        """Test adding schedule with invalid tasks."""
        with pytest.raises(CronScheduleError) as exc_info:
            await cron_scheduler.add_schedule(
                name="invalid-tasks",
                cron_pattern="0 */2 * * *",
                tasks=["invalid_task", "another_invalid"]
            )
        
        assert "Invalid tasks" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_remove_schedule(self, cron_scheduler):
        """Test removing a cron schedule."""
        # Set up Slack callback
        slack_callback = AsyncMock()
        cron_scheduler.set_slack_callback(slack_callback)
        
        # Add schedule first
        schedule_id = await cron_scheduler.add_schedule(
            name="removable-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        
        # Verify it exists
        assert schedule_id in cron_scheduler.schedules
        
        # Remove schedule
        removed = await cron_scheduler.remove_schedule(schedule_id)
        
        assert removed is True
        assert schedule_id not in cron_scheduler.schedules
        
        # Verify Slack notification was sent (add + remove = 2 calls)
        assert slack_callback.call_count == 2
    
    @pytest.mark.asyncio
    async def test_remove_schedule_not_found(self, cron_scheduler):
        """Test removing non-existent schedule."""
        removed = await cron_scheduler.remove_schedule("nonexistent-id")
        assert removed is False
    
    @pytest.mark.asyncio
    async def test_enable_disable_schedule(self, cron_scheduler):
        """Test enabling and disabling schedules."""
        # Add schedule
        schedule_id = await cron_scheduler.add_schedule(
            name="toggle-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        
        # Initially enabled
        schedule = cron_scheduler.schedules[schedule_id]
        assert schedule.enabled is True
        
        # Disable schedule
        disabled = await cron_scheduler.disable_schedule(schedule_id)
        assert disabled is True
        assert schedule.enabled is False
        
        # Enable schedule
        enabled = await cron_scheduler.enable_schedule(schedule_id)
        assert enabled is True
        assert schedule.enabled is True
    
    @pytest.mark.asyncio
    async def test_enable_disable_schedule_not_found(self, cron_scheduler):
        """Test enabling/disabling non-existent schedule."""
        enabled = await cron_scheduler.enable_schedule("nonexistent")
        assert enabled is False
        
        disabled = await cron_scheduler.disable_schedule("nonexistent")
        assert disabled is False
    
    @pytest.mark.asyncio
    async def test_get_schedules(self, cron_scheduler):
        """Test getting all schedules."""
        # Initially empty
        schedules = cron_scheduler.get_schedules()
        assert schedules == []
        
        # Add schedules
        schedule_id1 = await cron_scheduler.add_schedule(
            name="schedule1",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        schedule_id2 = await cron_scheduler.add_schedule(
            name="schedule2",
            cron_pattern="0 */2 * * *",
            tasks=["run_tests"]
        )
        
        # Get schedules
        schedules = cron_scheduler.get_schedules()
        
        assert len(schedules) == 2
        schedule_names = [s["name"] for s in schedules]
        assert "schedule1" in schedule_names
        assert "schedule2" in schedule_names
        
        # Verify schedule details
        for schedule_info in schedules:
            assert "schedule_id" in schedule_info
            assert "name" in schedule_info
            assert "cron_pattern" in schedule_info
            assert "tasks" in schedule_info
            assert "enabled" in schedule_info
            assert "next_run" in schedule_info
    
    def test_get_predefined_tasks(self, cron_scheduler):
        """Test getting predefined tasks."""
        tasks = cron_scheduler.get_predefined_tasks()
        
        assert isinstance(tasks, dict)
        assert len(tasks) > 0
        assert "clean_code" in tasks
        assert "run_tests" in tasks
        assert "code_review" in tasks
        
        # Verify descriptions
        assert isinstance(tasks["clean_code"], str)
        assert len(tasks["clean_code"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_schedule(self, cron_scheduler):
        """Test manually executing a schedule."""
        # Set up task callback
        task_callback = AsyncMock(return_value="Task completed")
        slack_callback = AsyncMock()
        cron_scheduler.set_task_callback(task_callback)
        cron_scheduler.set_slack_callback(slack_callback)
        
        # Add schedule
        schedule_id = await cron_scheduler.add_schedule(
            name="manual-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code", "run_tests"]
        )
        
        # Execute schedule
        result = await cron_scheduler.execute_schedule(schedule_id)
        
        # Verify execution
        assert result["schedule_id"] == schedule_id
        assert result["schedule_name"] == "manual-schedule"
        assert len(result["tasks"]) == 2
        
        # Verify all tasks were executed
        for task_result in result["tasks"]:
            assert task_result["status"] == "completed"
            assert task_result["result"] == "Task completed"
        
        # Verify task callback was called for each task
        assert task_callback.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_schedule_not_found(self, cron_scheduler):
        """Test executing non-existent schedule."""
        with pytest.raises(CronScheduleError) as exc_info:
            await cron_scheduler.execute_schedule("nonexistent-id")
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_schedule_no_callback(self, cron_scheduler):
        """Test executing schedule without task callback."""
        # Add schedule
        schedule_id = await cron_scheduler.add_schedule(
            name="no-callback-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        
        # Try to execute without callback
        with pytest.raises(CronScheduleError) as exc_info:
            await cron_scheduler.execute_schedule(schedule_id)
        
        assert "callback not configured" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_schedule_with_failure(self, cron_scheduler):
        """Test executing schedule with task failure."""
        # Set up task callback that fails
        task_callback = AsyncMock(side_effect=Exception("Task failed"))
        slack_callback = AsyncMock()
        cron_scheduler.set_task_callback(task_callback)
        cron_scheduler.set_slack_callback(slack_callback)
        
        # Add schedule
        schedule_id = await cron_scheduler.add_schedule(
            name="failing-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        
        # Execute schedule
        result = await cron_scheduler.execute_schedule(schedule_id)
        
        # Verify failure was recorded
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["status"] == "failed"
        assert "Task failed" in result["tasks"][0]["error"]
    
    def test_validate_cron_pattern(self, cron_scheduler):
        """Test cron pattern validation."""
        # Valid patterns
        valid_patterns = [
            "0 0 * * *",      # Daily at midnight
            "0 */2 * * *",    # Every 2 hours
            "30 9 * * 1-5",   # 9:30 AM on weekdays
            "0 0 1 * *",      # First day of month
            "*/15 * * * *"    # Every 15 minutes
        ]
        
        for pattern in valid_patterns:
            assert cron_scheduler._validate_cron_pattern(pattern) is True
        
        # Invalid patterns
        invalid_patterns = [
            "invalid",        # Not enough parts
            "0 0 * *",        # Too few parts
            "0 0 * * * *",    # Too many parts
            "60 0 * * *",     # Invalid minute
            "0 25 * * *",     # Invalid hour
            "0 0 32 * *",     # Invalid day
            "0 0 * 13 *",     # Invalid month
            "0 0 * * 8"       # Invalid weekday
        ]
        
        for pattern in invalid_patterns:
            assert cron_scheduler._validate_cron_pattern(pattern) is False
    
    def test_validate_cron_part(self, cron_scheduler):
        """Test individual cron part validation."""
        # Test wildcard
        assert cron_scheduler._validate_cron_part("*", 0, 59) is True
        
        # Test step values
        assert cron_scheduler._validate_cron_part("*/2", 0, 59) is True
        assert cron_scheduler._validate_cron_part("*/0", 0, 59) is False
        
        # Test ranges
        assert cron_scheduler._validate_cron_part("1-5", 0, 59) is True
        assert cron_scheduler._validate_cron_part("50-70", 0, 59) is False
        
        # Test lists
        assert cron_scheduler._validate_cron_part("1,3,5", 0, 59) is True
        assert cron_scheduler._validate_cron_part("1,70", 0, 59) is False
        
        # Test single values
        assert cron_scheduler._validate_cron_part("30", 0, 59) is True
        assert cron_scheduler._validate_cron_part("70", 0, 59) is False
    
    @pytest.mark.asyncio
    async def test_save_load_schedules(self, cron_scheduler):
        """Test saving and loading schedules."""
        # Add schedules
        schedule_id1 = await cron_scheduler.add_schedule(
            name="schedule1",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"]
        )
        schedule_id2 = await cron_scheduler.add_schedule(
            name="schedule2",
            cron_pattern="0 */2 * * *",
            tasks=["run_tests"]
        )
        
        # Save schedules
        cron_scheduler._save_schedules()
        
        # Verify file exists
        assert cron_scheduler.schedules_file.exists()
        
        # Clear schedules and reload
        cron_scheduler.schedules.clear()
        cron_scheduler._load_schedules()
        
        # Verify schedules were loaded
        assert len(cron_scheduler.schedules) == 2
        assert schedule_id1 in cron_scheduler.schedules
        assert schedule_id2 in cron_scheduler.schedules
        
        # Verify schedule details
        schedule1 = cron_scheduler.schedules[schedule_id1]
        schedule2 = cron_scheduler.schedules[schedule_id2]
        assert schedule1.name == "schedule1"
        assert schedule2.name == "schedule2"
        assert schedule1.cron_pattern == "0 0 * * *"
        assert schedule2.cron_pattern == "0 */2 * * *"
    
    def test_get_scheduler_stats(self, cron_scheduler):
        """Test getting scheduler statistics."""
        # Add schedules
        asyncio.run(cron_scheduler.add_schedule(
            name="enabled-schedule",
            cron_pattern="0 0 * * *",
            tasks=["clean_code"],
            enabled=True
        ))
        
        schedule_id = asyncio.run(cron_scheduler.add_schedule(
            name="disabled-schedule",
            cron_pattern="0 */2 * * *",
            tasks=["run_tests"],
            enabled=False
        ))
        
        # Set callbacks
        cron_scheduler.set_task_callback(AsyncMock())
        cron_scheduler.set_slack_callback(AsyncMock())
        
        stats = cron_scheduler.get_scheduler_stats()
        
        assert stats["is_running"] is False
        assert stats["total_schedules"] == 2
        assert stats["enabled_schedules"] == 1
        assert stats["disabled_schedules"] == 1
        assert stats["predefined_tasks"] == len(cron_scheduler.predefined_tasks)
        assert stats["task_callback_configured"] is True
        assert stats["slack_callback_configured"] is True