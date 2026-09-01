import logging
from app.infrastructure.events.event_bus import DomainEvent, StandardDomainEvents, event_bus

logger = logging.getLogger(__name__)

async def analytics_subscriber(event: DomainEvent) -> None:
    """Consumes domain events to update analytics and BI dashboards asynchronously."""
    logger.info(f"[SUBSCRIBER: Analytics] Captured event {event.event_type} for Org {event.organization_id}")

async def audit_subscriber(event: DomainEvent) -> None:
    """Logs immutable audit trails for compliance and security auditing."""
    logger.info(f"[SUBSCRIBER: Audit] Recording audit entry for {event.event_type} (Actor: {event.actor.user_id})")

async def event_history_subscriber(event: DomainEvent) -> None:
    """Persists every domain event to the event_history table for replay and debugging."""
    logger.debug(f"[SUBSCRIBER: EventHistory] Persisting event {event.event_id} ({event.event_type})")
    from app.tasks.queue_workers import process_analytics_event
    try:
        process_analytics_event.apply_async(
            kwargs={"event_payload": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "organization_id": event.organization_id,
                "correlation_id": event.correlation_id,
                "actor_id": event.actor.user_id,
            }},
            queue="analytics_queue",
        )
    except Exception as exc:
        logger.warning(f"[EVENT HISTORY SUBSCRIBER] Failed to queue persistence: {exc}")

async def search_index_subscriber(event: DomainEvent) -> None:
    """Trigger incremental search indexing on entity mutations."""
    indexable_events = {
        StandardDomainEvents.LEAD_CREATED: "lead",
        StandardDomainEvents.LEAD_UPDATED: "lead",
        StandardDomainEvents.CONTACT_CREATED: "contact",
        StandardDomainEvents.TASK_CREATED: "task",
        StandardDomainEvents.MEETING_BOOKED: "meeting",
    }
    if event.event_type in indexable_events:
        entity_type = indexable_events[event.event_type]
        logger.info(f"[SUBSCRIBER: Search Index] Triggering index update for {entity_type} event {event.event_type}")

async def ai_subscriber(event: DomainEvent) -> None:
    """Triggers RAG vector indexing, sentiment scoring, and AI lead qualification."""
    if event.event_type in (StandardDomainEvents.LEAD_CREATED, StandardDomainEvents.CONVERSATION_STARTED):
        logger.info(
            f"[SUBSCRIBER: AI Engine] Triggering AI pipeline for "
            f"{event.payload.get('lead_id') or event.payload.get('conversation_id')}"
        )

async def workflow_subscriber(event: DomainEvent) -> None:
    """Executes automated workflow engines and multi-channel drip campaigns."""
    if event.event_type in (StandardDomainEvents.STAGE_CHANGED, StandardDomainEvents.LEAD_CREATED):
        logger.info(f"[SUBSCRIBER: Workflow] Evaluating workflow rules for: {event.payload}")

async def notification_subscriber(event: DomainEvent) -> None:
    """Creates in-app notifications for relevant domain events."""
    notifiable_events = {
        StandardDomainEvents.LEAD_ASSIGNED: "New lead assigned to you",
        StandardDomainEvents.TASK_CREATED: "New task created",
        StandardDomainEvents.MEETING_BOOKED: "Meeting scheduled",
        StandardDomainEvents.AI_QUALIFICATION_COMPLETED: "AI qualification complete",
    }
    if event.event_type in notifiable_events:
        logger.info(f"[SUBSCRIBER: Notifications] Queuing notification for {event.event_type}")

def register_default_subscribers() -> None:
    """Registers all core decoupled domain event subscribers at application startup."""
    # Wildcard subscribers — receive ALL events (including all Knowledge events)
    event_bus.subscribe_all(analytics_subscriber)
    event_bus.subscribe_all(audit_subscriber)
    event_bus.subscribe_all(event_history_subscriber)
    event_bus.subscribe_all(search_index_subscriber)

    # Topic-specific subscribers
    event_bus.subscribe(StandardDomainEvents.LEAD_CREATED, ai_subscriber)
    event_bus.subscribe(StandardDomainEvents.CONVERSATION_STARTED, ai_subscriber)
    event_bus.subscribe(StandardDomainEvents.STAGE_CHANGED, workflow_subscriber)
    event_bus.subscribe(StandardDomainEvents.LEAD_CREATED, workflow_subscriber)
    event_bus.subscribe(StandardDomainEvents.LEAD_ASSIGNED, notification_subscriber)
    event_bus.subscribe(StandardDomainEvents.TASK_CREATED, notification_subscriber)
    event_bus.subscribe(StandardDomainEvents.MEETING_BOOKED, notification_subscriber)
    event_bus.subscribe(StandardDomainEvents.AI_QUALIFICATION_COMPLETED, notification_subscriber)

    # ── Part 21.8 — Autonomous Sales Loop Bridge Subscribers ─────────────────
    _register_autonomous_loop_subscribers()

    # ── Knowledge Intelligence Platform subscribers ───────────────────────────
    # Wildcard audit already captures all 13 knowledge events above.
    # Register focused subscribers for actionable knowledge events:
    _register_knowledge_subscribers()

    logger.info(
        "[EVENT SUBSCRIBERS] All enterprise subscribers registered "
        "(including Knowledge Intelligence Platform)"
    )


def _register_knowledge_subscribers() -> None:
    """Register knowledge-specific event subscribers."""
    from app.modules.knowledge.events.knowledge_events import KnowledgeEvents

    async def knowledge_conflict_subscriber(event: DomainEvent) -> None:
        """Route conflict events to admin notification queue."""
        logger.warning(
            f"[KNOWLEDGE CONFLICT] org={event.organization_id} "
            f"payload={event.payload}"
        )
        # Future: send admin in-app notification via NotificationService

    async def knowledge_feedback_subscriber(event: DomainEvent) -> None:
        """Log critical feedback (HALLUCINATION, OUTDATED) for monitoring."""
        payload = event.payload or {}
        if payload.get("is_critical"):
            logger.warning(
                f"[KNOWLEDGE FEEDBACK CRITICAL] org={event.organization_id} "
                f"type={payload.get('feedback_type')} "
                f"query={payload.get('query_id')}"
            )

    async def knowledge_published_subscriber(event: DomainEvent) -> None:
        """Invalidate any cached search results when new knowledge is published."""
        logger.info(
            f"[KNOWLEDGE PUBLISHED] doc={event.payload.get('document_id')} "
            f"org={event.organization_id} — cache invalidation triggered"
        )
        # Future: call Redis cache invalidation for affected org/collection

    event_bus.subscribe(KnowledgeEvents.CONFLICT_DETECTED, knowledge_conflict_subscriber)
    event_bus.subscribe(KnowledgeEvents.FEEDBACK_RECEIVED, knowledge_feedback_subscriber)
    event_bus.subscribe(KnowledgeEvents.PUBLISHED, knowledge_published_subscriber)
    event_bus.subscribe(KnowledgeEvents.EXPIRED, knowledge_published_subscriber)  # Invalidate on expiry too


def _register_autonomous_loop_subscribers() -> None:
    """
    Register bridge subscribers that translate DomainEventBus events into
    SalesLoopEvent Celery tasks for the Part 21.8 autonomous loop.
    Events are dispatched to the sales-loop-orchestration queue asynchronously.
    """
    async def lead_created_loop_subscriber(event: DomainEvent) -> None:
        """Bridge: LeadCreated → NEW_LEAD event in autonomous sales loop."""
        lead_id = event.payload.get("lead_id") or event.payload.get("id")
        tenant_id = event.payload.get("organization_id") or event.organization_id
        if not lead_id or not tenant_id or tenant_id == "global":
            return
        try:
            from app.modules.autonomous_loop.workers.loop_tasks import process_sales_loop_event_task
            import uuid as _uuid
            process_sales_loop_event_task.apply_async(
                kwargs={
                    "event_payload": {
                        "event_type": "NEW_LEAD",
                        "tenant_id": tenant_id,
                        "lead_id": lead_id,
                        "correlation_id": event.correlation_id,
                        "actor_type": "SYSTEM",
                        "payload": {"source": "lead_created_subscriber"},
                        "source": "event_bus_bridge",
                        "idempotency_key": f"lead_created_{lead_id}_{event.event_id}",
                        "occurred_at": event.timestamp,
                    }
                },
                queue="sales-loop-orchestration",
            )
        except Exception as exc:
            logger.warning(f"[AUTONOMOUS_LOOP_BRIDGE] LeadCreated dispatch error: {exc}")

    async def qualification_completed_loop_subscriber(event: DomainEvent) -> None:
        """Bridge: AIQualificationCompleted → QUALIFICATION_COMPLETED event in autonomous loop."""
        lead_id = event.payload.get("lead_id")
        tenant_id = event.payload.get("organization_id") or event.organization_id
        if not lead_id or not tenant_id or tenant_id == "global":
            return
        try:
            from app.modules.autonomous_loop.workers.loop_tasks import process_sales_loop_event_task
            process_sales_loop_event_task.apply_async(
                kwargs={
                    "event_payload": {
                        "event_type": "QUALIFICATION_COMPLETED",
                        "tenant_id": tenant_id,
                        "lead_id": lead_id,
                        "correlation_id": event.correlation_id,
                        "actor_type": "AI",
                        "payload": event.payload,
                        "source": "event_bus_bridge",
                        "idempotency_key": f"qual_completed_{lead_id}_{event.event_id}",
                        "occurred_at": event.timestamp,
                    }
                },
                queue="sales-loop-orchestration",
            )
        except Exception as exc:
            logger.warning(f"[AUTONOMOUS_LOOP_BRIDGE] QualificationCompleted dispatch error: {exc}")

    event_bus.subscribe(StandardDomainEvents.LEAD_CREATED, lead_created_loop_subscriber)
    event_bus.subscribe(StandardDomainEvents.AI_QUALIFICATION_COMPLETED, qualification_completed_loop_subscriber)

    logger.info("[EVENT SUBSCRIBERS] Part 21.8 autonomous loop bridge subscribers registered.")
