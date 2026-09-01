"""
Celery Background Tasks for Workflow Automation & Operations Engine
===================================================================
Executes periodic asynchronous jobs:
- Checking and resuming expired durable wait timers
- Dispatching asynchronous trigger events to matching workflow definitions
- Reconciling stuck workflow executions after worker restarts
"""

import asyncio
import logging
from typing import List, Dict, Any

from app.celery_app import celery_app
from app.database import async_session_factory
from app.modules.workflow.service import WorkflowService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker thread."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.modules.workflow.workers.workflow_tasks.process_due_workflow_waits_task", queue="workflow-timers")
def process_due_workflow_waits_task():
    """Checks and resumes workflow instances whose wait deadlines have elapsed (every 1 min)."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info("[WORKFLOW_TASK] Resolving due durable wait states...")
            service = WorkflowService(session)
            resumed = await service.resolve_due_waits()
            logger.info(f"[WORKFLOW_TASK] Resumed {len(resumed)} due wait instance(s).")
            return {"status": "SUCCESS", "resumed_count": len(resumed)}

    return _run_async(_runner())


@celery_app.task(name="app.modules.workflow.workers.workflow_tasks.dispatch_workflow_trigger_task", queue="workflow-trigger")
def dispatch_workflow_trigger_task(trigger_type: str, entity_id: str, organization_id: str, payload: Dict[str, Any]):
    """Dispatches an asynchronous trigger event to all matching published workflows."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info(f"[WORKFLOW_TASK] Dispatching trigger '{trigger_type}' for entity {entity_id}...")
            service = WorkflowService(session)
            defs = await service.list_definitions(organization_id, status="PUBLISHED")
            matching = [d for d in defs if d.trigger_type.lower() == trigger_type.lower()]

            count = 0
            for w in matching:
                try:
                    await service.execute_workflow(w.id, entity_id, organization_id, payload)
                    count += 1
                except Exception as e:
                    logger.error(f"[WORKFLOW_TASK] Failed to execute workflow {w.id} on trigger {trigger_type}: {e}")
            logger.info(f"[WORKFLOW_TASK] Executed {count} workflow(s) for trigger '{trigger_type}'.")
            return {"status": "SUCCESS", "triggered_count": count}

    return _run_async(_runner())
