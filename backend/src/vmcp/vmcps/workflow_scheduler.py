"""
Workflow Scheduler Service

Background service that executes scheduled workflows from all sandboxes.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from vmcp.vmcps.sandbox_service import get_sandbox_service, SandboxService
from vmcp.vmcps.vmcp_config_manager.custom_tool_engines.sandbox_tool import execute_sandbox_discovered_tool
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class WorkflowScheduler:
    """
    Background service that executes scheduled workflows.
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running_workflows: Dict[str, asyncio.Task] = {}
        self.sandbox_service = get_sandbox_service()
        self._initialized = False
    
    async def start(self):
        """Start the scheduler and load all workflows."""
        if self._initialized:
            return
        
        logger.info("Starting workflow scheduler...")
        
        # Load all workflows from all sandboxes
        await self._load_all_workflows()
        
        # Start scheduler
        self.scheduler.start()
        self._initialized = True
        
        logger.info("Workflow scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self._initialized:
            return
        
        logger.info("Stopping workflow scheduler...")
        self.scheduler.shutdown()
        
        # Cancel running workflows
        for task in self.running_workflows.values():
            task.cancel()
        
        self._initialized = False
        logger.info("Workflow scheduler stopped")
    
    async def _load_all_workflows(self):
        """Load workflows from all sandbox directories."""
        sandbox_base = SandboxService.SANDBOX_BASE
        
        if not sandbox_base.exists():
            return
        
        # Scan all sandbox directories
        for sandbox_dir in sandbox_base.iterdir():
            if not sandbox_dir.is_dir():
                continue
            
            # Try to get vmcp_id from config
            config_file = sandbox_dir / ".vmcp-config.json"
            if not config_file.exists():
                continue
            
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    vmcp_id = config.get('vmcp_id')
                    
                    if vmcp_id:
                        await self._load_workflows_for_sandbox(sandbox_dir, vmcp_id)
            except Exception as e:
                logger.warning(f"Failed to load workflows from {sandbox_dir}: {e}")
    
    async def _load_workflows_for_sandbox(self, sandbox_path: Path, vmcp_id: str):
        """Load and schedule workflows for a specific sandbox."""
        from vmcp.vmcps.sandbox_service import WorkflowManager
        
        manager = WorkflowManager(sandbox_path, vmcp_id)
        workflows = manager.list_workflows()
        
        for workflow in workflows:
            if not workflow.get('enabled', True):
                continue
            
            workflow_id = f"{vmcp_id}_{workflow['workflow_name']}"
            schedule = workflow.get('schedule', 'daily')
            
            # Create trigger based on schedule
            trigger = self._parse_schedule(schedule)
            if not trigger:
                logger.warning(f"Invalid schedule for workflow {workflow_id}: {schedule}")
                continue
            
            # Schedule workflow
            self.scheduler.add_job(
                self._execute_workflow,
                trigger=trigger,
                id=workflow_id,
                args=[vmcp_id, workflow['workflow_name'], workflow['script_path']],
                replace_existing=True
            )
            
            logger.info(f"Scheduled workflow: {workflow_id} with schedule: {schedule}")
    
    def _parse_schedule(self, schedule: str):
        """Parse schedule string into APScheduler trigger."""
        schedule_lower = schedule.lower().strip()
        
        if schedule_lower == 'once':
            # Run once immediately (not scheduled)
            return None
        
        elif schedule_lower == 'hourly':
            return IntervalTrigger(hours=1)
        
        elif schedule_lower == 'daily':
            return CronTrigger(hour=0, minute=0)  # Midnight
        
        elif schedule_lower.startswith('cron:'):
            # Parse cron expression: "cron:0 0 * * *"
            cron_expr = schedule_lower[5:].strip()
            parts = cron_expr.split()
            if len(parts) == 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                )
        
        # Try to parse as direct cron expression
        try:
            parts = schedule.split()
            if len(parts) == 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                )
        except Exception:
            pass
        
        return None
    
    async def _execute_workflow(
        self,
        vmcp_id: str,
        workflow_name: str,
        script_path: str
    ):
        """Execute a workflow script."""
        workflow_id = f"{vmcp_id}_{workflow_name}"
        
        # Check if already running
        if workflow_id in self.running_workflows:
            logger.warning(f"Workflow {workflow_id} is already running, skipping")
            return
        
        logger.info(f"Executing workflow: {workflow_id}")
        
        # Create task for workflow execution
        task = asyncio.create_task(
            self._run_workflow(vmcp_id, workflow_name, script_path)
        )
        self.running_workflows[workflow_id] = task
        
        try:
            await task
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_id}: {e}")
        finally:
            self.running_workflows.pop(workflow_id, None)
    
    async def _run_workflow(
        self,
        vmcp_id: str,
        workflow_name: str,
        script_path: str
    ):
        """Run workflow script in sandbox environment."""
        try:
            # Use the same execution path as sandbox-discovered tools
            result = await execute_sandbox_discovered_tool(
                vmcp_id=vmcp_id,
                script_path=script_path,
                arguments={},  # Workflows typically don't take arguments
                environment_variables={},
                tool_as_prompt=False
            )
            
            # Update last_run timestamp
            from vmcp.vmcps.sandbox_service import WorkflowManager
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
            manager = WorkflowManager(sandbox_path, vmcp_id)
            
            schedule_data = manager._load_schedule()
            workflow_id = f"{vmcp_id}_{workflow_name}"
            if workflow_id in schedule_data:
                schedule_data[workflow_id]['last_run'] = datetime.now().isoformat()
                manager._save_schedule(schedule_data)
            
            logger.info(f"Workflow {workflow_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error running workflow {vmcp_id}_{workflow_name}: {e}")


# Singleton instance
_workflow_scheduler: Optional[WorkflowScheduler] = None


def get_workflow_scheduler() -> WorkflowScheduler:
    """Get the singleton workflow scheduler instance."""
    global _workflow_scheduler
    if _workflow_scheduler is None:
        _workflow_scheduler = WorkflowScheduler()
    return _workflow_scheduler

