"""
Cron scheduler for automated task execution.

This module handles cron-based scheduling of predefined tasks,
pattern parsing, and automated execution with Claude integration.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import re
import aiofiles
import aiofiles.os

from ..models import CronSchedule, QueuedTask, TaskStatus
from ..config import Config
from ..exceptions import CronScheduleError
from ..utils import setup_logging, ensure_directory_exists


class CronScheduler:
    """
    Scheduler for cron-based automated task execution.
    
    Handles cron pattern parsing, schedule management, and automated
    execution of predefined tasks with Claude integration.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the cron scheduler.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = setup_logging()
        
        # Schedule storage
        self.schedules: Dict[str, CronSchedule] = {}
        
        # Schedule persistence
        self.schedules_file = Path(config.data_dir) / "cron_schedules.json"
        
        # Predefined tasks
        self.predefined_tasks = {
            "clean_code": "Clean and format code files",
            "run_tests": "Run project test suite",
            "code_review": "Perform automated code review",
            "update_deps": "Check and update dependencies",
            "security_scan": "Run security vulnerability scan",
            "performance_check": "Analyze performance metrics",
            "documentation_update": "Update README and documentation"
        }
        
        # Background scheduling
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Callbacks for execution
        self.task_execution_callback = None
        self.slack_notification_callback = None
        
        # Ensure data directory exists
        ensure_directory_exists(config.data_dir)
        
        # Load existing schedules
        self._load_schedules()
    
    async def start(self) -> None:
        """Start the cron scheduler and background execution."""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info("Starting cron scheduler...")
        
        # Start background scheduler task
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info("Cron scheduler started")
    
    async def stop(self) -> None:
        """Stop the cron scheduler and cleanup."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("Stopping cron scheduler...")
        
        # Cancel background task
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Save schedule state
        self._save_schedules()
        
        self.logger.info("Cron scheduler stopped")
    
    def set_task_callback(self, callback) -> None:
        """
        Set callback for task execution.
        
        Args:
            callback: Async function that takes (task_name, project_path) and executes
        """
        self.task_execution_callback = callback
    
    def set_slack_callback(self, callback) -> None:
        """
        Set callback for Slack notifications.
        
        Args:
            callback: Async function that takes (channel, message) and sends to Slack
        """
        self.slack_notification_callback = callback 
   
    async def add_schedule(self, name: str, cron_pattern: str, tasks: List[str], 
                          project_path: str = "", enabled: bool = True) -> str:
        """
        Add a new cron schedule.
        
        Args:
            name: Schedule name
            cron_pattern: Cron pattern (e.g., "0 */2 * * *")
            tasks: List of predefined task names
            project_path: Optional project path for task context
            enabled: Whether schedule is enabled
        
        Returns:
            str: Schedule ID
        
        Raises:
            CronScheduleError: If schedule cannot be added
        """
        try:
            # Validate cron pattern
            if not self._validate_cron_pattern(cron_pattern):
                raise CronScheduleError(f"Invalid cron pattern: {cron_pattern}")
            
            # Validate tasks
            invalid_tasks = [task for task in tasks if task not in self.predefined_tasks]
            if invalid_tasks:
                raise CronScheduleError(f"Invalid tasks: {invalid_tasks}")
            
            # Create schedule
            schedule = CronSchedule(
                name=name,
                cron_pattern=cron_pattern,
                tasks=tasks,
                project_path=project_path,
                enabled=enabled
            )
            
            # Store schedule
            self.schedules[schedule.schedule_id] = schedule
            
            # Save schedules
            self._save_schedules()
            
            self.logger.info(f"Added cron schedule '{name}': {cron_pattern} -> {tasks}")
            
            # Notify via Slack
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"⏰ **Cron Schedule Added**\n"
                    f"• **Name:** `{name}`\n"
                    f"• **Pattern:** `{cron_pattern}`\n"
                    f"• **Tasks:** {', '.join(tasks)}\n"
                    f"• **Next Run:** {schedule.next_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.next_run else 'N/A'}"
                )
            
            return schedule.schedule_id
        
        except Exception as e:
            raise CronScheduleError(f"Failed to add schedule: {str(e)}")
    
    async def remove_schedule(self, schedule_id: str) -> bool:
        """
        Remove a cron schedule.
        
        Args:
            schedule_id: ID of schedule to remove
        
        Returns:
            bool: True if schedule was removed, False if not found
        """
        if schedule_id not in self.schedules:
            return False
        
        try:
            schedule = self.schedules[schedule_id]
            del self.schedules[schedule_id]
            
            # Save schedules
            self._save_schedules()
            
            self.logger.info(f"Removed cron schedule: {schedule.name}")
            
            # Notify via Slack
            if self.slack_notification_callback:
                await self.slack_notification_callback(
                    "general",
                    f"🗑️ **Cron Schedule Removed**\n"
                    f"• **Name:** `{schedule.name}`\n"
                    f"• **Pattern:** `{schedule.cron_pattern}`"
                )
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error removing schedule {schedule_id}: {e}")
            return False
    
    async def enable_schedule(self, schedule_id: str) -> bool:
        """
        Enable a cron schedule.
        
        Args:
            schedule_id: ID of schedule to enable
        
        Returns:
            bool: True if schedule was enabled, False if not found
        """
        if schedule_id not in self.schedules:
            return False
        
        schedule = self.schedules[schedule_id]
        schedule.enabled = True
        schedule.calculate_next_run()
        
        self._save_schedules()
        
        self.logger.info(f"Enabled cron schedule: {schedule.name}")
        return True
    
    async def disable_schedule(self, schedule_id: str) -> bool:
        """
        Disable a cron schedule.
        
        Args:
            schedule_id: ID of schedule to disable
        
        Returns:
            bool: True if schedule was disabled, False if not found
        """
        if schedule_id not in self.schedules:
            return False
        
        schedule = self.schedules[schedule_id]
        schedule.enabled = False
        
        self._save_schedules()
        
        self.logger.info(f"Disabled cron schedule: {schedule.name}")
        return True
    
    def get_schedules(self) -> List[Dict[str, Any]]:
        """
        Get all cron schedules.
        
        Returns:
            List[Dict[str, Any]]: List of schedule information
        """
        schedules = []
        
        for schedule in self.schedules.values():
            schedule_info = {
                "schedule_id": schedule.schedule_id,
                "name": schedule.name,
                "cron_pattern": schedule.cron_pattern,
                "tasks": schedule.tasks,
                "project_path": schedule.project_path,
                "enabled": schedule.enabled,
                "created_at": schedule.created_at.isoformat(),
                "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
                "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
                "run_count": schedule.run_count
            }
            schedules.append(schedule_info)
        
        # Sort by next run time
        schedules.sort(key=lambda s: s["next_run"] or "9999-12-31T23:59:59")
        
        return schedules
    
    def get_predefined_tasks(self) -> Dict[str, str]:
        """
        Get available predefined tasks.
        
        Returns:
            Dict[str, str]: Task name to description mapping
        """
        return self.predefined_tasks.copy()
    
    async def execute_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """
        Manually execute a cron schedule.
        
        Args:
            schedule_id: ID of schedule to execute
        
        Returns:
            Dict[str, Any]: Execution results
        
        Raises:
            CronScheduleError: If schedule cannot be executed
        """
        if schedule_id not in self.schedules:
            raise CronScheduleError(f"Schedule {schedule_id} not found")
        
        schedule = self.schedules[schedule_id]
        
        return await self._execute_schedule_tasks(schedule)
    
    def _validate_cron_pattern(self, pattern: str) -> bool:
        """
        Validate a cron pattern.
        
        Args:
            pattern: Cron pattern to validate
        
        Returns:
            bool: True if pattern is valid
        """
        # Simple validation for basic patterns
        # In a real implementation, you might use a library like croniter
        
        # Split pattern into parts
        parts = pattern.split()
        if len(parts) != 5:
            return False
        
        # Basic validation for each part
        minute, hour, day, month, weekday = parts
        
        # Validate ranges and special characters
        patterns = [
            (minute, 0, 59),    # Minutes: 0-59
            (hour, 0, 23),      # Hours: 0-23
            (day, 1, 31),       # Day of month: 1-31
            (month, 1, 12),     # Month: 1-12
            (weekday, 0, 7)     # Day of week: 0-7 (0 and 7 are Sunday)
        ]
        
        for part, min_val, max_val in patterns:
            if not self._validate_cron_part(part, min_val, max_val):
                return False
        
        return True
    
    def _validate_cron_part(self, part: str, min_val: int, max_val: int) -> bool:
        """
        Validate a single part of a cron pattern.
        
        Args:
            part: Cron part to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
        
        Returns:
            bool: True if part is valid
        """
        # Allow wildcard
        if part == "*":
            return True
        
        # Allow step values (e.g., */2)
        if part.startswith("*/"):
            try:
                step = int(part[2:])
                return step > 0
            except ValueError:
                return False
        
        # Allow ranges (e.g., 1-5)
        if "-" in part:
            try:
                start, end = part.split("-")
                start_val = int(start)
                end_val = int(end)
                return min_val <= start_val <= end_val <= max_val
            except ValueError:
                return False
        
        # Allow lists (e.g., 1,3,5)
        if "," in part:
            try:
                values = [int(v) for v in part.split(",")]
                return all(min_val <= v <= max_val for v in values)
            except ValueError:
                return False
        
        # Single value
        try:
            value = int(part)
            return min_val <= value <= max_val
        except ValueError:
            return False
    
    async def _scheduler_loop(self) -> None:
        """Background scheduler loop."""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check for schedules that should run
                await self._check_and_execute_schedules()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
    
    async def _check_and_execute_schedules(self) -> None:
        """Check for schedules that should run and execute them."""
        current_time = datetime.now()
        
        for schedule in self.schedules.values():
            if schedule.should_run():
                try:
                    self.logger.info(f"Executing scheduled tasks for: {schedule.name}")
                    
                    # Execute schedule
                    result = await self._execute_schedule_tasks(schedule)
                    
                    # Mark as executed
                    schedule.mark_executed()
                    
                    # Save updated schedule
                    self._save_schedules()
                    
                    self.logger.info(f"Completed scheduled execution for: {schedule.name}")
                
                except Exception as e:
                    self.logger.error(f"Error executing schedule {schedule.name}: {e}")
                    
                    # Notify error via Slack
                    if self.slack_notification_callback:
                        await self.slack_notification_callback(
                            "general",
                            f"❌ **Cron Schedule Failed**\n"
                            f"• **Name:** `{schedule.name}`\n"
                            f"• **Error:** {str(e)[:200]}..."
                        )
    
    async def _execute_schedule_tasks(self, schedule: CronSchedule) -> Dict[str, Any]:
        """
        Execute all tasks in a schedule.
        
        Args:
            schedule: Schedule to execute
        
        Returns:
            Dict[str, Any]: Execution results
        """
        if not self.task_execution_callback:
            raise CronScheduleError("Task execution callback not configured")
        
        results = {
            "schedule_id": schedule.schedule_id,
            "schedule_name": schedule.name,
            "executed_at": datetime.now().isoformat(),
            "tasks": []
        }
        
        # Notify start of execution
        if self.slack_notification_callback:
            await self.slack_notification_callback(
                "general",
                f"⏰ **Cron Schedule Executing**\n"
                f"• **Name:** `{schedule.name}`\n"
                f"• **Tasks:** {', '.join(schedule.tasks)}\n"
                f"• **Project:** `{schedule.project_path or 'Default'}`"
            )
        
        # Execute each task
        for task_name in schedule.tasks:
            try:
                task_description = self.predefined_tasks.get(task_name, task_name)
                
                self.logger.info(f"Executing task: {task_name}")
                
                # Execute task via callback
                task_result = await self.task_execution_callback(task_name, schedule.project_path)
                
                task_info = {
                    "task_name": task_name,
                    "description": task_description,
                    "status": "completed",
                    "result": str(task_result)[:500],  # Limit result size
                    "executed_at": datetime.now().isoformat()
                }
                
                results["tasks"].append(task_info)
                
                self.logger.info(f"Task {task_name} completed successfully")
            
            except Exception as e:
                task_info = {
                    "task_name": task_name,
                    "description": self.predefined_tasks.get(task_name, task_name),
                    "status": "failed",
                    "error": str(e)[:500],
                    "executed_at": datetime.now().isoformat()
                }
                
                results["tasks"].append(task_info)
                
                self.logger.error(f"Task {task_name} failed: {e}")
        
        # Notify completion
        if self.slack_notification_callback:
            successful_tasks = len([t for t in results["tasks"] if t["status"] == "completed"])
            failed_tasks = len([t for t in results["tasks"] if t["status"] == "failed"])
            
            await self.slack_notification_callback(
                "general",
                f"✅ **Cron Schedule Complete**\n"
                f"• **Name:** `{schedule.name}`\n"
                f"• **Successful:** {successful_tasks}\n"
                f"• **Failed:** {failed_tasks}\n"
                f"• **Next Run:** {schedule.next_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.next_run else 'N/A'}"
            )
        
        return results
    
    async def _load_schedules(self) -> None:
        """Load schedules from persistent storage."""
        if not await aiofiles.os.path.exists(self.schedules_file):
            return
        
        try:
            async with aiofiles.open(self.schedules_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)
            
            for schedule_data in data.get('schedules', []):
                schedule = CronSchedule(
                    schedule_id=schedule_data['schedule_id'],
                    name=schedule_data['name'],
                    cron_pattern=schedule_data['cron_pattern'],
                    tasks=schedule_data['tasks'],
                    project_path=schedule_data['project_path'],
                    enabled=schedule_data['enabled'],
                    created_at=datetime.fromisoformat(schedule_data['created_at']),
                    run_count=schedule_data.get('run_count', 0)
                )
                
                # Restore timestamps if available
                if schedule_data.get('last_run'):
                    schedule.last_run = datetime.fromisoformat(schedule_data['last_run'])
                if schedule_data.get('next_run'):
                    schedule.next_run = datetime.fromisoformat(schedule_data['next_run'])
                else:
                    schedule.calculate_next_run()
                
                self.schedules[schedule.schedule_id] = schedule
            
            self.logger.info(f"Loaded {len(self.schedules)} cron schedules from storage")
        
        except Exception as e:
            self.logger.error(f"Error loading schedules: {e}")
    
    async def _save_schedules(self) -> None:
        """Save schedules to persistent storage."""
        try:
            data = {
                'schedules': [],
                'last_updated': datetime.now().isoformat()
            }
            
            for schedule in self.schedules.values():
                schedule_data = {
                    'schedule_id': schedule.schedule_id,
                    'name': schedule.name,
                    'cron_pattern': schedule.cron_pattern,
                    'tasks': schedule.tasks,
                    'project_path': schedule.project_path,
                    'enabled': schedule.enabled,
                    'created_at': schedule.created_at.isoformat(),
                    'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                    'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                    'run_count': schedule.run_count
                }
                data['schedules'].append(schedule_data)
            
            async with aiofiles.open(self.schedules_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        
        except Exception as e:
            self.logger.error(f"Error saving schedules: {e}")
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cron scheduler.
        
        Returns:
            Dict[str, Any]: Scheduler statistics
        """
        enabled_schedules = len([s for s in self.schedules.values() if s.enabled])
        next_run_times = [s.next_run for s in self.schedules.values() if s.enabled and s.next_run]
        next_execution = min(next_run_times) if next_run_times else None
        
        return {
            "is_running": self.is_running,
            "total_schedules": len(self.schedules),
            "enabled_schedules": enabled_schedules,
            "disabled_schedules": len(self.schedules) - enabled_schedules,
            "next_execution": next_execution.isoformat() if next_execution else None,
            "predefined_tasks": len(self.predefined_tasks),
            "schedules_file": str(self.schedules_file),
            "task_callback_configured": self.task_execution_callback is not None,
            "slack_callback_configured": self.slack_notification_callback is not None
        }