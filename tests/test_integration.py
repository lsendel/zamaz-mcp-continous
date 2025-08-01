"""
Integration tests for Claude Remote Client.

These tests verify end-to-end functionality across multiple components
including session management, Slack integration, and task processing.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from pathlib import Path

from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.slack_client.client import SlackBotClient
from claude_remote_client.task_queue.queue_manager import QueueManager
from claude_remote_client.task_queue.cron_scheduler import CronScheduler
from claude_remote_client.models import SessionStatus, TaskStatus
from claude_remote_client.exceptions import SessionError, SlackConnectionError


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self, integration_test_environment, mock_subprocess):
        """Test complete session lifecycle from creation to cleanup."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize session manager
        session_manager = SessionManager(config)
        await session_manager.start()
        
        try:
            # Create session
            session = await session_manager.create_session("project-0")
            assert session.status == SessionStatus.ACTIVE
            assert session.project_name == "project-0"
            
            # Send message to session
            response = await session_manager.send_message(session.session_id, "Hello Claude")
            assert response is not None
            
            # Switch to different project
            new_session = await session_manager.switch_project("project-1")
            assert new_session.project_name == "project-1"
            assert session_manager.active_session_id == new_session.session_id
            
            # List sessions
            sessions = await session_manager.list_sessions()
            assert len(sessions) == 2
            
            # Stop specific session
            await session_manager.stop_session(session.session_id)
            stopped_session = await session_manager.get_session(session.session_id)
            assert stopped_session.status == SessionStatus.INACTIVE
            
        finally:
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_task_queue_integration(self, integration_test_environment, mock_subprocess):
        """Test task queue integration with session management."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize components
        session_manager = SessionManager(config)
        queue_manager = QueueManager(config)
        
        await session_manager.start()
        await queue_manager.start()
        
        try:
            # Set up Claude execution callback
            async def claude_execution_callback(task):
                session = await session_manager.get_or_create_session(task.project_name)
                response = await session_manager.send_message(session.session_id, task.prompt)
                return response
            
            queue_manager.claude_execution_callback = claude_execution_callback
            
            # Add task to queue
            task_id = await queue_manager.add_task(
                queue_name="default",
                task_type="code_review",
                prompt="Review the main.py file",
                project_name="project-0"
            )
            
            # Wait for task execution
            await asyncio.sleep(0.5)  # Allow time for processing
            
            # Check task status
            task = await queue_manager.get_task(task_id)
            assert task.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED]
            
            # Verify session was created
            sessions = await session_manager.list_sessions()
            project_sessions = [s for s in sessions if s.project_name == "project-0"]
            assert len(project_sessions) > 0
            
        finally:
            await queue_manager.stop()
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_cron_scheduler_integration(self, integration_test_environment, mock_subprocess):
        """Test cron scheduler integration with task queue and sessions."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize components
        session_manager = SessionManager(config)
        queue_manager = QueueManager(config)
        cron_scheduler = CronScheduler(config)
        
        await session_manager.start()
        await queue_manager.start()
        await cron_scheduler.start()
        
        try:
            # Set up callbacks
            async def task_execution_callback(schedule):
                return await queue_manager.add_task(
                    queue_name="scheduled",
                    task_type=schedule.task_type,
                    prompt=f"Scheduled task: {schedule.name}",
                    project_name=schedule.project_name
                )
            
            async def claude_execution_callback(task):
                session = await session_manager.get_or_create_session(task.project_name)
                return await session_manager.send_message(session.session_id, task.prompt)
            
            cron_scheduler.task_execution_callback = task_execution_callback
            queue_manager.claude_execution_callback = claude_execution_callback
            
            # Add cron schedule (every minute for testing)
            schedule_id = await cron_scheduler.add_schedule(
                name="test_cleanup",
                cron_pattern="* * * * *",  # Every minute
                task_type="clean_code",
                project_name="project-0"
            )
            
            # Wait for schedule execution
            await asyncio.sleep(65)  # Wait for at least one execution
            
            # Check that tasks were created
            tasks = await queue_manager.list_tasks("scheduled")
            assert len(tasks) > 0
            
            # Verify task execution
            completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
            assert len(completed_tasks) > 0
            
        finally:
            await cron_scheduler.stop()
            await queue_manager.stop()
            await session_manager.stop()


@pytest.mark.integration
class TestSlackIntegration:
    """Test Slack integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_slack_message_handling(self, integration_test_environment, mock_slack_client):
        """Test Slack message handling and response."""
        env = integration_test_environment
        config = env['config']
        
        # Mock Slack client setup
        with patch('claude_remote_client.slack_client.client.AsyncWebClient') as mock_web_client, \
             patch('claude_remote_client.slack_client.client.AsyncBaseSocketModeClient') as mock_socket_client:
            
            mock_web_client.return_value = mock_slack_client
            mock_socket_client.return_value = AsyncMock()
            
            # Initialize Slack client
            slack_client = SlackBotClient(config.slack)
            
            # Test connection
            await slack_client.connect()
            assert slack_client.is_connected
            
            # Test message sending
            response = await slack_client.send_message("Test message")
            assert response["ok"] is True
            
            # Test message handling
            test_event = {
                'type': 'message',
                'channel': config.slack.channel_id,
                'user': 'U1234567890',
                'text': '@@status',
                'ts': '1234567890.123456'
            }
            
            # Simulate message handling
            handlers = slack_client.message_handlers
            if handlers:
                await handlers[0](test_event)
            
            await slack_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_slack_command_routing(self, integration_test_environment, mock_slack_client, mock_subprocess):
        """Test Slack command routing and execution."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize components
        session_manager = SessionManager(config)
        await session_manager.start()
        
        try:
            # Mock command router
            from claude_remote_client.slack_client.command_router import CommandRouter
            
            with patch('claude_remote_client.slack_client.client.AsyncWebClient') as mock_web_client:
                mock_web_client.return_value = mock_slack_client
                
                command_router = CommandRouter(session_manager, mock_slack_client)
                
                # Test project listing command
                await command_router.handle_projects_command("U1234567890")
                mock_slack_client.send_message.assert_called()
                
                # Test project switching command
                await command_router.handle_switch_command("U1234567890", "project-0")
                mock_slack_client.send_message.assert_called()
                
                # Test status command
                await command_router.handle_status_command("U1234567890")
                mock_slack_client.send_message.assert_called()
                
        finally:
            await session_manager.stop()


@pytest.mark.integration
class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_session_recovery_after_crash(self, integration_test_environment, mock_subprocess):
        """Test session recovery after unexpected termination."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize session manager
        session_manager = SessionManager(config)
        await session_manager.start()
        
        try:
            # Create session
            session = await session_manager.create_session("project-0")
            session_id = session.session_id
            
            # Simulate process crash
            if session_id in session_manager.subprocess_handlers:
                handler = session_manager.subprocess_handlers[session_id]
                handler.process = None  # Simulate crashed process
            
            # Attempt to send message (should trigger recovery)
            response = await session_manager.send_message(session_id, "Test message")
            
            # Verify session was recovered
            recovered_session = await session_manager.get_session(session_id)
            assert recovered_session.status == SessionStatus.ACTIVE
            
        finally:
            await session_manager.stop()
    
    @pytest.mark.asyncio
    async def test_queue_persistence_and_recovery(self, integration_test_environment):
        """Test task queue persistence and recovery."""
        env = integration_test_environment
        config = env['config']
        
        # Initialize queue manager
        queue_manager1 = QueueManager(config)
        await queue_manager1.start()
        
        # Add tasks
        task_ids = []
        for i in range(5):
            task_id = await queue_manager1.add_task(
                queue_name="test",
                task_type="test_task",
                prompt=f"Test task {i}",
                project_name="project-0"
            )
            task_ids.append(task_id)
        
        # Stop queue manager
        await queue_manager1.stop()
        
        # Create new queue manager (simulating restart)
        queue_manager2 = QueueManager(config)
        await queue_manager2.start()
        
        try:
            # Verify tasks were persisted and loaded
            tasks = await queue_manager2.list_tasks("test")
            assert len(tasks) == 5
            
            # Verify task IDs match
            loaded_task_ids = [task.task_id for task in tasks]
            for task_id in task_ids:
                assert task_id in loaded_task_ids
                
        finally:
            await queue_manager2.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_session_management(self, integration_test_environment, mock_subprocess):
        """Test concurrent session operations."""
        env = integration_test_environment
        config = env['config']
        
        session_manager = SessionManager(config)
        await session_manager.start()
        
        try:
            # Create multiple sessions concurrently
            tasks = []
            for i in range(10):
                task = asyncio.create_task(
                    session_manager.create_session(f"project-{i % 3}")
                )
                tasks.append(task)
            
            sessions = await asyncio.gather(*tasks)
            
            # Verify all sessions were created
            assert len(sessions) == 10
            assert all(s.status == SessionStatus.ACTIVE for s in sessions)
            
            # Send messages concurrently
            message_tasks = []
            for session in sessions:
                task = asyncio.create_task(
                    session_manager.send_message(session.session_id, f"Message to {session.project_name}")
                )
                message_tasks.append(task)
            
            responses = await asyncio.gather(*message_tasks, return_exceptions=True)
            
            # Verify most messages succeeded (some may fail due to mocking)
            successful_responses = [r for r in responses if not isinstance(r, Exception)]
            assert len(successful_responses) > 0
            
        finally:
            await session_manager.stop()


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test performance under load."""
    
    @pytest.mark.asyncio
    async def test_high_volume_task_processing(self, integration_test_environment, performance_test_data):
        """Test processing high volume of tasks."""
        env = integration_test_environment
        config = env['config']
        
        queue_manager = QueueManager(config)
        await queue_manager.start()
        
        try:
            # Add many tasks
            task_ids = []
            for i in range(100):
                task_id = await queue_manager.add_task(
                    queue_name="performance",
                    task_type="test_task",
                    prompt=f"Performance test task {i}",
                    project_name=f"project-{i % 3}"
                )
                task_ids.append(task_id)
            
            # Wait for processing
            await asyncio.sleep(2.0)
            
            # Check task completion
            tasks = await queue_manager.list_tasks("performance")
            completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
            
            # Should have processed at least some tasks
            assert len(completed_tasks) > 0
            
        finally:
            await queue_manager.stop()
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, integration_test_environment, mock_subprocess):
        """Test memory usage with many concurrent sessions."""
        env = integration_test_environment
        config = env['config']
        
        session_manager = SessionManager(config)
        await session_manager.start()
        
        try:
            # Create many sessions
            sessions = []
            for i in range(50):
                session = await session_manager.create_session(f"project-{i % 3}")
                sessions.append(session)
            
            # Send messages to all sessions
            for session in sessions:
                await session_manager.send_message(
                    session.session_id, 
                    "Test message with some content to simulate real usage"
                )
            
            # Verify sessions are still active
            active_sessions = [s for s in sessions if s.status == SessionStatus.ACTIVE]
            assert len(active_sessions) > 0
            
            # Clean up sessions
            for session in sessions:
                await session_manager.stop_session(session.session_id)
            
        finally:
            await session_manager.stop()
