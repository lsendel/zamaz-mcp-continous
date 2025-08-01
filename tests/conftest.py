"""
Comprehensive test configuration and fixtures for Claude Remote Client.

This module provides shared fixtures, mocks, and utilities for testing
all components of the application with proper isolation and cleanup.
"""

import pytest
import asyncio
import tempfile
import json
import os
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from claude_remote_client.config import Config, SlackConfig, ClaudeConfig, ProjectConfig
from claude_remote_client.models import ClaudeSession, QueuedTask, CronSchedule, SessionStatus, TaskStatus
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.task_queue.queue_manager import QueueManager
from claude_remote_client.task_queue.cron_scheduler import CronScheduler
from claude_remote_client.logging_config import setup_enhanced_logging, DEFAULT_LOGGING_CONFIG


# Test data constants
TEST_SLACK_TOKEN = "xoxb-test-token-12345"
TEST_APP_TOKEN = "xapp-test-token-12345"
TEST_CHANNEL_ID = "C1234567890"
TEST_SIGNING_SECRET = "test-signing-secret"
TEST_PROJECT_NAME = "test-project"
TEST_SESSION_ID = "test-session-123"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration with temporary directories."""
    return Config(
        slack=SlackConfig(
            bot_token=TEST_SLACK_TOKEN,
            app_token=TEST_APP_TOKEN,
            channel_id=TEST_CHANNEL_ID,
            signing_secret=TEST_SIGNING_SECRET
        ),
        claude=ClaudeConfig(
            cli_path="claude",
            timeout=300,
            default_args=["--dangerously-skip-permissions"]
        ),
        projects=[
            ProjectConfig(
                name=TEST_PROJECT_NAME,
                path=temp_dir,
                description="Test project"
            )
        ],
        log_level="DEBUG",
        data_dir=temp_dir,
        max_sessions=5,
        task_queue_size=100
    )


@pytest.fixture
def test_project_dir():
    """Create a temporary project directory with sample files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create sample project structure
        (Path(temp_dir) / "src").mkdir()
        (Path(temp_dir) / "tests").mkdir()
        (Path(temp_dir) / "README.md").write_text("# Test Project")
        (Path(temp_dir) / "src" / "main.py").write_text("print('Hello, World!')")
        (Path(temp_dir) / "tests" / "test_main.py").write_text("def test_main(): pass")
        
        yield temp_dir


@pytest.fixture
def test_session():
    """Create a test Claude session."""
    return ClaudeSession(
        session_id=TEST_SESSION_ID,
        project_path="/test/project",
        project_name=TEST_PROJECT_NAME,
        status=SessionStatus.ACTIVE,
        created_at=datetime.now(),
        last_activity=datetime.now(),
        process_id=12345,
        conversation_history=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    )


@pytest.fixture
def test_queued_task():
    """Create a test queued task."""
    return QueuedTask(
        task_id="task-123",
        queue_name="default",
        task_type="code_review",
        prompt="Review this code",
        project_name=TEST_PROJECT_NAME,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        priority=1
    )


@pytest.fixture
def test_cron_schedule():
    """Create a test cron schedule."""
    return CronSchedule(
        schedule_id="schedule-123",
        name="daily_cleanup",
        cron_pattern="0 2 * * *",
        task_type="clean_code",
        project_name=TEST_PROJECT_NAME,
        enabled=True,
        created_at=datetime.now()
    )


@pytest.fixture
async def session_manager(test_config):
    """Create a session manager with test configuration."""
    manager = SessionManager(test_config)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    client = MagicMock(spec=SlackBotClient)
    client.is_connected = True
    client.send_message = AsyncMock(return_value={"ok": True, "ts": "1234567890.123456"})
    client.update_message = AsyncMock(return_value={"ok": True})
    client.delete_message = AsyncMock(return_value={"ok": True})
    client.get_user_info = AsyncMock(return_value={"ok": True, "user": {"name": "testuser"}})
    return client


@pytest.fixture
def mock_subprocess():
    """Create a mock subprocess for Claude CLI."""
    with patch('asyncio.create_subprocess_exec') as mock_create:
        mock_process = AsyncMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.stdout.readline = AsyncMock(return_value=b"Claude response\n")
        mock_process.stderr.readline = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.terminate = AsyncMock()
        mock_process.kill = AsyncMock()
        
        mock_create.return_value = mock_process
        yield mock_create


@pytest.fixture
async def queue_manager(test_config):
    """Create a queue manager with test configuration."""
    manager = QueueManager(test_config)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
async def cron_scheduler(test_config):
    """Create a cron scheduler with test configuration."""
    scheduler = CronScheduler(test_config)
    await scheduler.start()
    yield scheduler
    await scheduler.stop()


@pytest.fixture
def mock_file_operations():
    """Mock file operations for testing."""
    with patch('aiofiles.open') as mock_open, \
         patch('aiofiles.os.path.exists') as mock_exists, \
         patch('aiofiles.os.makedirs') as mock_makedirs:
        
        mock_exists.return_value = True
        mock_makedirs.return_value = None
        
        # Mock file context manager
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value='{"test": "data"}')
        mock_file.write = AsyncMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        mock_open.return_value = mock_file
        
        yield {
            'open': mock_open,
            'exists': mock_exists,
            'makedirs': mock_makedirs,
            'file': mock_file
        }


@pytest.fixture
def enhanced_logger():
    """Create an enhanced logger for testing."""
    config = DEFAULT_LOGGING_CONFIG.copy()
    config['level'] = 'DEBUG'
    config['console']['enabled'] = False  # Disable console output in tests
    config['file']['enabled'] = False     # Disable file output in tests
    config['error_file']['enabled'] = False
    
    return setup_enhanced_logging(config)


class MockSlackEvent:
    """Mock Slack event for testing."""
    
    def __init__(self, event_type: str = "message", **kwargs):
        self.type = event_type
        self.data = {
            'type': event_type,
            'channel': TEST_CHANNEL_ID,
            'user': 'U1234567890',
            'text': 'test message',
            'ts': '1234567890.123456',
            **kwargs
        }


class MockClaudeProcess:
    """Mock Claude process for testing."""
    
    def __init__(self, responses: List[str] = None):
        self.responses = responses or ["Claude response"]
        self.response_index = 0
        self.pid = 12345
        self.returncode = 0
        self.terminated = False
    
    async def readline(self):
        """Mock readline method."""
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response.encode() + b'\n'
        return b''
    
    async def wait(self):
        """Mock wait method."""
        return self.returncode
    
    async def terminate(self):
        """Mock terminate method."""
        self.terminated = True
    
    async def kill(self):
        """Mock kill method."""
        self.terminated = True


@pytest.fixture
def performance_test_data():
    """Generate test data for performance testing."""
    return {
        'sessions': [
            ClaudeSession(
                session_id=f"session-{i}",
                project_name=f"project-{i}",
                project_path=f"/test/project-{i}",
                status=SessionStatus.ACTIVE
            )
            for i in range(100)
        ],
        'tasks': [
            QueuedTask(
                task_id=f"task-{i}",
                queue_name="default",
                task_type="code_review",
                prompt=f"Review code {i}",
                project_name=f"project-{i % 10}",
                status=TaskStatus.PENDING
            )
            for i in range(1000)
        ],
        'messages': [
            f"Test message {i} with some content to simulate real usage"
            for i in range(500)
        ]
    }


@pytest.fixture
def integration_test_environment(temp_dir):
    """Set up a complete integration test environment."""
    # Create directory structure
    data_dir = Path(temp_dir) / "data"
    logs_dir = Path(temp_dir) / "logs"
    projects_dir = Path(temp_dir) / "projects"
    
    data_dir.mkdir()
    logs_dir.mkdir()
    projects_dir.mkdir()
    
    # Create test projects
    for i in range(3):
        project_dir = projects_dir / f"project-{i}"
        project_dir.mkdir()
        (project_dir / "README.md").write_text(f"# Project {i}")
        (project_dir / "main.py").write_text(f"# Main file for project {i}")
    
    # Create configuration
    config = Config(
        slack=SlackConfig(
            bot_token=TEST_SLACK_TOKEN,
            app_token=TEST_APP_TOKEN,
            channel_id=TEST_CHANNEL_ID,
            signing_secret=TEST_SIGNING_SECRET
        ),
        claude=ClaudeConfig(cli_path="claude"),
        projects=[
            ProjectConfig(
                name=f"project-{i}",
                path=str(projects_dir / f"project-{i}"),
                description=f"Test project {i}"
            )
            for i in range(3)
        ],
        data_dir=str(data_dir),
        log_level="DEBUG"
    )
    
    return {
        'config': config,
        'data_dir': data_dir,
        'logs_dir': logs_dir,
        'projects_dir': projects_dir,
        'temp_dir': temp_dir
    }


# Utility functions for tests

def assert_session_state(session: ClaudeSession, expected_status: SessionStatus, **kwargs):
    """Assert session state matches expectations."""
    assert session.status == expected_status
    for key, value in kwargs.items():
        assert getattr(session, key) == value


def assert_task_state(task: QueuedTask, expected_status: TaskStatus, **kwargs):
    """Assert task state matches expectations."""
    assert task.status == expected_status
    for key, value in kwargs.items():
        assert getattr(task, key) == value


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for a condition to become true."""
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < timeout:
        if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
            return True
        await asyncio.sleep(interval)
    
    return False


def create_test_file(path: Path, content: str = "test content"):
    """Create a test file with content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# Markers for different test types
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.slow = pytest.mark.slow
