"""
Enhanced unit tests for core data models.

These tests provide comprehensive coverage of model behavior
with various edge cases and data combinations.
"""

import pytest
import string
import random
from datetime import datetime, timedelta
from typing import List

from claude_remote_client.models import (
    ClaudeSession, QueuedTask, CronSchedule, SlackMessage,
    TaskStatus, SessionStatus
)
from tests.test_utilities import TestDataGenerator, AssertionHelpers


class TestClaudeSessionEnhanced:
    """Enhanced tests for ClaudeSession."""
    
    def test_session_serialization_various_states(self):
        """Test session serialization with various states."""
        test_cases = [
            {
                'project_path': '/home/user/project',
                'project_name': 'test-project',
                'status': SessionStatus.ACTIVE
            },
            {
                'project_path': '/very/long/path/to/some/deeply/nested/project',
                'project_name': 'nested-project',
                'status': SessionStatus.INACTIVE
            },
            {
                'project_path': '',
                'project_name': '',
                'status': SessionStatus.ERROR
            }
        ]
        
        for case in test_cases:
            session = ClaudeSession(**case)
            data = session.to_dict()
            
            # Verify all required fields are present
            required_fields = [
                'session_id', 'project_path', 'project_name', 'status',
                'created_at', 'last_activity', 'conversation_history'
            ]
            for field in required_fields:
                assert field in data
            
            # Verify data types
            assert isinstance(data['session_id'], str)
            assert isinstance(data['project_path'], str)
            assert isinstance(data['project_name'], str)
            assert isinstance(data['status'], str)
            assert isinstance(data['created_at'], str)
            assert isinstance(data['last_activity'], str)
            assert isinstance(data['conversation_history'], list)
    
    def test_session_activity_update_multiple_times(self):
        """Test multiple activity updates are monotonically increasing."""
        session = ClaudeSession()
        timestamps = [session.last_activity]
        
        # Update activity multiple times
        for _ in range(5):
            import time
            time.sleep(0.001)
            session.update_activity()
            timestamps.append(session.last_activity)
        
        # Verify all timestamps are increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]
    
    def test_add_message_preserves_order_bulk(self):
        """Test that multiple messages are added in correct order."""
        session = ClaudeSession()
        
        messages = [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
            ("user", "How are you?"),
            ("assistant", "I'm doing well, thanks!"),
            ("user", "Great!")
        ]
        
        for role, content in messages:
            session.add_message(role, content)
        
        assert len(session.conversation_history) == len(messages)
        
        for i, (expected_role, expected_content) in enumerate(messages):
            message = session.conversation_history[i]
            assert message['role'] == expected_role
            assert message['content'] == expected_content
            assert 'timestamp' in message
    
    def test_project_name_extraction_edge_cases(self):
        """Test project name extraction with edge cases."""
        test_cases = [
            ("/home/user/my-project", "my-project"),
            ("/single", "single"),
            ("relative/path", "path"),
            ("", ""),
            ("/", ""),
            ("/home/user/project/", ""),  # Trailing slash
        ]
        
        for path, expected_name in test_cases:
            session = ClaudeSession(project_path=path)
            if expected_name:
                assert session.project_name == expected_name
    
    def test_is_active_all_statuses(self):
        """Test is_active() for all possible statuses."""
        for status in SessionStatus:
            session = ClaudeSession(status=status)
            expected_active = (status == SessionStatus.ACTIVE)
            assert session.is_active() == expected_active
    
    def test_conversation_history_with_timestamps(self):
        """Test conversation history maintains proper timestamps."""
        session = ClaudeSession()
        
        # Add messages with custom timestamps
        base_time = datetime.now()
        for i in range(3):
            timestamp = base_time + timedelta(minutes=i)
            session.add_message("user", f"Message {i}", timestamp)
        
        # Verify timestamps are preserved
        for i, message in enumerate(session.conversation_history):
            expected_time = base_time + timedelta(minutes=i)
            assert message['timestamp'] == expected_time.isoformat()


class TestQueuedTaskEnhanced:
    """Enhanced tests for QueuedTask."""
    
    def test_task_serialization_various_states(self):
        """Test task serialization with various states and data."""
        test_cases = [
            {
                'queue_name': 'high-priority',
                'description': 'Critical bug fix',
                'command': 'fix_critical_bug.py',
                'priority': 10,
                'status': TaskStatus.PENDING
            },
            {
                'queue_name': 'maintenance',
                'description': 'Clean up temporary files',
                'command': 'cleanup.sh',
                'priority': 1,
                'status': TaskStatus.COMPLETED,
                'result': 'Cleanup completed successfully'
            },
            {
                'queue_name': 'testing',
                'description': 'Run integration tests',
                'command': 'pytest tests/integration/',
                'priority': 5,
                'status': TaskStatus.FAILED,
                'error_message': 'Test timeout'
            }
        ]
        
        for case in test_cases:
            task = QueuedTask(**case)
            data = task.to_dict()
            
            # Verify all required fields are present
            required_fields = [
                'task_id', 'queue_name', 'description', 'command',
                'status', 'priority', 'created_at', 'retry_count', 'max_retries'
            ]
            for field in required_fields:
                assert field in data
            
            # Verify data types
            assert isinstance(data['task_id'], str)
            assert isinstance(data['queue_name'], str)
            assert isinstance(data['status'], str)
            assert isinstance(data['priority'], int)
            assert isinstance(data['retry_count'], int)
            assert isinstance(data['max_retries'], int)
    
    def test_task_execution_state_transitions_complete_flow(self):
        """Test complete task execution flow."""
        task = QueuedTask(
            queue_name="test-queue",
            description="Test task",
            command="echo 'test'"
        )
        
        # Initial state
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None
        
        # Start execution
        task.start_execution()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        assert task.completed_at is None
        AssertionHelpers.assert_datetime_recent(task.started_at)
        
        # Complete execution
        result = "Task completed successfully"
        task.complete_execution(result)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == result
        assert task.completed_at is not None
        AssertionHelpers.assert_datetime_recent(task.completed_at)
        assert task.completed_at >= task.started_at
    
    def test_task_failure_and_retry_scenarios(self):
        """Test various failure and retry scenarios."""
        # Test with different max_retries values
        retry_scenarios = [
            (0, 1),  # No retries allowed
            (1, 3),  # Some retries allowed
            (5, 5),  # At max retries
        ]
        
        for retry_count, max_retries in retry_scenarios:
            task = QueuedTask(
                retry_count=retry_count,
                max_retries=max_retries
            )
            
            original_retry_count = task.retry_count
            error_message = f"Error after {retry_count} retries"
            
            task.fail_execution(error_message)
            
            assert task.status == TaskStatus.FAILED
            assert task.error_message == error_message
            assert task.retry_count == original_retry_count + 1
            assert task.completed_at is not None
            
            # Test retry logic
            if task.retry_count < task.max_retries:
                assert task.can_retry()
            else:
                assert not task.can_retry()
    
    def test_can_retry_logic_comprehensive(self):
        """Test comprehensive retry logic scenarios."""
        test_cases = [
            # (retry_count, max_retries, status, expected_can_retry)
            (0, 3, TaskStatus.FAILED, True),
            (2, 3, TaskStatus.FAILED, True),
            (3, 3, TaskStatus.FAILED, False),
            (0, 3, TaskStatus.COMPLETED, False),
            (0, 3, TaskStatus.RUNNING, False),
            (0, 3, TaskStatus.PENDING, False),
            (5, 3, TaskStatus.FAILED, False),  # Over max retries
        ]
        
        for retry_count, max_retries, status, expected in test_cases:
            task = QueuedTask(
                retry_count=retry_count,
                max_retries=max_retries,
                status=status
            )
            assert task.can_retry() == expected, f"Failed for {retry_count}/{max_retries}, status={status}"
    
    def test_task_priority_ordering(self):
        """Test that tasks can be properly ordered by priority."""
        tasks = [
            QueuedTask(description="Low priority", priority=1),
            QueuedTask(description="High priority", priority=10),
            QueuedTask(description="Medium priority", priority=5),
            QueuedTask(description="Urgent", priority=15),
        ]
        
        # Sort by priority (descending)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        expected_order = [15, 10, 5, 1]
        actual_order = [t.priority for t in sorted_tasks]
        assert actual_order == expected_order


class TestCronScheduleEnhanced:
    """Enhanced tests for CronSchedule."""
    
    def test_schedule_serialization_various_patterns(self):
        """Test schedule serialization with various cron patterns."""
        test_cases = [
            {
                'name': 'hourly-cleanup',
                'cron_pattern': '0 * * * *',
                'tasks': ['clean_temp', 'vacuum_db'],
                'enabled': True
            },
            {
                'name': 'daily-backup',
                'cron_pattern': '0 2 * * *',
                'tasks': ['backup_database', 'backup_files'],
                'enabled': False
            },
            {
                'name': 'weekly-report',
                'cron_pattern': '0 0 * * 0',
                'tasks': ['generate_report'],
                'enabled': True
            }
        ]
        
        for case in test_cases:
            schedule = CronSchedule(**case)
            data = schedule.to_dict()
            
            # Verify all required fields are present
            required_fields = [
                'schedule_id', 'name', 'cron_pattern', 'tasks',
                'enabled', 'created_at', 'run_count'
            ]
            for field in required_fields:
                assert field in data
            
            # Verify data types
            assert isinstance(data['schedule_id'], str)
            assert isinstance(data['name'], str)
            assert isinstance(data['cron_pattern'], str)
            assert isinstance(data['tasks'], list)
            assert isinstance(data['enabled'], bool)
            assert isinstance(data['run_count'], int)
    
    def test_next_run_calculation_various_patterns(self):
        """Test next run calculation for various cron patterns."""
        patterns = [
            "0 * * * *",      # Every hour
            "0 0 * * *",      # Daily at midnight
            "0 0 * * 0",      # Weekly on Sunday
            "*/15 * * * *",   # Every 15 minutes
        ]
        
        for pattern in patterns:
            schedule = CronSchedule(cron_pattern=pattern)
            schedule.calculate_next_run()
            
            if schedule.next_run:
                # Next run should be in the future
                assert schedule.next_run > datetime.now()
                # Should be within reasonable bounds (not too far in future)
                max_future = datetime.now() + timedelta(days=8)  # Allow for weekly schedules
                assert schedule.next_run < max_future
    
    def test_should_run_logic_comprehensive(self):
        """Test comprehensive should_run logic."""
        schedule = CronSchedule(cron_pattern="0 * * * *")
        
        # Test disabled schedule
        schedule.enabled = False
        schedule.next_run = datetime.now() - timedelta(minutes=1)
        assert not schedule.should_run()
        
        # Test enabled schedule with no next_run
        schedule.enabled = True
        schedule.next_run = None
        assert not schedule.should_run()
        
        # Test enabled schedule with past next_run
        schedule.next_run = datetime.now() - timedelta(minutes=1)
        assert schedule.should_run()
        
        # Test enabled schedule with future next_run
        schedule.next_run = datetime.now() + timedelta(minutes=1)
        assert not schedule.should_run()
        
        # Test edge case: next_run is very close to now
        schedule.next_run = datetime.now() - timedelta(seconds=1)
        assert schedule.should_run()
    
    def test_mark_executed_updates_correctly(self):
        """Test that mark_executed updates all relevant fields."""
        schedule = CronSchedule(
            cron_pattern="0 */2 * * *",  # Every 2 hours
            run_count=5
        )
        
        original_count = schedule.run_count
        original_next_run = schedule.next_run
        
        schedule.mark_executed()
        
        # Run count should increment
        assert schedule.run_count == original_count + 1
        
        # Last run should be set to recent time
        assert schedule.last_run is not None
        AssertionHelpers.assert_datetime_recent(schedule.last_run)
        
        # Next run should be recalculated (may be same if we're at exact hour boundary)
        assert schedule.next_run is not None
        assert schedule.next_run > datetime.now()
    
    def test_invalid_cron_patterns(self):
        """Test handling of invalid cron patterns."""
        invalid_patterns = [
            "",
            "invalid",
            "60 * * * *",  # Invalid minute
            "* 25 * * *",  # Invalid hour
            "* * 32 * *",  # Invalid day
        ]
        
        for pattern in invalid_patterns:
            schedule = CronSchedule(cron_pattern=pattern)
            schedule.calculate_next_run()
            # Should handle gracefully without crashing
            assert schedule.next_run is None or isinstance(schedule.next_run, datetime)


class TestSlackMessageEnhanced:
    """Enhanced tests for SlackMessage."""
    
    def test_message_serialization_various_types(self):
        """Test message serialization with various message types."""
        test_cases = [
            {
                'channel_id': 'C1234567890',
                'user_id': 'U1234567890',
                'text': 'Regular message',
                'is_bot_message': False
            },
            {
                'channel_id': 'C0987654321',
                'user_id': 'U0987654321',
                'text': '@@projects',
                'is_bot_message': False
            },
            {
                'channel_id': 'C1111111111',
                'user_id': 'B2222222222',  # Bot user
                'text': 'Bot response message',
                'is_bot_message': True
            }
        ]
        
        for case in test_cases:
            message = SlackMessage(**case)
            data = message.to_dict()
            
            # Verify all required fields are present
            required_fields = [
                'message_id', 'channel_id', 'user_id', 'text',
                'timestamp', 'is_bot_message', 'is_command'
            ]
            for field in required_fields:
                assert field in data
            
            # Verify data types
            assert isinstance(data['message_id'], str)
            assert isinstance(data['channel_id'], str)
            assert isinstance(data['user_id'], str)
            assert isinstance(data['text'], str)
            assert isinstance(data['timestamp'], str)
            assert isinstance(data['is_bot_message'], bool)
            assert isinstance(data['is_command'], bool)
    
    def test_command_detection_edge_cases(self):
        """Test command detection with edge cases."""
        test_cases = [
            ("@@projects", True),
            ("  @@projects  ", True),
            ("@@", True),  # Just @@ is considered a command (empty command)
            ("@projects", False),  # Single @
            ("Regular message", False),
            ("This has @@projects in middle", False),
            ("@@projects with args", True),
            ("@@switch project-name", True),
            ("", False),
        ]
        
        for text, expected_is_command in test_cases:
            message = SlackMessage(text=text)
            assert message.is_command == expected_is_command, f"Failed for text: '{text}'"
    
    def test_command_extraction_comprehensive(self):
        """Test comprehensive command extraction scenarios."""
        test_cases = [
            # (text, expected_command, expected_args)
            ("@@projects", "projects", []),
            ("@@switch my-project", "switch", ["my-project"]),
            ("@@queue_add urgent 'Fix critical bug'", "queue_add", ["urgent", "'Fix", "critical", "bug'"]),
            ("  @@help  ", "help", []),
            ("@@sessions --verbose", "sessions", ["--verbose"]),
            ("Regular message", None, []),
            ("@@", "", []),
        ]
        
        for text, expected_command, expected_args in test_cases:
            message = SlackMessage(text=text)
            
            command = message.get_command()
            args = message.get_command_args()
            
            assert command == expected_command, f"Command mismatch for '{text}': got {command}, expected {expected_command}"
            assert args == expected_args, f"Args mismatch for '{text}': got {args}, expected {expected_args}"
    
    def test_code_formatting_various_languages(self):
        """Test code formatting with various languages and content."""
        message = SlackMessage()
        
        test_cases = [
            ("print('hello')", "python", "```python\nprint('hello')\n```"),
            ("console.log('hello')", "javascript", "```javascript\nconsole.log('hello')\n```"),
            ("echo 'hello'", "bash", "```bash\necho 'hello'\n```"),
            ("SELECT * FROM users", "sql", "```sql\nSELECT * FROM users\n```"),
            ("def func():\n    pass", None, "```\ndef func():\n    pass\n```"),
        ]
        
        for code, language, expected in test_cases:
            if language:
                result = message.format_code_block(code, language)
            else:
                result = message.format_code_block(code)
            
            assert result == expected
        
        # Test inline code formatting
        inline_cases = [
            ("variable", "`variable`"),
            ("function_name", "`function_name`"),
            ("", "``"),
        ]
        
        for code, expected in inline_cases:
            result = message.format_inline_code(code)
            assert result == expected
    
    def test_message_threading_support(self):
        """Test message threading functionality."""
        # Parent message
        parent = SlackMessage(
            channel_id="C1234567890",
            user_id="U1234567890",
            text="Original message"
        )
        
        # Thread reply
        reply = SlackMessage(
            channel_id="C1234567890",
            user_id="U0987654321",
            text="Reply to message",
            thread_ts="1234567890.123456"
        )
        
        assert parent.thread_ts is None
        assert reply.thread_ts == "1234567890.123456"
        
        # Serialization should include thread_ts
        reply_data = reply.to_dict()
        assert reply_data['thread_ts'] == "1234567890.123456"


class TestModelInvariants:
    """Test invariants that should hold across all models."""
    
    def test_all_models_have_valid_ids(self):
        """Test that all models generate valid UUIDs for IDs."""
        models = [
            ClaudeSession(),
            QueuedTask(),
            CronSchedule(),
            SlackMessage()
        ]
        
        for model in models:
            if hasattr(model, 'session_id'):
                AssertionHelpers.assert_valid_uuid(model.session_id)
            elif hasattr(model, 'task_id'):
                AssertionHelpers.assert_valid_uuid(model.task_id)
            elif hasattr(model, 'schedule_id'):
                AssertionHelpers.assert_valid_uuid(model.schedule_id)
            elif hasattr(model, 'message_id'):
                AssertionHelpers.assert_valid_uuid(model.message_id)
    
    def test_all_models_serializable(self):
        """Test that all models can be serialized to JSON-compatible dict."""
        models = [
            ClaudeSession(project_path="/test", project_name="test"),
            QueuedTask(queue_name="test", description="test task"),
            CronSchedule(name="test", cron_pattern="0 * * * *"),
            SlackMessage(text="test message")
        ]
        
        for model in models:
            data = model.to_dict()
            
            # Should be a dictionary
            assert isinstance(data, dict)
            
            # Should have at least one field
            assert len(data) > 0
            
            # All values should be JSON-serializable types
            import json
            try:
                json.dumps(data)
            except (TypeError, ValueError) as e:
                pytest.fail(f"Model {type(model).__name__} serialization not JSON-compatible: {e}")
    
    def test_models_with_timestamps_have_recent_creation(self):
        """Test that models with creation timestamps are recent."""
        models_with_timestamps = [
            ClaudeSession(),
            QueuedTask(),
            CronSchedule(),
            SlackMessage()
        ]
        
        for model in models_with_timestamps:
            if hasattr(model, 'created_at'):
                # Allow for some tolerance in test execution time
                AssertionHelpers.assert_datetime_recent(model.created_at, tolerance_seconds=60)
            if hasattr(model, 'timestamp'):
                AssertionHelpers.assert_datetime_recent(model.timestamp, tolerance_seconds=60)
    
    def test_model_id_uniqueness(self):
        """Test that model IDs are unique across instances."""
        # Test each model type
        model_types = [ClaudeSession, QueuedTask, CronSchedule, SlackMessage]
        
        for model_type in model_types:
            # Create multiple instances
            instances = [model_type() for _ in range(10)]
            
            # Extract IDs
            ids = []
            for instance in instances:
                if hasattr(instance, 'session_id'):
                    ids.append(instance.session_id)
                elif hasattr(instance, 'task_id'):
                    ids.append(instance.task_id)
                elif hasattr(instance, 'schedule_id'):
                    ids.append(instance.schedule_id)
                elif hasattr(instance, 'message_id'):
                    ids.append(instance.message_id)
            
            # All IDs should be unique
            assert len(ids) == len(set(ids)), f"Duplicate IDs found in {model_type.__name__}"