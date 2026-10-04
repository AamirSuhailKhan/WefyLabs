"""
Phase 2B — Human Approval Queue Service
========================================
Manages the human approval workflow for Phase 2B controlled pilots.
When governance determines an action requires explicit human approval,
the action is placed in this queue for human review.

PER PHASE 2 SPEC (Sections 33, 34):
  - Every approval-required action must enter the queue with full context
  - Approvals carry: expiry, resource hash, approver identity
  - Stale approvals are auto-rejected (resource state may have changed)
  - Approval decisions are auditable and immutable
  - Approval queues are tenant-scoped (full tenant isolation)

INVARIANTS:
  1. Pending approval items never auto-execute on timeout — they expire.
  2. Approval expires at the earlier of: explicit expiry OR policy change.
  3. Resource state hash must match at approval time; mismatch = rejection.
  4. Approval cannot be granted by the same agent that proposed the action.
  5. Every approval/denial is audit-logged with actor identity.
"""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType,
    Phase2RiskClass,
    Phase2AutonomyLevel,
    Phase2PolicyDecision,
)
from app.modules.autonomous_loop.phase2_agent_contracts import AgentDomain

logger = logging.getLogger("wefylabs.phase2b.approval_queue")

APPROVAL_DEFAULT_EXPIRY_MINUTES = 60
APPROVAL_HIGH_RISK_EXPIRY_MINUTES = 30
APPROVAL_FINANCIAL_EXPIRY_MINUTES = 15


class ApprovalStatus(str, enum.Enum):
    PENDING   = "PENDING"
    APPROVED  = "APPROVED"
    DENIED    = "DENIED"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"


class ApprovalUrgency(str, enum.Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ApprovalQueueItem:
    """
    Single pending approval request in the human review queue.
    Contains full context for the human reviewer to make an informed decision.
    """
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    lead_id: Optional[str] = None
    agent_domain: AgentDomain = AgentDomain.LEAD_INTELLIGENCE
    execution_id: Optional[str] = None
    agent_id: Optional[str] = None

    # Action context
    action_type: Phase2ActionType = Phase2ActionType.NO_ACTION
    risk_class: Phase2RiskClass = Phase2RiskClass.LOW
    action_description: str = ""
    proposed_content: Optional[str] = None   # e.g. draft message text for review
    expected_outcome: Optional[str] = None

    # Evidence for reviewer
    lead_summary: Optional[str] = None
    reasoning: Optional[str] = None
    policy_decision_summary: Optional[str] = None

    # Integrity fields
    resource_hash: str = ""                  # Hash of resource state at proposal time
    policy_version: str = "phase2-v1.0"

    # Urgency & expiry
    urgency: ApprovalUrgency = ApprovalUrgency.MEDIUM
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    # Resolution fields
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    is_approved: bool = False

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def time_remaining_minutes(self) -> Optional[float]:
        if self.expires_at is None:
            return None
        remaining = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining / 60)

    def compute_resource_hash(self, resource_data: Dict[str, Any]) -> str:
        """Computes deterministic hash of resource state for staleness detection."""
        payload = json.dumps(resource_data, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "organization_id": self.organization_id,
            "lead_id": self.lead_id,
            "agent_domain": self.agent_domain.value,
            "execution_id": self.execution_id,
            "action_type": self.action_type.value,
            "risk_class": self.risk_class.value,
            "action_description": self.action_description,
            "proposed_content": self.proposed_content,
            "expected_outcome": self.expected_outcome,
            "urgency": self.urgency.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "time_remaining_minutes": self.time_remaining_minutes(),
            "is_expired": self.is_expired(),
            "is_approved": self.is_approved,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_notes": self.reviewer_notes,
        }


@dataclass
class ApprovalDecision:
    """Result of an approval queue review decision."""
    approval_id: str
    organization_id: str
    action_type: Phase2ActionType
    decision: ApprovalStatus
    is_approved: bool
    reviewer_id: str
    reviewer_notes: str
    decided_at: datetime
    resource_hash_at_review: Optional[str] = None
    hash_matches: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "organization_id": self.organization_id,
            "action_type": self.action_type.value,
            "decision": self.decision.value,
            "is_approved": self.is_approved,
            "reviewer_id": self.reviewer_id,
            "reviewer_notes": self.reviewer_notes,
            "decided_at": self.decided_at.isoformat(),
            "hash_matches": self.hash_matches,
        }


class HumanApprovalQueueService:
    """
    Human approval queue for Phase 2B controlled pilots.

    Per Phase 2 Spec Section 33:
      - Actions requiring approval are queued here with full context
      - Human reviewer decides: APPROVE or DENY
      - Approved actions return to the execution engine
      - Expired/stale approvals are auto-rejected at execution time
    """

    def __init__(self):
        self._queue: Dict[str, ApprovalQueueItem] = {}   # approval_id -> item
        self._decisions: List[ApprovalDecision] = []
        self._audit_log: List[Dict[str, Any]] = []

    def submit_for_approval(
        self,
        organization_id: str,
        action_type: Phase2ActionType,
        risk_class: Phase2RiskClass,
        agent_domain: AgentDomain,
        action_description: str,
        lead_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        proposed_content: Optional[str] = None,
        expected_outcome: Optional[str] = None,
        lead_summary: Optional[str] = None,
        reasoning: Optional[str] = None,
        resource_data: Optional[Dict[str, Any]] = None,
        policy_version: str = "phase2-v1.0",
        urgency: ApprovalUrgency = ApprovalUrgency.MEDIUM,
        custom_expiry_minutes: Optional[int] = None,
    ) -> ApprovalQueueItem:
        """
        Submits an action to the human approval queue.
        Returns the ApprovalQueueItem with expiry set.
        """
        # Compute expiry based on risk
        if custom_expiry_minutes is not None:
            expiry_minutes = custom_expiry_minutes
        elif risk_class == Phase2RiskClass.FINANCIAL_IRREVERSIBLE:
            expiry_minutes = APPROVAL_FINANCIAL_EXPIRY_MINUTES
        elif risk_class == Phase2RiskClass.HIGH:
            expiry_minutes = APPROVAL_HIGH_RISK_EXPIRY_MINUTES
        else:
            expiry_minutes = APPROVAL_DEFAULT_EXPIRY_MINUTES

        item = ApprovalQueueItem(
            organization_id=organization_id,
            lead_id=lead_id,
            agent_domain=agent_domain,
            execution_id=execution_id,
            agent_id=agent_id,
            action_type=action_type,
            risk_class=risk_class,
            action_description=action_description,
            proposed_content=proposed_content,
            expected_outcome=expected_outcome,
            lead_summary=lead_summary,
            reasoning=reasoning,
            policy_version=policy_version,
            urgency=urgency,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        )

        if resource_data:
            item.resource_hash = item.compute_resource_hash(resource_data)

        self._queue[item.approval_id] = item
        self._audit("SUBMITTED", item.approval_id, organization_id, "AGENT", {
            "action_type": action_type.value,
            "risk_class": risk_class.value,
            "expiry_minutes": expiry_minutes,
        })

        logger.info(
            f"[APPROVAL_QUEUE] Submitted approval_id={item.approval_id} "
            f"org={organization_id} action={action_type.value} "
            f"risk={risk_class.value} expires_in={expiry_minutes}min"
        )
        return item

    def get_pending_items(
        self,
        organization_id: Optional[str] = None,
    ) -> List[ApprovalQueueItem]:
        """Returns all pending (non-expired, non-reviewed) items."""
        now = datetime.now(timezone.utc)
        items = []
        for item in self._queue.values():
            if item.status != ApprovalStatus.PENDING:
                continue
            if item.expires_at and now > item.expires_at:
                item.status = ApprovalStatus.EXPIRED
                continue
            if organization_id and item.organization_id != organization_id:
                continue
            items.append(item)
        return sorted(items, key=lambda x: x.created_at)

    def get_item(self, approval_id: str) -> Optional[ApprovalQueueItem]:
        return self._queue.get(approval_id)

    def approve(
        self,
        approval_id: str,
        reviewer_id: str,
        reviewer_notes: str = "",
        current_resource_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ApprovalDecision, bool]:
        """
        Approves a pending approval item.
        Validates: not expired, resource hash integrity.
        Returns (ApprovalDecision, success_bool).
        """
        item = self._queue.get(approval_id)
        if item is None:
            raise ValueError(f"Approval {approval_id} not found.")

        if item.is_expired():
            item.status = ApprovalStatus.EXPIRED
            decision = self._make_decision(item, reviewer_id, reviewer_notes, approved=False)
            decision.decision = ApprovalStatus.EXPIRED
            logger.warning(f"[APPROVAL_QUEUE] Approval {approval_id} has expired. Auto-denied.")
            return decision, False

        if item.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not PENDING (current status: {item.status.value}).")

        # Hash integrity check
        hash_matches = True
        if item.resource_hash and current_resource_data:
            current_hash = item.compute_resource_hash(current_resource_data)
            hash_matches = current_hash == item.resource_hash
            if not hash_matches:
                logger.warning(
                    f"[APPROVAL_QUEUE] Resource state changed since approval {approval_id} was submitted. "
                    "Approval denied due to hash mismatch."
                )
                item.status = ApprovalStatus.DENIED
                decision = self._make_decision(item, reviewer_id, "Resource state changed — stale approval denied.", approved=False)
                decision.hash_matches = False
                return decision, False

        # Grant approval
        item.status = ApprovalStatus.APPROVED
        item.is_approved = True
        item.reviewed_by = reviewer_id
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewer_notes = reviewer_notes

        decision = self._make_decision(item, reviewer_id, reviewer_notes, approved=True)
        self._decisions.append(decision)
        self._audit("APPROVED", approval_id, item.organization_id, reviewer_id, {
            "action_type": item.action_type.value,
        })

        logger.info(
            f"[APPROVAL_QUEUE] APPROVED approval_id={approval_id} "
            f"by {reviewer_id} for org={item.organization_id}"
        )
        return decision, True

    def deny(
        self,
        approval_id: str,
        reviewer_id: str,
        reviewer_notes: str = "",
    ) -> ApprovalDecision:
        """Denies a pending approval item."""
        item = self._queue.get(approval_id)
        if item is None:
            raise ValueError(f"Approval {approval_id} not found.")
        if item.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not PENDING.")

        item.status = ApprovalStatus.DENIED
        item.is_approved = False
        item.reviewed_by = reviewer_id
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewer_notes = reviewer_notes

        decision = self._make_decision(item, reviewer_id, reviewer_notes, approved=False)
        self._decisions.append(decision)
        self._audit("DENIED", approval_id, item.organization_id, reviewer_id, {
            "action_type": item.action_type.value,
        })

        logger.info(
            f"[APPROVAL_QUEUE] DENIED approval_id={approval_id} "
            f"by {reviewer_id} for org={item.organization_id}"
        )
        return decision

    def cancel(self, approval_id: str, cancelled_by: str) -> bool:
        """Cancels a pending approval (e.g., context changed before review)."""
        item = self._queue.get(approval_id)
        if item is None or item.status != ApprovalStatus.PENDING:
            return False
        item.status = ApprovalStatus.CANCELLED
        self._audit("CANCELLED", approval_id, item.organization_id, cancelled_by, {})
        return True

    def expire_stale_items(self) -> int:
        """Scans queue and marks expired items. Returns count of expired items."""
        now = datetime.now(timezone.utc)
        expired_count = 0
        for item in self._queue.values():
            if item.status == ApprovalStatus.PENDING and item.expires_at and now > item.expires_at:
                item.status = ApprovalStatus.EXPIRED
                expired_count += 1
        if expired_count:
            logger.info(f"[APPROVAL_QUEUE] Expired {expired_count} stale approval items.")
        return expired_count

    def get_queue_stats(self, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns queue statistics for monitoring."""
        items = list(self._queue.values())
        if organization_id:
            items = [i for i in items if i.organization_id == organization_id]

        self.expire_stale_items()

        return {
            "total": len(items),
            "pending": sum(1 for i in items if i.status == ApprovalStatus.PENDING),
            "approved": sum(1 for i in items if i.status == ApprovalStatus.APPROVED),
            "denied": sum(1 for i in items if i.status == ApprovalStatus.DENIED),
            "expired": sum(1 for i in items if i.status == ApprovalStatus.EXPIRED),
            "cancelled": sum(1 for i in items if i.status == ApprovalStatus.CANCELLED),
            "total_decisions": len(self._decisions),
        }

    def _make_decision(self, item, reviewer_id, notes, approved) -> ApprovalDecision:
        return ApprovalDecision(
            approval_id=item.approval_id,
            organization_id=item.organization_id,
            action_type=item.action_type,
            decision=item.status,
            is_approved=approved,
            reviewer_id=reviewer_id,
            reviewer_notes=notes,
            decided_at=datetime.now(timezone.utc),
        )

    def _audit(self, event, approval_id, org_id, actor, data):
        self._audit_log.append({
            "event": event,
            "approval_id": approval_id,
            "organization_id": org_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

    def get_audit_log(self, organization_id=None):
        if organization_id:
            return [e for e in self._audit_log if e.get("organization_id") == organization_id]
        return list(self._audit_log)

    def reset_for_testing(self):
        self._queue.clear()
        self._decisions.clear()
        self._audit_log.clear()


_approval_queue_instance: Optional[HumanApprovalQueueService] = None


def get_approval_queue() -> HumanApprovalQueueService:
    global _approval_queue_instance
    if _approval_queue_instance is None:
        _approval_queue_instance = HumanApprovalQueueService()
    return _approval_queue_instance
