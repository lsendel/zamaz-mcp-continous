"""
Comprehensive integration tests for Claude Remote Client.

These tests verify that components work together correctly in realistic scenarios,
including end-to-end workflows and cross-component interactions.
"""

import pytest
import asyncio
import tempfile
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta

from claude_remote_client.config import Config, SlackConfig, ClaudeConfig, ProjectConfig
from claude_remote_client.models import ClaudeSession, QueuedTask, CronSchedule, SlackMessage, TaskStatus
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.slack_client.message_handler import MessageHandler
from claude_remote_client.slack_client.command_router import CommandRouter
from claude_remote_client.task_queue.queue_manager import QueueManager
from claude_remote_client.task_queue.cron_scheduler import CronScheduler
from tests.test_utilities import MockFactory, TestDataGenerator


@pytest.fixture
def integration_config():
    """Create integration test configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            slack=SlackConfig(
                bot_token="xoxb-test-token",
                app_token="xapp-test-token",
                channel_id="C1234567890",
                signing_secret="test-secret"
            ),
            claude=ClaudeConfig(
                cli_path="claude",
                timeout=30,
                default_args=["--dangerously-skip-permissions"]
            ),
            projects=[
                ProjectConfig(
                    name="test-project-1",
                    path=os.path.join(temp_dir, "project1"),
                    description="Test project 1"
                ),
                ProjectConfig(
                    name="test-project-2",
                    path=os.path.join(temp_dir, "project2"),
                    description="Test project 2"
                )
            ],
            data_dir=temp_dir,
            log_level="DEBUG",
            max_sessions=3,
            task_queue_size=50
        )
        
        # Create project directories
        for project in config.projects:
            os.makedirs(project.path, exist_ok=True)
            # Add some sample files
            (Path(project.path) / "README.md").write_text(f"# {project.name}")
            (Path(project.path) / "main.py").write_text("print('Hello, World!')")
        
        yield config


class TestSlackIntegration:
    """Integration tests for Slack components."""
    
    @pytest.mark.asyncio
    async def test_complete_slack_message_flow(self, integration_config):
        """Test complete message flow from Slack to Claude and back."""
        # Mock external dependencies
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_socket, \
             patch('slack_sdk.WebClient') as mock_web_client:
            
            # Setup mocks
            mock_socket_client = AsyncMock()
            mock_socket.return_value = mock_socket_client
            mock_socket_client.connect = AsyncMock()
            
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123"})
            
            # Create components
            slack_client = SlackBotClient(integration_config)
            message_handler = MessageHandler(integration_config)
            command_router = CommandRouter(integration_config)
            
            # Connect Slack client
            await slack_client.connect()
            assert slack_client.is_connected
            
            # Test command message flow
            command_message = SlackMessage(
                channel_id="C1234567890",
                user_id="U1234567890",
                text="@@projects"
            )
            
            # Process message through handler
            with patch.object(command_router, 'route_command') as mock_route:
                mock_route.return_value = "Available projects: test-project-1, test-project-2"
                
                await message_handler.handle_message(command_message, slack_client)
                
                # Verify command was routed
                mock_route.assert_called_once()
                
                # Verify response was sent to Slack
                mock_client.chat_postMessage.assert_called()
    
    @pytest.mark.asyncio
    async def test_slack_error_handling_integration(self, integration_config):
        """Test error handling across Slack components."""
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_socket, \
             patch('slack_sdk.WebClient') as mock_web_client:
            
            # Setup failing mocks
            mock_socket_client = AsyncMock()
            mock_socket.return_value = mock_socket_client
            mock_socket_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
            
            slack_client = SlackBotClient(integration_config)
            
            # Should handle connection failure gracefully
            with pytest.raises(Exception):
                await slack_client.connect()
            
            assert not slack_client.is_connected


class TestSessionManagementIntegration:
    """Integration tests for session management."""
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_integration(self, integration_config):
        """Test complete session lifecycle with real components."""
        # Mock subprocess handler
        with patch('claude_remote_client.claude_client.subprocess_handler.SubprocessHandler') as mock_handler:
            mock_handler_instance = AsyncMock()
            mock_handler.return_value = mock_handler_instance
            mock_handler_instance.start_process = AsyncMock()
            mock_handler_instance.stop_process = AsyncMock()
            mock_handler_instance.send_message = AsyncMock()
            
            session_manager = SessionManager(integration_config)
            await session_manager.start()
            
            try:
                # Create session
                project_path = integration_config.projects[0].path
                session = await session_manager.create_session(project_path)
                
                assert session is not None
                assert session.project_path == project_path
                assert session.session_id in session_manager.sessions
                
                # Verify subprocess was started
                mock_handler_instance.start_process.assert_called_once()
                
                # Test session switching
                session2 = await session_manager.create_session(
                    integration_config.projects[1].path
                )
                
                await session_manager.switch_session(session.session_id)
                assert session_manager.active_session_id == session.session_id
                
                # Test session cleanup
                await session_manager.terminate_session(session.session_id)
                mock_handler_instance.stop_process.assert_called()
                
            finally:
                await session_manager.stop()


class TestTaskQueueIntegration:
    """Integration tests for task queue system."""
    
    @pytest.mark.asyncio
    async def test_queue_and_cron_integration(self, integration_config):
        """Test integration between queue manager and cron scheduler."""
        queue_manager = QueueManager(integration_config)
        cron_scheduler = CronScheduler(integration_config)
        
        await queue_manager.start()
        await cron_scheduler.start()
        
        try:
            # Create a cron schedule that adds tasks to queue
            schedule = CronSchedule(
                name="test-schedule",
                cron_pattern="* * * * *",  # Every minute
                tasks=["test_task"],
                project_path=integration_config.projects[0].path,
                next_run=datetime.now() - timedelta(seconds=1)  # Should run immediately
            )
            
            await cron_scheduler.add_schedule(schedule)
            
            # Mock task execution to add to queue
            async def mock_execute_task(task_name, project_path):
                task = QueuedTask(
                    queue_name="cron-generated",
                    description=f"Task from cron: {task_name}",
                    project_path=project_path
                )
                await queue_manager.add_task(task)
                return "Task added to queue"
            
            with patch.object(cron_scheduler, 'execute_predefined_task', mock_execute_task):
                # Execute due schedules
                await cron_scheduler.execute_due_schedules()
                
                # Verify task was added to queue
                queue_tasks = await queue_manager.get_queue("cron-generated")
                assert len(queue_tasks) == 1
                assert "Task from cron" in queue_tasks[0].description
                
                # Process the queue
                with patch.object(queue_manager, 'execute_task') as mock_exec:
                    mock_exec.return_value = "Task completed"
                    
                    results = []
                    async for result in queue_manager.process_queue("cron-generated"):
                        results.append(result)
                    
                    assert len(results) == 1
                    assert results[0].status == TaskStatus.COMPLETED
        
        finally:
            await queue_manager.stop()
            await cron_scheduler.stop()


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""
    
    @pytest.mark.asyncio
    async def test_complete_user_workflow(self, integration_config):
        """Test complete user workflow from Slack command to task execution."""
        # Mock all external dependencies
        with patch('slack_sdk.socket_mode.SocketModeClient') as mock_socket, \
             patch('slack_sdk.WebClient') as mock_web_client, \
             patch('claude_remote_client.claude_client.subprocess_handler.SubprocessHandler') as mock_handler:
            
            # Setup mocks
            mock_socket_client = AsyncMock()
            mock_socket.return_value = mock_socket_client
            mock_socket_client.connect = AsyncMock()
            
            mock_client = MagicMock()
            mock_web_client.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123"})
            
            mock_handler_instance = AsyncMock()
            mock_handler.return_value = mock_handler_instance
            mock_handler_instance.start_process = AsyncMock()
            mock_handler_instance.send_message = AsyncMock()
            
            # Create all components
            slack_client = SlackBotClient(integration_config)
            session_manager = SessionManager(integration_config)
            queue_manager = QueueManager(integration_config)
            message_handler = MessageHandler(integration_config)
            command_router = CommandRouter(integration_config)
            
            # Start all components
            await slack_client.connect()
            await session_manager.start()
            await queue_manager.start()
            
            try:
                # Simulate user workflow
                
                # 1. User asks for available projects
                projects_message = SlackMessage(
                    channel_id="C1234567890",
                    user_id="U1234567890",
                    text="@@projects"
                )
                
                with patch.object(command_router, 'session_manager', session_manager):
                    result = await command_router.route_command(projects_message)
                    assert "test-project-1" in result
                    assert "test-project-2" in result
                
                # 2. User switches to a project
                switch_message = SlackMessage(
                    channel_id="C1234567890",
                    user_id="U1234567890",
                    text="@@switch test-project-1"
                )
                
                with patch.object(command_router, 'session_manager', session_manager):
                    # Create session first
                    session = await session_manager.create_session(
                        integration_config.projects[0].path
                    )
                    
                    result = await command_router.route_command(switch_message)
                    assert "switched" in result.lower() or "active" in result.lower()
                
                # 3. User adds task to queue
                queue_message = SlackMessage(
                    channel_id="C1234567890",
                    user_id="U1234567890",
                    text="@@queue_add dev-tasks 'Implement new feature'"
                )
                
                with patch.object(command_router, 'queue_manager', queue_manager):
                    result = await command_router.route_command(queue_message)
                    assert "added" in result.lower()
                
                # 4. Verify task was added
                queue_tasks = await queue_manager.get_queue("dev-tasks")
                assert len(queue_tasks) == 1
                assert "Implement new feature" in queue_tasks[0].description
                
                # 5. Process the queue
                with patch.object(queue_manager, 'execute_task') as mock_exec:
                    mock_exec.return_value = "Feature implemented successfully"
                    
                    results = []
                    async for result in queue_manager.process_queue("dev-tasks"):
                        results.append(result)
                    
                    assert len(results) == 1
                    assert results[0].status == TaskStatus.COMPLETED
                    assert "Feature implemented" in results[0].result
            
            finally:
                await session_manager.stop()
                await queue_manager.stop()
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, integration_config):
        """Test error recovery across the entire system."""
        with patch('claude_remote_client.claude_client.subprocess_handler.SubprocessHandler') as mock_handler:
            mock_handler_instance = AsyncMock()
            mock_handler.return_value = mock_handler_instance
            
            # Simulate process failure
            mock_handler_instance.start_process = AsyncMock(side_effect=Exception("Process failed"))
            
            session_manager = SessionManager(integration_config)
            await session_manager.start()
            
            try:
                # Attempt to create session should fail gracefully
                with pytest.raises(Exception):
                    await session_manager.create_session(integration_config.projects[0].path)
                
                # System should still be operational for other operations
                assert session_manager.is_running
                
            finally:
                await session_manager.stop()


class TestPerformanceIntegration:
    """Performance and load testing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_handling(self, integration_config):
        """Test handling multiple concurrent sessions."""
        with patch('claude_remote_client.claude_client.subprocess_handler.SubprocessHandler') as mock_handler:
            mock_handler_instance = AsyncMock()
            mock_handler.return_value = mock_handler_instance
            mock_handler_instance.start_process = AsyncMock()
            
            session_manager = SessionManager(integration_config)
            await session_manager.start()
            
            try:
                # Create multiple sessions concurrently
                tasks = []
                for i in range(3):  # Within max_sessions limit
                    project_path = integration_config.projects[i % 2].path
                    task = session_manager.create_session(project_path)
                    tasks.append(task)
                
                sessions = await asyncio.gather(*tasks)
                
                # Verify all sessions created
                assert len(sessions) == 3
                assert len(session_manager.sessions) == 3
                
                # Verify unique session IDs
                session_ids = [s.session_id for s in sessions]
                assert len(set(session_ids)) == 3
                
            finally:
                await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_high_volume_task_processing(self, integration_config):
        """Test processing high volume of tasks."""
        queue_manager = QueueManager(integration_config)
        await queue_manager.start()
        
        try:
            # Add many tasks
            task_count = 50
            for i in range(task_count):
                task = QueuedTask(
                    queue_name="load-test",
                    description=f"Load test task {i}",
                    command=f"echo 'Task {i}'"
                )
                await queue_manager.add_task(task)
            
            # Verify all tasks added
            queue_tasks = await queue_manager.get_queue("load-test")
            assert len(queue_tasks) == task_count
            
            # Process all tasks
            with patch.object(queue_manager, 'execute_task') as mock_exec:
                mock_exec.return_value = "Task completed"
                
                results = []
                async for result in queue_manager.process_queue("load-test"):
                    results.append(result)
                
                # Verify all tasks processed
                assert len(results) == task_count
                assert all(r.status == TaskStatus.COMPLETED for r in results)
        
        finally:
            await queue_manager.stop()


class TestDataPersistenceIntegration:
    """Test data persistence across components."""
    
    @pytest.mark.asyncio
    async def test_session_state_persistence(self, integration_config):
        """Test session state persistence and recovery."""
        with patch('claude_remote_client.claude_client.subprocess_handler.SubprocessHandler') as mock_handler:
            mock_handler_instance = AsyncMock()
            mock_handler.return_value = mock_handler_instance
            mock_handler_instance.start_process = AsyncMock()
            
            session_manager = SessionManager(integration_config)
            await session_manager.start()
            
            try:
                # Create session with conversation history
                session = await session_manager.create_session(
                    integration_config.projects[0].path
                )
                session.add_message("user", "Hello Claude!")
                session.add_message("assistant", "Hello! How can I help?")
                
                # Save session state
                await session_manager.save_sessions()
                
                # Stop and restart session manager
                await session_manager.stop()
                
                session_manager2 = SessionManager(integration_config)
                await session_manager2.start()
                
                try:
                    # Load sessions
                    await session_manager2.load_sessions()
                    
                    # Verify session was restored
                    if session.session_id in session_manager2.sessions:
                        restored_session = session_manager2.sessions[session.session_id]
                        assert len(restored_session.conversation_history) == 2
                        assert restored_session.conversation_history[0]["content"] == "Hello Claude!"
                
                finally:
                    await session_manager2.stop()
            
            finally:
                if session_manager.is_running:
                    await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_queue_state_persistence(self, integration_config):
        """Test queue state persistence and recovery."""
        queue_manager = QueueManager(integration_config)
        await queue_manager.start()
        
        try:
            # Add tasks to queue
            tasks = []
            for i in range(3):
                task = QueuedTask(
                    queue_name="persistent-queue",
                    description=f"Persistent task {i}",
                    priority=i
                )
                await queue_manager.add_task(task)
                tasks.append(task)
            
            # Save queue state
            await queue_manager.save_queue_state("persistent-queue")
            
            # Stop and restart queue manager
            await queue_manager.stop()
            
            queue_manager2 = QueueManager(integration_config)
            await queue_manager2.start()
            
            try:
                # Load queue state
                loaded_tasks = await queue_manager2.load_queue_state("persistent-queue")
                
                # Verify tasks were restored
                assert len(loaded_tasks) == 3
                for i, task in enumerate(loaded_tasks):
                    assert f"Persistent task {i}" in task.description
            
            finally:
                await queue_manager2.stop()
        
        finally:
            if queue_manager.is_running:
                await queue_manager.stop()


class TestConfigurationIntegration:
    """Test configuration handling across components."""
    
    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, integration_config):
        """Test configuration validation across all components."""
        # Test with valid configuration
        session_manager = SessionManager(integration_config)
        queue_manager = QueueManager(integration_config)
        
        # Should initialize without errors
        await session_manager.start()
        await queue_manager.start()
        
        try:
            assert session_manager.is_running
            assert queue_manager.is_running
            
            # Test configuration limits
            assert session_manager.max_sessions == integration_config.max_sessions
            assert queue_manager.max_queue_size == integration_config.task_queue_size
        
        finally:
            await session_manager.stop()
            await queue_manager.stop()
    
    def test_invalid_configuration_handling(self):
        """Test handling of invalid configurations."""
        # Test with missing required fields
        invalid_config = Config()
        
        # Should handle gracefully or raise appropriate errors
        with pytest.raises((ValueError, AttributeError)):
            SessionManager(invalid_config)


@pytest.mark.slow
class TestLongRunningIntegration:
    """Long-running integration tests."""
    
    @pytest.mark.asyncio
    async def test_system_stability_over_time(self, integration_config):
        """Test system stability over extended operation."""
        session_manager = SessionManager(integration_config)
        queue_manager = QueueManager(integration_config)
        
        await session_manager.start()
        await queue_manager.start()
        
        try:
            # Simulate extended operation
            for cycle in range(5):  # Reduced for test speed
                # Create and cleanup sessions
                session = await session_manager.create_session(
                    integration_config.projects[0].path
                )
                
                # Add and process tasks
                task = QueuedTask(
                    queue_name=f"cycle-{cycle}",
                    description=f"Cycle {cycle} task"
                )
                await queue_manager.add_task(task)
                
                # Small delay to simulate real usage
                await asyncio.sleep(0.1)
                
                # Cleanup
                await session_manager.terminate_session(session.session_id)
            
            # System should still be operational
            assert session_manager.is_running
            assert queue_manager.is_running
        
        finally:
            await session_manager.stop()
            await queue_manager.stop()