import os
import ssl
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from app.config import settings

celery_app = Celery(
    "wefylabs_enterprise_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.followup_tasks",
        "app.tasks.queue_workers",
        # Knowledge Intelligence Platform workers
        "app.modules.knowledge.workers.knowledge_tasks",
        # Calendar & Scheduling Intelligence Engine workers
        "app.modules.calendar.workers.calendar_tasks",
        # CRM Intelligence & Autonomous Sales Operations workers
        "app.modules.crm_intelligence.workers.intelligence_tasks",
        # Predictive Analytics & MLOps Engine workers
        "app.modules.predictive.workers.predictive_tasks",
        # Workflow Automation & Revenue Operations workers
        "app.modules.workflow.workers.workflow_tasks",
        # AI Memory & Customer Intelligence Engine workers
        "app.modules.memory.workers.memory_tasks",
        # Part 21.8 — AI Autonomous Sales Loop & Event-Driven Orchestration Engine workers
        "app.modules.autonomous_loop.workers.loop_tasks",
        # Part 35 — AI Real Estate Revenue Autopilot workers
        "app.modules.revenue_autopilot.tasks",
        # Part 12 — Follow-Up dispatch through the Communication Hub
        "app.modules.follow_up.tasks",
        # Phase 1 Sprint 1E — Revenue Learning OS & Outcome Intelligence
        "app.modules.intelligence.tasks",
    ]
)

# Enterprise Queues Configuration
default_exchange = Exchange("default", type="direct")
dlq_exchange = Exchange("dlq", type="direct")

task_queues = [
    # ── Existing BeetleLabs Queues (unchanged) ────────────────────────────
    Queue("lead_queue", default_exchange, routing_key="lead_queue"),
    Queue("notification_queue", default_exchange, routing_key="notification_queue"),
    Queue("email_queue", default_exchange, routing_key="email_queue"),
    Queue("whatsapp_queue", default_exchange, routing_key="whatsapp_queue"),
    Queue("analytics_queue", default_exchange, routing_key="analytics_queue"),
    Queue("webhook_queue", default_exchange, routing_key="webhook_queue"),
    Queue("export_queue", default_exchange, routing_key="export_queue"),
    Queue("import_queue", default_exchange, routing_key="import_queue"),
    Queue("ai_queue", default_exchange, routing_key="ai_queue"),
    Queue("retry_queue", default_exchange, routing_key="retry_queue"),
    Queue("dead_letter_queue", dlq_exchange, routing_key="dead_letter_queue"),
    # ── Knowledge Intelligence Platform Queues ────────────────────────────
    Queue("knowledge-ingestion", default_exchange, routing_key="knowledge-ingestion"),
    Queue("knowledge-parser", default_exchange, routing_key="knowledge-parser"),
    Queue("knowledge-ocr", default_exchange, routing_key="knowledge-ocr"),
    Queue("knowledge-extraction", default_exchange, routing_key="knowledge-extraction"),
    Queue("knowledge-chunking", default_exchange, routing_key="knowledge-chunking"),
    Queue("knowledge-embedding", default_exchange, routing_key="knowledge-embedding"),
    Queue("knowledge-indexing", default_exchange, routing_key="knowledge-indexing"),
    Queue("knowledge-reindex", default_exchange, routing_key="knowledge-reindex"),
    Queue("knowledge-deletion", default_exchange, routing_key="knowledge-deletion"),
    Queue("knowledge-evaluation", default_exchange, routing_key="knowledge-evaluation"),
    Queue("knowledge-retry", default_exchange, routing_key="knowledge-retry"),
    Queue("knowledge-dead-letter", dlq_exchange, routing_key="knowledge-dead-letter"),
    # ── Calendar & Scheduling Intelligence Platform Queues ────────────────
    Queue("calendar-sync", default_exchange, routing_key="calendar-sync"),
    Queue("reminders", default_exchange, routing_key="reminders"),
    Queue("booking", default_exchange, routing_key="booking"),
    Queue("calendar-conflict", default_exchange, routing_key="calendar-conflict"),
    Queue("meeting-preparation", default_exchange, routing_key="meeting-preparation"),
    Queue("no-show-prediction", default_exchange, routing_key="no-show-prediction"),
    # ── CRM Intelligence & Sales Operations Queues ────────────────────────
    Queue("crm-intelligence-processing", default_exchange, routing_key="crm-intelligence-processing"),
    Queue("lead-health", default_exchange, routing_key="lead-health"),
    Queue("sla-monitoring", default_exchange, routing_key="sla-monitoring"),
    Queue("pipeline-analysis", default_exchange, routing_key="pipeline-analysis"),
    Queue("agent-analysis", default_exchange, routing_key="agent-analysis"),
    Queue("anomaly-detection", default_exchange, routing_key="anomaly-detection"),
    Queue("daily-brief", default_exchange, routing_key="daily-brief"),
    # ── Predictive Analytics & MLOps Engine Queues ────────────────────────
    Queue("prediction", default_exchange, routing_key="prediction"),
    Queue("forecast", default_exchange, routing_key="forecast"),
    Queue("drift-monitoring", default_exchange, routing_key="drift-monitoring"),
    Queue("batch-prediction", default_exchange, routing_key="batch-prediction"),
    Queue("outcome-processing", default_exchange, routing_key="outcome-processing"),
    # ── Workflow Automation Engine Queues ─────────────────────────────────
    Queue("workflow-trigger", default_exchange, routing_key="workflow-trigger"),
    Queue("workflow-execution", default_exchange, routing_key="workflow-execution"),
    Queue("workflow-actions", default_exchange, routing_key="workflow-actions"),
    Queue("workflow-timers", default_exchange, routing_key="workflow-timers"),
    Queue("workflow-approvals", default_exchange, routing_key="workflow-approvals"),
    # ── AI Memory & Customer Intelligence Queues ──────────────────────────
    Queue("memory-decay", default_exchange, routing_key="memory-decay"),
    Queue("memory-retention", default_exchange, routing_key="memory-retention"),
    # ── Part 21.8 — Autonomous Sales Loop Queues ───────────────────────────
    Queue("sales-loop-orchestration", default_exchange, routing_key="sales-loop-orchestration"),
    Queue("sales-loop-retry", default_exchange, routing_key="sales-loop-retry"),
    # ── Phase 2C — Pilot evidence snapshot queue ───────────────────────────
    Queue("pilot-snapshot", default_exchange, routing_key="pilot-snapshot"),
]

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,       # 10 minutes max per heavy task execution
    task_soft_time_limit=540,
    task_default_queue="lead_queue",
    task_queues=task_queues,
    task_routes={
        # ── Existing routes (unchanged) ───────────────────────────────────
        "app.tasks.queue_workers.process_lead_event": {"queue": "lead_queue"},
        "app.tasks.queue_workers.process_webhook_event": {"queue": "webhook_queue"},
        "app.tasks.queue_workers.process_ai_qualification": {"queue": "ai_queue"},
        "app.tasks.queue_workers.process_email_dispatch": {"queue": "email_queue"},
        "app.tasks.queue_workers.process_whatsapp_dispatch": {"queue": "whatsapp_queue"},
        "app.tasks.queue_workers.process_analytics_event": {"queue": "analytics_queue"},
        # ── Knowledge pipeline routes ─────────────────────────────────────
        "app.modules.knowledge.workers.knowledge_tasks.process_document": {"queue": "knowledge-parser"},
        "app.modules.knowledge.workers.knowledge_tasks.run_ocr": {"queue": "knowledge-ocr"},
        "app.modules.knowledge.workers.knowledge_tasks.extract_facts": {"queue": "knowledge-extraction"},
        "app.modules.knowledge.workers.knowledge_tasks.chunk_document_task": {"queue": "knowledge-chunking"},
        "app.modules.knowledge.workers.knowledge_tasks.generate_embeddings": {"queue": "knowledge-embedding"},
        "app.modules.knowledge.workers.knowledge_tasks.index_document": {"queue": "knowledge-indexing"},
        "app.modules.knowledge.workers.knowledge_tasks.reindex_document": {"queue": "knowledge-reindex"},
        "app.modules.knowledge.workers.knowledge_tasks.delete_document_knowledge": {"queue": "knowledge-deletion"},
        "app.modules.knowledge.workers.knowledge_tasks.run_evaluation": {"queue": "knowledge-evaluation"},
        "app.modules.knowledge.workers.knowledge_tasks.expire_stale_knowledge": {"queue": "knowledge-indexing"},
        # ── Calendar & Scheduling Intelligence routes ─────────────────────
        "app.modules.calendar.workers.calendar_tasks.process_due_reminders_task": {"queue": "reminders"},
        "app.modules.calendar.workers.calendar_tasks.cleanup_expired_holds_task": {"queue": "booking"},
        "app.modules.calendar.workers.calendar_tasks.reconcile_calendar_conflicts_task": {"queue": "calendar-conflict"},
        "app.modules.calendar.workers.calendar_tasks.generate_meeting_prep_brief_task": {"queue": "meeting-preparation"},
        "app.modules.calendar.workers.calendar_tasks.evaluate_no_show_risk_task": {"queue": "no-show-prediction"},
        # ── CRM Intelligence routes ───────────────────────────────────────
        "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_lead_health_and_decay_task": {"queue": "lead-health"},
        "app.modules.crm_intelligence.workers.intelligence_tasks.monitor_sla_breaches_task": {"queue": "sla-monitoring"},
        "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_pipeline_stagnation_task": {"queue": "pipeline-analysis"},
        "app.modules.crm_intelligence.workers.intelligence_tasks.calculate_agent_workload_task": {"queue": "agent-analysis"},
        "app.modules.crm_intelligence.workers.intelligence_tasks.detect_crm_anomalies_task": {"queue": "anomaly-detection"},
        "app.modules.crm_intelligence.workers.intelligence_tasks.generate_daily_briefs_task": {"queue": "daily-brief"},
        # ── Predictive Analytics & MLOps routes ───────────────────────────
        "app.modules.predictive.workers.predictive_tasks.refresh_active_lead_predictions": {"queue": "prediction"},
        "app.modules.predictive.workers.predictive_tasks.recalculate_pipeline_revenue_forecasts": {"queue": "forecast"},
        "app.modules.predictive.workers.predictive_tasks.monitor_prediction_drift": {"queue": "drift-monitoring"},
        # ── Workflow Automation Engine routes ─────────────────────────────
        "app.modules.workflow.workers.workflow_tasks.process_due_workflow_waits_task": {"queue": "workflow-timers"},
        "app.modules.workflow.workers.workflow_tasks.dispatch_workflow_trigger_task": {"queue": "workflow-trigger"},
        # ── AI Memory Engine routes ───────────────────────────────────────
        "app.modules.memory.workers.memory_tasks.evaluate_memory_decay_task": {"queue": "memory-decay"},
        # ── Follow-Up Automation Engine routes ─────────────────────────────
        "app.tasks.followup_tasks.evaluate_followups": {"queue": "lead_queue"},
        "app.tasks.followup_tasks.escalate_stale_lead": {"queue": "lead_queue"},
        "app.tasks.followup_tasks.process_followup_rule": {"queue": "lead_queue"},
        "app.tasks.followup_tasks.send_daily_briefing": {"queue": "daily-brief"},
        # ── Part 12 — Follow-Up dispatch through the Communication Hub ──────
        "follow_up.dispatch_due_executions": {"queue": "lead_queue"},
        # ── Phase 1 Sprint 1E — Revenue Learning & Intelligence Routes ───────
        "intelligence.run_nightly_learning_cycle": {"queue": "analytics_queue"},
        "intelligence.run_data_quality_scan": {"queue": "analytics_queue"},
        # ── Phase 1 Sprint 1F — Governed Adaptive Policy Rollout Controller ──
        "intelligence.advance_policy_rollouts": {"queue": "analytics_queue"},
        # ── Phase 2C — Daily pilot evidence snapshot ──────────────────────────
        "autonomous_loop.generate_daily_pilot_snapshots": {"queue": "pilot-snapshot"},
    },
    beat_schedule={
        # ── Existing schedules (unchanged) ────────────────────────────────
        "check-hourly-followups": {
            "task": "app.tasks.followup_tasks.check_and_schedule_followups",
            "schedule": crontab(minute=0, hour="*"),
        },
        # ── Part 27 — Follow-up evaluation every 5 minutes ────────────────
        "evaluate-followups-periodic": {
            "task": "app.tasks.followup_tasks.evaluate_followups",
            "schedule": crontab(minute="*/5"),
        },
        # ── Part 27 — Escalate uncontacted hot leads every 10 minutes ─────
        "escalate-stale-leads-periodic": {
            "task": "app.tasks.followup_tasks.escalate_stale_lead",
            "schedule": crontab(minute="*/10"),
        },
        # ── Part 27 — Daily CRM Briefing at 07:00 AM UTC ──────────────────
        "send-daily-followup-briefing": {
            "task": "app.tasks.followup_tasks.send_daily_briefing",
            "schedule": crontab(minute=0, hour=7),
        },
        # ── Knowledge freshness expiration every 6 hours ──────────────────
        "expire-stale-knowledge": {
            "task": "app.modules.knowledge.workers.knowledge_tasks.expire_stale_knowledge",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # ── Calendar reminder processing every 5 minutes ──────────────────
        "dispatch-due-calendar-reminders": {
            "task": "app.modules.calendar.workers.calendar_tasks.process_due_reminders_task",
            "schedule": crontab(minute="*/5"),
        },
        # ── Release expired booking holds every 5 minutes ─────────────────
        "cleanup-expired-booking-holds": {
            "task": "app.modules.calendar.workers.calendar_tasks.cleanup_expired_holds_task",
            "schedule": crontab(minute="*/5"),
        },
        # ── Reconcile external calendar conflicts every 15 minutes ────────
        "reconcile-calendar-conflicts": {
            "task": "app.modules.calendar.workers.calendar_tasks.reconcile_calendar_conflicts_task",
            "schedule": crontab(minute="*/15"),
        },
        # ── CRM Intelligence: Monitor SLA breaches every 2 minutes ────────
        "monitor-sla-breaches": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.monitor_sla_breaches_task",
            "schedule": crontab(minute="*/2"),
        },
        # ── CRM Intelligence: Lead health & decay every 10 minutes ────────
        "evaluate-lead-health-and-decay": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_lead_health_and_decay_task",
            "schedule": crontab(minute="*/10"),
        },
        # ── CRM Intelligence: Agent workload every 15 minutes ─────────────
        "calculate-agent-workload": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.calculate_agent_workload_task",
            "schedule": crontab(minute="*/15"),
        },
        # ── CRM Intelligence: Pipeline stagnation every 30 minutes ────────
        "evaluate-pipeline-stagnation": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.evaluate_pipeline_stagnation_task",
            "schedule": crontab(minute="*/30"),
        },
        # ── CRM Intelligence: Detect anomalies hourly ─────────────────────
        "detect-crm-anomalies": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.detect_crm_anomalies_task",
            "schedule": crontab(minute=0, hour="*"),
        },
        # ── CRM Intelligence: Daily operational briefs at 07:00 AM UTC ────
        "generate-daily-briefs": {
            "task": "app.modules.crm_intelligence.workers.intelligence_tasks.generate_daily_briefs_task",
            "schedule": crontab(minute=0, hour=7),
        },
        # ── Predictive Analytics: Refresh active predictions every 15m ────
        "refresh-active-lead-predictions": {
            "task": "app.modules.predictive.workers.predictive_tasks.refresh_active_lead_predictions",
            "schedule": crontab(minute="*/15"),
        },
        # ── Predictive Analytics: Recalculate revenue forecast every 30m ──
        "recalculate-pipeline-revenue-forecasts": {
            "task": "app.modules.predictive.workers.predictive_tasks.recalculate_pipeline_revenue_forecasts",
            "schedule": crontab(minute="*/30"),
        },
        # ── Predictive Analytics: Monitor prediction drift hourly ─────────
        "monitor-prediction-drift": {
            "task": "app.modules.predictive.workers.predictive_tasks.monitor_prediction_drift",
            "schedule": crontab(minute=0, hour="*"),
        },
        # ── Workflow Automation: Resume expired wait states every 1 min ───
        "process-due-workflow-waits": {
            "task": "app.modules.workflow.workers.workflow_tasks.process_due_workflow_waits_task",
            "schedule": crontab(minute="*"),
        },
        # ── AI Memory Engine: Evaluate memory decay daily at 03:00 UTC ────
        "evaluate-memory-decay": {
            "task": "app.modules.memory.workers.memory_tasks.evaluate_memory_decay_task",
            "schedule": crontab(minute=0, hour=3),
        },
        # ── Part 21.8 — Autonomous Sales Loop: Evaluate inactive leads every 5 min ─
        "autonomous-loop-inactive-lead-scan": {
            "task": "autonomous_loop.evaluate_inactive_leads",
            "schedule": crontab(minute="*/5"),
            "kwargs": {"tenant_id": "__all__"},  # Per-tenant scan triggered by API/worker
        },
        # ── Part 21.8 — Autonomous Sales Loop: Retry failed events every 2 min ──────
        "autonomous-loop-retry-failed": {
            "task": "autonomous_loop.retry_failed_events",
            "schedule": crontab(minute="*/2"),
            "kwargs": {"tenant_id": "__all__"},
        },
        # ── Part 35 — AI Real Estate Revenue Autopilot: Scan tenant opportunities every 10 min ──
        "scan-revenue-opportunities": {
            "task": "app.modules.revenue_autopilot.tasks.scan_all_tenants_revenue_opportunities_task",
            "schedule": crontab(minute="*/10"),
        },
        # ── Part 35 — AI Real Estate Revenue Autopilot: Expire stale opportunities hourly ──
        "expire-stale-revenue-opportunities": {
            "task": "app.modules.revenue_autopilot.tasks.expire_stale_opportunities_task",
            "schedule": crontab(minute=0, hour="*"),
        },
        # ── Part 12 — Dispatch due follow-up executions through the Hub every 5 min.
        # Inert until FOLLOWUP_HUB_DISPATCH_ENABLED is turned on (see follow_up/tasks.py).
        "dispatch-due-followup-executions": {
            "task": "follow_up.dispatch_due_executions",
            "schedule": crontab(minute="*/5"),
        },
        # ── Phase 1 Sprint 1E — Nightly Revenue Learning Cycle at 02:00 UTC ───
        "nightly-revenue-learning-cycle": {
            "task": "intelligence.run_nightly_learning_cycle",
            "schedule": crontab(minute=0, hour=2),
        },
        # ── Phase 1 Sprint 1E — Data Quality Scan at 03:00 UTC ────────────────
        "daily-data-quality-scan": {
            "task": "intelligence.run_data_quality_scan",
            "schedule": crontab(minute=0, hour=3),
        },
        # ── Phase 1 Sprint 1F — Policy Rollout Controller (every 1h at :30) ──
        # Advances progressive rollout for each active policy by 10%/day when
        # guardrails pass. Emergency pause flag halts controller non-destructively.
        "advance-policy-rollouts": {
            "task": "intelligence.advance_policy_rollouts",
            "schedule": crontab(minute=30, hour="*"),
        },
        # ── Phase 2C — Daily Pilot Metric Snapshot (00:30 UTC each day) ───────
        # Seals the previous calendar day's real shadow observations into a
        # hash-locked PilotMetricSnapshot. Idempotent — a duplicate run for the
        # same pilot+day will be detected and skipped by the repository.
        # NEVER generates synthetic evidence; all metrics sourced from PostgreSQL.
        "generate-daily-pilot-snapshots": {
            "task": "autonomous_loop.generate_daily_pilot_snapshots",
            "schedule": crontab(minute=30, hour=0),
        },
    }
)

# ── Upstash Redis TLS SSL Configuration ──────────────────────────────────────
# When using rediss:// (TLS), Celery requires ssl_cert_reqs for both broker and backend
if settings.REDIS_URL and settings.REDIS_URL.startswith("rediss://"):
    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
    )

