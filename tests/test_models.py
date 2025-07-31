"""
Unit tests for the core data models.
"""

import pytest
from datetime import datetime, timedelta
from claude_remote_client.models import (
    ClaudeSession, QueuedTask, CronSchedule, SlackMessage,
    TaskStatus, SessionStatus
)


class TestClaudeSession:
    """Test cases for ClaudeSession model."""
    
    def test_session_creation(self):
        """Test basic session creation."""
        session = ClaudeSession(
            project_path="/home/user/project",
            project_name="test-project"
        )
        
        assert session.session_id is not None
        assert session.project_path == "/home/user/project"
        assert session.project_name == "test-project"
        assert session.status == SessionStatus.INACTIVE
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
        assert session.conversation_history == []
    
    def test_session_auto_project_name(self):
        """Test automatic project name extraction from path."""
        session = ClaudeSession(project_path="/home/user/my-awesome-project")
        assert session.project_name == "my-awesome-project"
    
    def test_update_activity(self):
        """Test activity timestamp update."""
        session = ClaudeSession()
        original_time = session.last_activity
        
        # Wait a small amount to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        session.update_activity()
        assert session.last_activity > original_time
    
    def test_add_message(self):
        """Test adding messages to conversation history."""
        session = ClaudeSession()
        
        session.add_message("user", "Hello Claude!")
        session.add_message("assistant", "Hello! How can I help you?")
        
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0]["role"] == "user"
        assert session.conversation_history[0]["content"] == "Hello Claude!"
        assert session.conversation_history[1]["role"] == "assistant"
        assert "timestamp" in session.conversation_history[0]
    
    def test_is_active(self):
        """Test session active status check."""
        session = ClaudeSession()
        assert not session.is_active()
        
        session.status = SessionStatus.ACTIVE
        assert session.is_active()
    
    def test_to_dict(self):
        """Test session serialization to dictionary."""
        session = ClaudeSession(
            project_path="/test/path",
            project_name="test"
        )
        session.add_message("user", "test message")
        
        data = session.to_dict()
        
        assert data["session_id"] == session.session_id
        assert data["project_path"] == "/test/path"
        assert data["project_name"] == "test"
        assert data["status"] == "inactive"
        assert len(data["conversation_history"]) == 1


class TestQueuedTask:
    """Test cases for QueuedTask model."""
    
    def test_task_creation(self):
        """Test basic task creation."""
        task = QueuedTask(
            queue_name="test-queue",
            description="Test task",
            command="echo 'hello'",
            project_path="/test/path"
        )
        
        assert task.task_id is not None
        assert task.queue_name == "test-queue"
        assert task.description == "Test task"
        assert task.command == "echo 'hello'"
        assert task.status == TaskStatus.PENDING
        assert task.priority == 0
        assert task.retry_count == 0
        assert task.max_retries == 3
    
    def test_start_execution(self):
        """Test task execution start."""
        task = QueuedTask()
        task.start_execution()
        
        assert task.status == TaskStatus.RUNNING
        assert isinstance(task.started_at, datetime)
    
    def test_complete_execution(self):
        """Test task completion."""
        task = QueuedTask()
        task.start_execution()
        task.complete_execution("Task completed successfully")
        
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "Task completed successfully"
        assert isinstance(task.completed_at, datetime)
    
    def test_fail_execution(self):
        """Test task failure."""
        task = QueuedTask()
        task.start_execution()
        task.fail_execution("Task failed with error")
        
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Task failed with error"
        assert task.retry_count == 1
        assert isinstance(task.completed_at, datetime)
    
    def test_can_retry(self):
        """Test retry logic."""
        task = QueuedTask(max_retries=3)
        
        # Initially can't retry (not failed)
        assert not task.can_retry()
        
        # After first failure, can retry
        task.fail_execution("First failure")
        assert task.can_retry()
        assert task.retry_count == 1
        
        # After second failure, can still retry
        task.status = TaskStatus.PENDING  # Reset for retry
        task.fail_execution("Second failure")
        assert task.can_retry()
        assert task.retry_count == 2
        
        # After third failure, can't retry anymore (retry_count == max_retries)
        task.status = TaskStatus.PENDING  # Reset for retry
        task.fail_execution("Third failure")
        assert not task.can_retry()
        assert task.retry_count == 3
    
    def test_to_dict(self):
        """Test task serialization to dictionary."""
        task = QueuedTask(
            queue_name="test",
            description="Test task",
            command="test command"
        )
        
        data = task.to_dict()
        
        assert data["task_id"] == task.task_id
        assert data["queue_name"] == "test"
        assert data["description"] == "Test task"
        assert data["status"] == "pending"
        assert data["retry_count"] == 0


class TestCronSchedule:
    """Test cases for CronSchedule model."""
    
    def test_schedule_creation(self):
        """Test basic schedule creation."""
        schedule = CronSchedule(
            name="test-schedule",
            cron_pattern="0 */2 * * *",
            tasks=["clean_code", "run_tests"],
            project_path="/test/path"
        )
        
        assert schedule.schedule_id is not None
        assert schedule.name == "test-schedule"
        assert schedule.cron_pattern == "0 */2 * * *"
        assert schedule.tasks == ["clean_code", "run_tests"]
        assert schedule.enabled is True
        assert schedule.run_count == 0
        assert schedule.next_run is not None
    
    def test_calculate_next_run_hourly(self):
        """Test next run calculation for hourly pattern."""
        schedule = CronSchedule(cron_pattern="0 */2 * * *")
        schedule.calculate_next_run()
        
        # Should be approximately 2 hours from now
        expected_time = datetime.now() + timedelta(hours=2)
        time_diff = abs((schedule.next_run - expected_time).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    def test_calculate_next_run_daily(self):
        """Test next run calculation for daily pattern."""
        schedule = CronSchedule(cron_pattern="0 0 * * *")
        schedule.calculate_next_run()
        
        # Should be next midnight
        now = datetime.now()
        expected_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        assert schedule.next_run.hour == 0
        assert schedule.next_run.minute == 0
        assert schedule.next_run.date() == expected_time.date()
    
    def test_should_run(self):
        """Test schedule execution check."""
        schedule = CronSchedule()
        
        # Should not run if disabled
        schedule.enabled = False
        assert not schedule.should_run()
        
        # Should not run if next_run is in future
        schedule.enabled = True
        schedule.next_run = datetime.now() + timedelta(hours=1)
        assert not schedule.should_run()
        
        # Should run if next_run is in past
        schedule.next_run = datetime.now() - timedelta(minutes=1)
        assert schedule.should_run()
    
    def test_mark_executed(self):
        """Test marking schedule as executed."""
        schedule = CronSchedule(cron_pattern="0 */2 * * *")
        original_run_count = schedule.run_count
        
        schedule.mark_executed()
        
        assert schedule.run_count == original_run_count + 1
        assert isinstance(schedule.last_run, datetime)
        assert schedule.next_run is not None
    
    def test_to_dict(self):
        """Test schedule serialization to dictionary."""
        schedule = CronSchedule(
            name="test",
            cron_pattern="0 0 * * *",
            tasks=["task1", "task2"]
        )
        
        data = schedule.to_dict()
        
        assert data["schedule_id"] == schedule.schedule_id
        assert data["name"] == "test"
        assert data["cron_pattern"] == "0 0 * * *"
        assert data["tasks"] == ["task1", "task2"]
        assert data["enabled"] is True


class TestSlackMessage:
    """Test cases for SlackMessage model."""
    
    def test_message_creation(self):
        """Test basic message creation."""
        message = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Hello world!"
        )
        
        assert message.message_id is not None
        assert message.channel_id == "C1234567890"
        assert message.user_id == "U1234567890"
        assert message.text == "Hello world!"
        assert isinstance(message.timestamp, datetime)
        assert message.is_bot_message is False
        assert message.is_command is False
    
    def test_command_detection(self):
        """Test command message detection."""
        # Regular message
        regular_msg = SlackMessage(text="Hello world!")
        assert not regular_msg.is_command
        
        # Command message
        command_msg = SlackMessage(text="@@projects")
        assert command_msg.is_command
        
        # Command with spaces
        command_with_spaces = SlackMessage(text="  @@switch my-project  ")
        assert command_with_spaces.is_command
    
    def test_get_command(self):
        """Test command extraction."""
        # Regular message
        regular_msg = SlackMessage(text="Hello world!")
        assert regular_msg.get_command() is None
        
        # Simple command
        command_msg = SlackMessage(text="@@projects")
        assert command_msg.get_command() == "projects"
        
        # Command with arguments
        command_with_args = SlackMessage(text="@@switch my-project")
        assert command_with_args.get_command() == "switch"
    
    def test_get_command_args(self):
        """Test command argument extraction."""
        # No arguments
        no_args = SlackMessage(text="@@projects")
        assert no_args.get_command_args() == []
        
        # Single argument
        single_arg = SlackMessage(text="@@switch my-project")
        assert single_arg.get_command_args() == ["my-project"]
        
        # Multiple arguments
        multi_args = SlackMessage(text="@@queue_add my-queue 'Fix bug in auth'")
        assert multi_args.get_command_args() == ["my-queue", "'Fix", "bug", "in", "auth'"]
        
        # Regular message
        regular_msg = SlackMessage(text="Hello world!")
        assert regular_msg.get_command_args() == []
    
    def test_format_code_block(self):
        """Test code block formatting."""
        message = SlackMessage()
        
        # Without language
        result = message.format_code_block("print('hello')")
        assert result == "```\nprint('hello')\n```"
        
        # With language
        result = message.format_code_block("print('hello')", "python")
        assert result == "```python\nprint('hello')\n```"
    
    def test_format_inline_code(self):
        """Test inline code formatting."""
        message = SlackMessage()
        result = message.format_inline_code("variable_name")
        assert result == "`variable_name`"
    
    def test_to_dict(self):
        """Test message serialization to dictionary."""
        message = SlackMessage(
            channel_id="C123",
            user_id="U123",
            text="@@projects"
        )
        
        data = message.to_dict()
        
        assert data["message_id"] == message.message_id
        assert data["channel_id"] == "C123"
        assert data["user_id"] == "U123"
        assert data["text"] == "@@projects"
        assert data["is_command"] is True