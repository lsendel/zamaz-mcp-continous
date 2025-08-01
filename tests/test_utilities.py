"""
Test utilities and helper functions for comprehensive testing.

This module provides utilities for property-based testing, test data generation,
and common test patterns used across the test suite.
"""

import pytest
import string
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

from claude_remote_client.models import (
    ClaudeSession, QueuedTask, CronSchedule, SlackMessage,
    TaskStatus, SessionStatus
)


# Test data generation utilities


class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_conversation_history(length: int = 10) -> List[Dict[str, Any]]:
        """Generate conversation history for testing."""
        roles = ["user", "assistant"]
        history = []
        
        for i in range(length):
            history.append({
                "role": random.choice(roles),
                "content": f"Test message {i + 1}",
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat()
            })
        
        return history
    
    @staticmethod
    def generate_project_structure() -> Dict[str, Any]:
        """Generate a mock project structure."""
        return {
            "name": "test-project",
            "path": "/test/project",
            "files": [
                "README.md",
                "src/main.py",
                "src/utils.py",
                "tests/test_main.py",
                "requirements.txt"
            ],
            "directories": [
                "src",
                "tests",
                "docs"
            ]
        }
    
    @staticmethod
    def generate_task_queue(size: int = 20) -> List[QueuedTask]:
        """Generate a list of tasks for queue testing."""
        tasks = []
        task_types = ["code_review", "run_tests", "clean_code", "update_deps"]
        
        for i in range(size):
            task = QueuedTask(
                queue_name="test-queue",
                description=f"Test task {i + 1}",
                command=f"test_command_{i}",
                project_path=f"/test/project-{i % 3}",
                priority=random.randint(0, 5),
                status=random.choice(list(TaskStatus))
            )
            tasks.append(task)
        
        return tasks
    
    @staticmethod
    def generate_cron_schedules(count: int = 5) -> List[CronSchedule]:
        """Generate cron schedules for testing."""
        schedules = []
        patterns = [
            "0 * * * *",      # Hourly
            "0 0 * * *",      # Daily
            "0 0 * * 0",      # Weekly
            "*/15 * * * *",   # Every 15 minutes
            "30 2 * * *"      # Daily at 2:30 AM
        ]
        
        for i in range(count):
            schedule = CronSchedule(
                name=f"schedule-{i + 1}",
                cron_pattern=patterns[i % len(patterns)],
                tasks=[f"task-{j}" for j in range(1, 4)],
                project_path=f"/test/project-{i}",
                enabled=random.choice([True, False])
            )
            schedules.append(schedule)
        
        return schedules


class MockFactory:
    """Factory for creating mock objects."""
    
    @staticmethod
    def create_mock_slack_client():
        """Create a comprehensive mock Slack client."""
        client = MagicMock()
        client.is_connected = True
        client.send_message = AsyncMock(return_value={"ok": True, "ts": "1234567890.123456"})
        client.update_message = AsyncMock(return_value={"ok": True})
        client.delete_message = AsyncMock(return_value={"ok": True})
        client.get_user_info = AsyncMock(return_value={
            "ok": True,
            "user": {
                "id": "U1234567890",
                "name": "testuser",
                "real_name": "Test User"
            }
        })
        client.get_channel_info = AsyncMock(return_value={
            "ok": True,
            "channel": {
                "id": "C1234567890",
                "name": "test-channel"
            }
        })
        return client
    
    @staticmethod
    def create_mock_claude_process():
        """Create a mock Claude subprocess."""
        process = AsyncMock()
        process.pid = 12345
        process.returncode = 0
        process.stdout.readline = AsyncMock(return_value=b"Claude response\n")
        process.stderr.readline = AsyncMock(return_value=b"")
        process.stdin.write = AsyncMock()
        process.stdin.drain = AsyncMock()
        process.wait = AsyncMock(return_value=0)
        process.terminate = AsyncMock()
        process.kill = AsyncMock()
        return process
    
    @staticmethod
    def create_mock_session_manager():
        """Create a mock session manager."""
        manager = AsyncMock()
        manager.active_sessions = {}
        manager.create_session = AsyncMock()
        manager.get_session = AsyncMock()
        manager.switch_session = AsyncMock()
        manager.list_sessions = AsyncMock(return_value=[])
        manager.cleanup_session = AsyncMock()
        return manager
    
    @staticmethod
    def create_mock_queue_manager():
        """Create a mock queue manager."""
        manager = AsyncMock()
        manager.queues = {}
        manager.add_task = AsyncMock()
        manager.get_queue = AsyncMock(return_value=[])
        manager.process_queue = AsyncMock()
        manager.clear_queue = AsyncMock()
        return manager


class AssertionHelpers:
    """Helper methods for common assertions."""
    
    @staticmethod
    def assert_valid_uuid(uuid_string: str):
        """Assert that a string is a valid UUID."""
        import uuid
        try:
            uuid.UUID(uuid_string)
        except ValueError:
            pytest.fail(f"'{uuid_string}' is not a valid UUID")
    
    @staticmethod
    def assert_datetime_recent(dt: datetime, tolerance_seconds: int = 60):
        """Assert that a datetime is recent (within tolerance)."""
        now = datetime.now()
        diff = abs((now - dt).total_seconds())
        assert diff <= tolerance_seconds, f"DateTime {dt} is not recent (diff: {diff}s)"
    
    @staticmethod
    def assert_dict_subset(subset: Dict, superset: Dict):
        """Assert that subset is contained in superset."""
        for key, value in subset.items():
            assert key in superset, f"Key '{key}' not found in superset"
            assert superset[key] == value, f"Value mismatch for key '{key}': {superset[key]} != {value}"
    
    @staticmethod
    def assert_async_mock_called_with_timeout(mock: AsyncMock, timeout: float = 1.0):
        """Assert that an async mock was called within timeout."""
        import asyncio
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if mock.called:
                return
            time.sleep(0.01)
        
        pytest.fail(f"AsyncMock was not called within {timeout} seconds")


# Test configuration


# Common test fixtures
@pytest.fixture
def test_data_generator():
    """Provide test data generator."""
    return TestDataGenerator()


@pytest.fixture
def mock_factory():
    """Provide mock factory."""
    return MockFactory()


@pytest.fixture
def assertion_helpers():
    """Provide assertion helpers."""
    return AssertionHelpers()