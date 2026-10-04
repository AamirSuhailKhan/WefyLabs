"""
Phase 2 — Revenue Action Policy Engine (RAPE)
==============================================
Platform-wide governance for ALL autonomous agent actions across WefyLabs.

ARCHITECTURE INVARIANTS (from Phase 2 prompt):
  1. AI never decides its own authority. This module is purely deterministic Python.
  2. Every action type carries a canonical risk classification.
  3. Autonomy levels 0-6 are enforced per-tenant per-action-type.
  4. Safe default: when policy state is ambiguous → DO NOT EXECUTE.
  5. Shadow mode: agent operates against real data, executes nothing external.
  6. Policy versioning: every policy change is auditable.
  7. Kill switches: global / tenant / agent / workflow / action-type all delegate
     to EmergencyAutomationPauseService (existing Phase 1F infrastructure).

DOES NOT DUPLICATE:
  - EmergencyAutomationPauseService (emergency_pause.py) — reused directly.
  - AutonomyPolicyEngine (automation_policy.py) — extended, not replaced.
  - ActionPolicyEngine (ai_agent/action_policy.py) — extended, not replaced.
  - LoopProtectionService (loop_protection.py) — reused.
  - GuardChain (guard_chain.py) — extended by Phase 2 guards.
"""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("wefylabs.phase2.governance")

# ─── Policy Version ───────────────────────────────────────────────────────────

PHASE2_POLICY_VERSION = "phase2-v1.0"
PHASE2_POLICY_DATE = "2026-10-01"


# ─── 1. Phase 2 Autonomy Levels (Sections 3, 34) ────────────────────────────

class Phase2AutonomyLevel(int, enum.Enum):
    """
    Graduated autonomy ladder per Phase 2 specification (Section 3).
    Every action type declares its MAXIMUM permitted level.
    Tenants may only configure at or BELOW that maximum.
    """
    OBSERVE_ONLY = 0              # Read state, record data, generate insights. Never act.
    RECOMMEND = 1                  # Surface recommendation for human. No execution.
    PREPARE = 2                    # Prepare draft, plan, shortlist. No external action.
    REQUEST_APPROVAL = 3           # Submit action for explicit human approval.
    EXECUTE_APPROVED = 4           # Execute once explicit human approval is received.
    CONDITIONALLY_AUTONOMOUS = 5   # Execute within strict, policy-verified conditions.
    AUTONOMOUS_GOVERNED = 6        # Execute autonomously with full governance & audit trail.


# ─── 2. Phase 2 Action Risk Classification (Section 4) ──────────────────────

class Phase2RiskClass(str, enum.Enum):
    """
    Canonical 4-tier action risk model.
    Determines minimum required governance before execution.
    """
    LOW = "LOW"                         # Internal task, summary, draft, shortlist
    MEDIUM = "MEDIUM"                    # External communication (send), reschedule
    HIGH = "HIGH"                        # Deal status, negotiation state, inventory reserve
    FINANCIAL_IRREVERSIBLE = "FINANCIAL_IRREVERSIBLE"  # Booking, payment, financial commitment


# ─── 3. Phase 2 Canonical Action Registry (Sections 4, 5, 8) ────────────────

class Phase2ActionType(str, enum.Enum):
    """
    Complete canonical registry of all agent-executable action types.
    AI may ONLY invoke actions from this enumeration.
    New action types MUST be registered here — never inferred at runtime.
    """
    # ── Internal / Low Risk ──────────────────────────────────────────────────
    CREATE_INTERNAL_TASK = "CREATE_INTERNAL_TASK"
    SUMMARIZE_LEAD = "SUMMARIZE_LEAD"
    PREPARE_PROPERTY_SHORTLIST = "PREPARE_PROPERTY_SHORTLIST"
    PREPARE_MESSAGE_DRAFT = "PREPARE_MESSAGE_DRAFT"
    PREPARE_NEGOTIATION_SUMMARY = "PREPARE_NEGOTIATION_SUMMARY"
    PREPARE_VISIT_PROPOSAL = "PREPARE_VISIT_PROPOSAL"
    RECORD_OUTCOME = "RECORD_OUTCOME"
    UPDATE_LEAD_INTENT_STATE = "UPDATE_LEAD_INTENT_STATE"
    LOG_OBJECTION = "LOG_OBJECTION"
    UPDATE_QUALIFICATION_PROFILE = "UPDATE_QUALIFICATION_PROFILE"

    # ── External Communication / Medium Risk ─────────────────────────────────
    SEND_WHATSAPP_MESSAGE = "SEND_WHATSAPP_MESSAGE"
    SEND_EMAIL = "SEND_EMAIL"
    SEND_SMS = "SEND_SMS"
    SEND_PROPERTY_RECOMMENDATIONS = "SEND_PROPERTY_RECOMMENDATIONS"
    SEND_PROPERTY_DETAILS = "SEND_PROPERTY_DETAILS"
    SEND_VIEWING_INVITATION = "SEND_VIEWING_INVITATION"
    SEND_FOLLOW_UP = "SEND_FOLLOW_UP"
    SEND_REACTIVATION_OUTREACH = "SEND_REACTIVATION_OUTREACH"

    # ── Scheduling & State Changes / High Risk ───────────────────────────────
    SCHEDULE_SITE_VISIT = "SCHEDULE_SITE_VISIT"
    RESCHEDULE_SITE_VISIT = "RESCHEDULE_SITE_VISIT"
    CANCEL_SITE_VISIT = "CANCEL_SITE_VISIT"
    UPDATE_DEAL_STATUS = "UPDATE_DEAL_STATUS"
    UPDATE_NEGOTIATION_STATE = "UPDATE_NEGOTIATION_STATE"
    RESERVE_INVENTORY_UNIT = "RESERVE_INVENTORY_UNIT"
    ESCALATE_TO_MANAGER = "ESCALATE_TO_MANAGER"
    TRIGGER_HUMAN_HANDOFF = "TRIGGER_HUMAN_HANDOFF"

    # ── Financial / Irreversible ─────────────────────────────────────────────
    CREATE_BOOKING = "CREATE_BOOKING"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    PROCESS_PAYMENT = "PROCESS_PAYMENT"
    CANCEL_BOOKING = "CANCEL_BOOKING"
    ISSUE_REFUND = "ISSUE_REFUND"

    # ── System / Control ─────────────────────────────────────────────────────
    NO_ACTION = "NO_ACTION"
    REQUEST_HUMAN_APPROVAL = "REQUEST_HUMAN_APPROVAL"
    SHADOW_OBSERVE = "SHADOW_OBSERVE"


# ─── 4. Canonical Action Risk Table (Section 4) ──────────────────────────────

ACTION_RISK_TABLE: Dict[Phase2ActionType, Tuple[Phase2RiskClass, Phase2AutonomyLevel]] = {
    # (risk_class, max_autonomy_level_permitted)
    # LOW risk → may be AUTONOMOUS_GOVERNED (6) with full governance
    Phase2ActionType.CREATE_INTERNAL_TASK:          (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.SUMMARIZE_LEAD:                (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.PREPARE_PROPERTY_SHORTLIST:    (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.PREPARE_MESSAGE_DRAFT:         (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY:   (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.PREPARE_VISIT_PROPOSAL:        (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.RECORD_OUTCOME:                (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.UPDATE_LEAD_INTENT_STATE:      (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.LOG_OBJECTION:                 (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.UPDATE_QUALIFICATION_PROFILE:  (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.NO_ACTION:                     (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
    Phase2ActionType.SHADOW_OBSERVE:                (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),

    # MEDIUM risk → max CONDITIONALLY_AUTONOMOUS (5) requires policy conditions
    Phase2ActionType.SEND_WHATSAPP_MESSAGE:         (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_EMAIL:                    (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_SMS:                      (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_PROPERTY_RECOMMENDATIONS: (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_PROPERTY_DETAILS:         (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_VIEWING_INVITATION:       (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_FOLLOW_UP:                (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),
    Phase2ActionType.SEND_REACTIVATION_OUTREACH:    (Phase2RiskClass.MEDIUM, Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS),

    # HIGH risk → max EXECUTE_APPROVED (4) — human must have approved
    Phase2ActionType.SCHEDULE_SITE_VISIT:           (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.RESCHEDULE_SITE_VISIT:         (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.CANCEL_SITE_VISIT:             (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.UPDATE_DEAL_STATUS:            (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.UPDATE_NEGOTIATION_STATE:      (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.RESERVE_INVENTORY_UNIT:        (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.ESCALATE_TO_MANAGER:           (Phase2RiskClass.HIGH, Phase2AutonomyLevel.EXECUTE_APPROVED),
    Phase2ActionType.TRIGGER_HUMAN_HANDOFF:         (Phase2RiskClass.HIGH, Phase2AutonomyLevel.REQUEST_APPROVAL),

    # FINANCIAL/IRREVERSIBLE → max REQUEST_APPROVAL (3) — strict human governance required
    Phase2ActionType.CREATE_BOOKING:                (Phase2RiskClass.FINANCIAL_IRREVERSIBLE, Phase2AutonomyLevel.REQUEST_APPROVAL),
    Phase2ActionType.CONFIRM_BOOKING:               (Phase2RiskClass.FINANCIAL_IRREVERSIBLE, Phase2AutonomyLevel.REQUEST_APPROVAL),
    Phase2ActionType.PROCESS_PAYMENT:               (Phase2RiskClass.FINANCIAL_IRREVERSIBLE, Phase2AutonomyLevel.REQUEST_APPROVAL),
    Phase2ActionType.CANCEL_BOOKING:                (Phase2RiskClass.FINANCIAL_IRREVERSIBLE, Phase2AutonomyLevel.REQUEST_APPROVAL),
    Phase2ActionType.ISSUE_REFUND:                  (Phase2RiskClass.FINANCIAL_IRREVERSIBLE, Phase2AutonomyLevel.REQUEST_APPROVAL),
    Phase2ActionType.REQUEST_HUMAN_APPROVAL:        (Phase2RiskClass.LOW, Phase2AutonomyLevel.AUTONOMOUS_GOVERNED),
}


# ─── 5. Execution Mode (Section 55, 56) ──────────────────────────────────────

class Phase2ExecutionMode(str, enum.Enum):
    """
    Determines whether the agent executes real external actions or observes only.
    SHADOW: agent operates against real data but executes nothing external.
    RECOMMEND: agent generates recommendations, never executes.
    PREPARE: Stage 3 — prepares drafts, plans, and shortlists into review staging. No external actions.
    APPROVAL: agent prepares + submits for approval before execution.
    LIVE: agent executes approved actions for real.
    """
    SHADOW = "SHADOW"           # Observe + plan + log what would happen. No external actions.
    RECOMMEND = "RECOMMEND"      # Surface recommendation only. No execution.
    PREPARE = "PREPARE"          # Stage 3: Prepare draft, plan, shortlist. No external action.
    APPROVAL = "APPROVAL"        # Prepare + submit for approval. Execute after approval.
    LIVE = "LIVE"                # Full live execution with governance.


# ─── 5A. Canonical Readiness Conditions Contract (Section 74) ────────────────

CANONICAL_CONDITION_1 = "FRESHNESS_VERIFIED"
CANONICAL_CONDITION_2 = "CONSENT_VERIFIED"
CANONICAL_CONDITION_3 = "QUIET_HOURS_PERMITTED"
CANONICAL_CONDITION_4 = "FATIGUE_BUDGET_AVAILABLE"
CANONICAL_CONDITION_5 = "CONFIDENCE_THRESHOLD_MET"

CANONICAL_AUTONOMY_CONDITIONS: Dict[str, str] = {
    CANONICAL_CONDITION_1: "Context retrieved within freshness TTL (300s) and zero stale commercial fields.",
    CANONICAL_CONDITION_2: "Customer has active explicit opt-in with zero opt-out/DND signals.",
    CANONICAL_CONDITION_3: "Current time is within recipient local timezone allowable window (09:00 - 20:00).",
    CANONICAL_CONDITION_4: "Daily and weekly outbound message counts do not exceed fatigue limits.",
    CANONICAL_CONDITION_5: "Agent confidence is categorically HIGH or score >= 0.85.",
}


# ─── 6. Policy Decision Record ───────────────────────────────────────────────

@dataclass
class Phase2PolicyDecision:
    """
    Result of the Revenue Action Policy Engine evaluation for a single action.
    Every execution must carry a PolicyDecision — it cannot be bypassed.
    """
    action_type: Phase2ActionType
    risk_class: Phase2RiskClass
    max_permitted_level: Phase2AutonomyLevel
    tenant_configured_level: Phase2AutonomyLevel
    effective_level: Phase2AutonomyLevel
    execution_mode: Phase2ExecutionMode
    is_permitted: bool
    requires_approval: bool
    block_reason: Optional[str]
    policy_version: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_conditions_met: List[str] = field(default_factory=list)
    policy_conditions_unmet: List[str] = field(default_factory=list)
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action_type": self.action_type.value,
            "risk_class": self.risk_class.value,
            "max_permitted_level": self.max_permitted_level.value,
            "tenant_configured_level": self.tenant_configured_level.value,
            "effective_level": self.effective_level.value,
            "execution_mode": self.execution_mode.value,
            "is_permitted": self.is_permitted,
            "requires_approval": self.requires_approval,
            "block_reason": self.block_reason,
            "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_conditions_met": self.policy_conditions_met,
            "policy_conditions_unmet": self.policy_conditions_unmet,
        }


# ─── 7. Tenant Autonomy Configuration (Sections 34, 35) ─────────────────────

@dataclass
class TenantAutonomyConfig:
    """
    Per-tenant autonomy configuration. RBAC-protected, auditable, versioned.
    Default configuration favors safety (all actions at OBSERVE_ONLY).
    Administrators must explicitly elevate actions to higher autonomy levels.
    """
    organization_id: str
    execution_mode: Phase2ExecutionMode = Phase2ExecutionMode.SHADOW
    # Per-action-type level overrides. Absent = system default for that risk class.
    action_overrides: Dict[str, int] = field(default_factory=dict)
    # Default levels by risk class (if no action-specific override)
    default_level_low_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.AUTONOMOUS_GOVERNED
    default_level_medium_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.RECOMMEND
    default_level_high_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.REQUEST_APPROVAL
    default_level_financial: Phase2AutonomyLevel = Phase2AutonomyLevel.REQUEST_APPROVAL
    config_version: int = 1
    configured_by: Optional[str] = None
    configured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_configured_level(self, action_type: Phase2ActionType) -> Phase2AutonomyLevel:
        """Returns tenant-configured autonomy level for this action type."""
        override_val = self.action_overrides.get(action_type.value)
        if override_val is not None:
            return Phase2AutonomyLevel(override_val)
        # Fall through to risk-class default
        risk_class, _ = ACTION_RISK_TABLE.get(action_type, (Phase2RiskClass.HIGH, Phase2AutonomyLevel.OBSERVE_ONLY))
        if risk_class == Phase2RiskClass.LOW:
            return self.default_level_low_risk
        elif risk_class == Phase2RiskClass.MEDIUM:
            return self.default_level_medium_risk
        elif risk_class == Phase2RiskClass.HIGH:
            return self.default_level_high_risk
        else:
            return self.default_level_financial

    def compute_config_hash(self) -> str:
        """Deterministic hash of config state for change detection."""
        payload = {
            "execution_mode": self.execution_mode.value,
            "action_overrides": self.action_overrides,
            "default_level_low_risk": self.default_level_low_risk.value,
            "default_level_medium_risk": self.default_level_medium_risk.value,
            "default_level_high_risk": self.default_level_high_risk.value,
            "default_level_financial": self.default_level_financial.value,
            "config_version": self.config_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


# ─── 8. Autonomy Conditions (Section 46) ─────────────────────────────────────

@dataclass
class AutonomyReadinessCondition:
    """
    Explicit condition that must be met before conditional autonomy executes.
    Conditions are checked deterministically — not by AI inference.
    """
    condition_id: str
    description: str
    is_met: bool
    evidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "description": self.description,
            "is_met": self.is_met,
            "evidence": self.evidence,
        }


# ─── 9. Revenue Action Policy Engine (Section 5) ─────────────────────────────

class RevenueActionPolicyEngine:
    """
    Phase 2 canonical governance engine for all autonomous agent actions.

    Evaluation order (fail-safe cascade):
      1. Shadow mode check — if SHADOW, block all external actions immediately.
      2. Action type registration — unknown actions → block (not in canonical registry).
      3. Risk classification lookup — determines max permitted autonomy level.
      4. Tenant autonomy configuration — tenant level ≤ max permitted level.
      5. Effective level determination — min(tenant_configured, max_permitted).
      6. Execution mode vs effective level gate — SHADOW never executes externally.
      7. Autonomy conditions — for CONDITIONALLY_AUTONOMOUS: all conditions must pass.
      8. Safe default — ambiguous policy state → BLOCK.
    """

    def __init__(self):
        # In-memory tenant configuration store.
        # In production this would be backed by PostgreSQL with Redis caching.
        self._tenant_configs: Dict[str, TenantAutonomyConfig] = {}
        self._config_history: Dict[str, List[TenantAutonomyConfig]] = {}
        self._config_audit_log: List[Dict[str, Any]] = []
        self._policy_version = PHASE2_POLICY_VERSION

    @property
    def policy_version(self) -> str:
        return self._policy_version

    def get_policy_version(self) -> str:
        return self._policy_version

    # ── Public API ────────────────────────────────────────────────────────────

    def configure_tenant(
        self,
        organization_id: str,
        execution_mode: Phase2ExecutionMode = Phase2ExecutionMode.SHADOW,
        action_overrides: Optional[Dict[str, int]] = None,
        default_level_low_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
        default_level_medium_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.RECOMMEND,
        default_level_high_risk: Phase2AutonomyLevel = Phase2AutonomyLevel.REQUEST_APPROVAL,
        default_level_financial: Phase2AutonomyLevel = Phase2AutonomyLevel.REQUEST_APPROVAL,
        configured_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> TenantAutonomyConfig:
        """
        Creates or replaces tenant autonomy configuration.
        Version incremented on every change for audit trail.
        MATHEMATICAL INVARIANT: Financial actions can NEVER exceed REQUEST_APPROVAL (level 3).
        """
        existing = self._tenant_configs.get(organization_id)
        new_version = (existing.config_version + 1) if existing else 1

        # Section 75: Financial action cap enforcement
        financial_actions = {
            Phase2ActionType.CREATE_BOOKING,
            Phase2ActionType.CONFIRM_BOOKING,
            Phase2ActionType.PROCESS_PAYMENT,
            Phase2ActionType.CANCEL_BOOKING,
            Phase2ActionType.ISSUE_REFUND,
        }
        if default_level_financial.value > Phase2AutonomyLevel.REQUEST_APPROVAL.value:
            logger.warning(
                f"[POLICY_ENGINE] Financial level {default_level_financial.name} exceeds hard cap. Clamped to REQUEST_APPROVAL."
            )
            default_level_financial = Phase2AutonomyLevel.REQUEST_APPROVAL

        cleaned_overrides = dict(action_overrides or {})
        for act_name, lvl in list(cleaned_overrides.items()):
            try:
                act_enum = Phase2ActionType(act_name)
                if act_enum in financial_actions and lvl > Phase2AutonomyLevel.REQUEST_APPROVAL.value:
                    logger.warning(
                        f"[POLICY_ENGINE] Override for {act_name} exceeds financial cap ({lvl} > 3). Clamped to REQUEST_APPROVAL."
                    )
                    cleaned_overrides[act_name] = Phase2AutonomyLevel.REQUEST_APPROVAL.value
            except ValueError:
                pass

        config = TenantAutonomyConfig(
            organization_id=organization_id,
            execution_mode=execution_mode,
            action_overrides=cleaned_overrides,
            default_level_low_risk=default_level_low_risk,
            default_level_medium_risk=default_level_medium_risk,
            default_level_high_risk=default_level_high_risk,
            default_level_financial=default_level_financial,
            config_version=new_version,
            configured_by=configured_by,
        )
        self._tenant_configs[organization_id] = config

        # Track historical configuration versions (Section 36, 78, 81)
        if organization_id not in self._config_history:
            self._config_history[organization_id] = []
        self._config_history[organization_id].append(config)

        # Audit record
        audit_entry = {
            "organization_id": organization_id,
            "old_version": existing.config_version if existing else 0,
            "new_version": new_version,
            "old_mode": existing.execution_mode.value if existing else None,
            "new_mode": execution_mode.value,
            "actor": configured_by or "SYSTEM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_hash": config.compute_config_hash(),
            "reason": reason or "Autonomy configuration update",
        }
        self._config_audit_log.append(audit_entry)

        logger.info(
            f"[POLICY_ENGINE] Tenant {organization_id} autonomy configured: "
            f"mode={execution_mode.value}, version={new_version}, "
            f"hash={config.compute_config_hash()}"
        )
        return config

    def rollback_tenant_config(
        self,
        organization_id: str,
        target_version: int,
        actor: str = "SYSTEM",
        reason: str = "Rollback execution",
    ) -> TenantAutonomyConfig:
        """
        Rolls back tenant configuration to a specific previous version.
        Appends to history without rewriting past versions (Section 81).
        """
        history = self._config_history.get(organization_id, [])
        target_config = next((c for c in history if c.config_version == target_version), None)
        if not target_config:
            raise ValueError(f"Target config version {target_version} not found for tenant {organization_id}")

        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=target_config.execution_mode,
            action_overrides=dict(target_config.action_overrides),
            default_level_low_risk=target_config.default_level_low_risk,
            default_level_medium_risk=target_config.default_level_medium_risk,
            default_level_high_risk=target_config.default_level_high_risk,
            default_level_financial=target_config.default_level_financial,
            configured_by=actor,
            reason=f"Rollback to version {target_version}: {reason}",
        )

    def get_config_audit_log(self, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns configuration mutation audit entries (Section 78)."""
        if organization_id:
            return [e for e in self._config_audit_log if e["organization_id"] == organization_id]
        return list(self._config_audit_log)

    def get_tenant_config(self, organization_id: str) -> TenantAutonomyConfig:
        """
        Returns tenant config, defaulting to maximally safe configuration (Section 76).
        Unconfigured or missing tenant always defaults to SHADOW mode.
        """
        if not organization_id or organization_id == "UNKNOWN":
            return TenantAutonomyConfig(
                organization_id=organization_id or "UNKNOWN",
                execution_mode=Phase2ExecutionMode.SHADOW,
                default_level_low_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_medium_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_high_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_financial=Phase2AutonomyLevel.OBSERVE_ONLY,
            )
        return self._tenant_configs.get(
            organization_id,
            TenantAutonomyConfig(
                organization_id=organization_id,
                execution_mode=Phase2ExecutionMode.SHADOW,
                default_level_low_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_medium_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_high_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
                default_level_financial=Phase2AutonomyLevel.OBSERVE_ONLY,
            ),
        )

    def validate_approval(
        self,
        *,
        organization_id: str,
        approval_id: str,
        action_type: Phase2ActionType,
        policy_version_at_approval: str,
        resource_hash_at_approval: str,
        current_resource_hash: str,
        expires_at: datetime,
        is_revoked: bool = False,
    ) -> Tuple[bool, str]:
        """
        Validates whether a previously granted approval is still valid at execution time (Section 9, 10).
        Revalidates: expiration, policy version, resource state hash, revocation.
        """
        now = datetime.now(timezone.utc)
        if now > expires_at:
            return False, f"Approval {approval_id} has expired (expired at {expires_at.isoformat()})."
        if is_revoked:
            return False, f"Approval {approval_id} has been revoked by a manager."
        if policy_version_at_approval != self._policy_version:
            return False, (
                f"Approval {approval_id} was granted under policy {policy_version_at_approval}, "
                f"but current policy is {self._policy_version}. Re-approval required."
            )
        if resource_hash_at_approval != current_resource_hash:
            return False, (
                f"Approval {approval_id} resource state changed between approval and execution "
                f"(hash mismatch). Stale approval rejected."
            )
        return True, "Approval is valid."

    def evaluate(
        self,
        organization_id: str,
        action_type: Phase2ActionType,
        conditions: Optional[List[AutonomyReadinessCondition]] = None,
        has_human_approval: bool = False,
    ) -> Phase2PolicyDecision:
        """
        Evaluates whether an agent may execute the specified action for this tenant.
        Returns Phase2PolicyDecision — this is the governance record for the action.

        SAFE DEFAULT: any unexpected state → BLOCK with reason.
        """
        try:
            # Emergency pause check (Section 32, 80)
            from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
            is_global_paused, global_reason = EmergencyAutomationPauseService.is_global_paused()
            if is_global_paused:
                risk_class, max_level = ACTION_RISK_TABLE.get(
                    action_type, (Phase2RiskClass.HIGH, Phase2AutonomyLevel.OBSERVE_ONLY)
                )
                return Phase2PolicyDecision(
                    action_type=action_type,
                    risk_class=risk_class,
                    max_permitted_level=max_level,
                    tenant_configured_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                    effective_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                    execution_mode=Phase2ExecutionMode.SHADOW,
                    is_permitted=False,
                    requires_approval=True,
                    block_reason=f"Emergency kill switch active: {global_reason}",
                    policy_version=self._policy_version,
                )

            if organization_id:
                is_tenant_paused, tenant_reason = EmergencyAutomationPauseService.is_tenant_paused(organization_id)
                if is_tenant_paused:
                    risk_class, max_level = ACTION_RISK_TABLE.get(
                        action_type, (Phase2RiskClass.HIGH, Phase2AutonomyLevel.OBSERVE_ONLY)
                    )
                    return Phase2PolicyDecision(
                        action_type=action_type,
                        risk_class=risk_class,
                        max_permitted_level=max_level,
                        tenant_configured_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                        effective_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                        execution_mode=Phase2ExecutionMode.SHADOW,
                        is_permitted=False,
                        requires_approval=True,
                        block_reason=f"Emergency pause active for tenant {organization_id}: {tenant_reason}",
                        policy_version=self._policy_version,
                    )

            return self._evaluate_internal(organization_id, action_type, conditions or [], has_human_approval=has_human_approval)
        except Exception as e:
            # Safe default — unexpected error → BLOCK (Section 77)
            logger.error(f"[POLICY_ENGINE] Unexpected error during evaluation: {e}", exc_info=True)
            risk_class, max_level = ACTION_RISK_TABLE.get(
                action_type, (Phase2RiskClass.HIGH, Phase2AutonomyLevel.OBSERVE_ONLY)
            )
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=risk_class,
                max_permitted_level=max_level,
                tenant_configured_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                effective_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                execution_mode=Phase2ExecutionMode.SHADOW,
                is_permitted=False,
                requires_approval=True,
                block_reason=f"Policy evaluation error — safe default engaged: {str(e)[:200]}",
                policy_version=self._policy_version,
            )

    def _evaluate_internal(
        self,
        organization_id: str,
        action_type: Phase2ActionType,
        conditions: List[AutonomyReadinessCondition],
        has_human_approval: bool = False,
    ) -> Phase2PolicyDecision:
        if organization_id not in self._tenant_configs and has_human_approval:
            config = TenantAutonomyConfig(
                organization_id=organization_id,
                execution_mode=Phase2ExecutionMode.APPROVAL,
                default_level_low_risk=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
                default_level_medium_risk=Phase2AutonomyLevel.EXECUTE_APPROVED,
                default_level_high_risk=Phase2AutonomyLevel.EXECUTE_APPROVED,
                default_level_financial=Phase2AutonomyLevel.REQUEST_APPROVAL,
            )
        else:
            config = self.get_tenant_config(organization_id)

        # 1. Action registration check
        if action_type not in ACTION_RISK_TABLE:
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=Phase2RiskClass.HIGH,
                max_permitted_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                tenant_configured_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                effective_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                execution_mode=config.execution_mode,
                is_permitted=False,
                requires_approval=True,
                block_reason=f"Action type {action_type.value} is not registered in the canonical action registry.",
                policy_version=self._policy_version,
            )

        # 2. Risk classification
        risk_class, max_permitted_level = ACTION_RISK_TABLE[action_type]

        # 3. Tenant configured level
        tenant_level = config.get_configured_level(action_type)

        # 4. Effective level = min(tenant_configured, max_permitted)
        effective_level = Phase2AutonomyLevel(min(tenant_level.value, max_permitted_level.value))

        # Elevate to EXECUTE_APPROVED if human approval is present and tenant allows up to REQUEST_APPROVAL
        if has_human_approval and effective_level == Phase2AutonomyLevel.REQUEST_APPROVAL:
            effective_level = Phase2AutonomyLevel.EXECUTE_APPROVED

        # 5. Shadow mode check — SHADOW mode always blocks external actions
        is_external = risk_class in (Phase2RiskClass.MEDIUM, Phase2RiskClass.HIGH, Phase2RiskClass.FINANCIAL_IRREVERSIBLE)
        if config.execution_mode == Phase2ExecutionMode.SHADOW and is_external:
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=risk_class,
                max_permitted_level=max_permitted_level,
                tenant_configured_level=tenant_level,
                effective_level=Phase2AutonomyLevel.OBSERVE_ONLY,
                execution_mode=config.execution_mode,
                is_permitted=False,
                requires_approval=False,
                block_reason=(
                    f"SHADOW MODE: Action {action_type.value} would execute externally, "
                    "but tenant is in shadow/observe-only mode. Action logged but not executed."
                ),
                policy_version=self._policy_version,
            )

        # 6A. RECOMMEND mode — only internal/low-risk actions permitted
        if config.execution_mode == Phase2ExecutionMode.RECOMMEND:
            if risk_class != Phase2RiskClass.LOW:
                return Phase2PolicyDecision(
                    action_type=action_type,
                    risk_class=risk_class,
                    max_permitted_level=max_permitted_level,
                    tenant_configured_level=tenant_level,
                    effective_level=Phase2AutonomyLevel.RECOMMEND,
                    execution_mode=config.execution_mode,
                    is_permitted=False,
                    requires_approval=False,
                    block_reason=(
                        f"RECOMMEND MODE: Only low-risk internal actions permitted. "
                        f"Action {action_type.value} (risk={risk_class.value}) requires higher mode."
                    ),
                    policy_version=self._policy_version,
                )

        # 6B. PREPARE mode (Stage 3) — prepare drafts, plans, shortlists; block external delivery
        if config.execution_mode == Phase2ExecutionMode.PREPARE:
            if risk_class != Phase2RiskClass.LOW:
                return Phase2PolicyDecision(
                    action_type=action_type,
                    risk_class=risk_class,
                    max_permitted_level=max_permitted_level,
                    tenant_configured_level=tenant_level,
                    effective_level=Phase2AutonomyLevel.PREPARE,
                    execution_mode=config.execution_mode,
                    is_permitted=False,
                    requires_approval=True,
                    block_reason=(
                        f"PREPARE MODE (Stage 3): Action {action_type.value} prepared in staging review queue; "
                        "external transmission is blocked in Stage 3."
                    ),
                    policy_version=self._policy_version,
                )

        # 7. Effective level gates
        if effective_level == Phase2AutonomyLevel.OBSERVE_ONLY:
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=risk_class,
                max_permitted_level=max_permitted_level,
                tenant_configured_level=tenant_level,
                effective_level=effective_level,
                execution_mode=config.execution_mode,
                is_permitted=False,
                requires_approval=False,
                block_reason="Effective autonomy level is OBSERVE_ONLY (0). No execution permitted.",
                policy_version=self._policy_version,
            )

        if effective_level == Phase2AutonomyLevel.REQUEST_APPROVAL or \
           (effective_level == Phase2AutonomyLevel.EXECUTE_APPROVED and risk_class == Phase2RiskClass.FINANCIAL_IRREVERSIBLE):
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=risk_class,
                max_permitted_level=max_permitted_level,
                tenant_configured_level=tenant_level,
                effective_level=effective_level,
                execution_mode=config.execution_mode,
                is_permitted=False,
                requires_approval=True,
                block_reason=f"Action requires explicit human approval (level={effective_level.name}, risk={risk_class.value}).",
                policy_version=self._policy_version,
            )

        # 8. Conditional autonomy conditions check (Section 74)
        conditions_met = []
        conditions_unmet = []
        for cond in conditions:
            if cond.is_met:
                conditions_met.append(cond.condition_id)
            else:
                conditions_unmet.append(cond.condition_id)

        if effective_level == Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS and conditions_unmet:
            return Phase2PolicyDecision(
                action_type=action_type,
                risk_class=risk_class,
                max_permitted_level=max_permitted_level,
                tenant_configured_level=tenant_level,
                effective_level=effective_level,
                execution_mode=config.execution_mode,
                is_permitted=False,
                requires_approval=True,
                block_reason=(
                    f"CONDITIONALLY_AUTONOMOUS: {len(conditions_unmet)} required conditions unmet: "
                    f"{conditions_unmet}. Escalating to human approval."
                ),
                policy_version=self._policy_version,
                policy_conditions_met=conditions_met,
                policy_conditions_unmet=conditions_unmet,
            )

        # 9. Execution permitted
        return Phase2PolicyDecision(
            action_type=action_type,
            risk_class=risk_class,
            max_permitted_level=max_permitted_level,
            tenant_configured_level=tenant_level,
            effective_level=effective_level,
            execution_mode=config.execution_mode,
            is_permitted=True,
            requires_approval=False,
            block_reason=None,
            policy_version=self._policy_version,
            policy_conditions_met=conditions_met,
            policy_conditions_unmet=conditions_unmet,
        )

    def evaluate_batch(
        self,
        organization_id: str,
        action_types: List[Phase2ActionType],
    ) -> Dict[str, Phase2PolicyDecision]:
        """Evaluates multiple actions for a tenant. Used by agent plan validation."""
        return {
            action_type.value: self.evaluate(organization_id, action_type)
            for action_type in action_types
        }

    # ── Pilot Deployment Helpers (Sections 72, 79, 98) ────────────────────────

    def set_shadow_mode(self, organization_id: str, configured_by: str = "SYSTEM") -> TenantAutonomyConfig:
        """Puts tenant into Stage 1: Shadow mode. No external actions."""
        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=Phase2ExecutionMode.SHADOW,
            configured_by=configured_by,
            reason="Pilot Stage 1: Shadow Mode Activation",
        )

    def set_recommend_mode(self, organization_id: str, configured_by: str = "SYSTEM") -> TenantAutonomyConfig:
        """Puts tenant into Stage 2: Recommend mode. Surfaces but does not execute external actions."""
        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=Phase2ExecutionMode.RECOMMEND,
            default_level_low_risk=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
            default_level_medium_risk=Phase2AutonomyLevel.RECOMMEND,
            default_level_high_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
            default_level_financial=Phase2AutonomyLevel.OBSERVE_ONLY,
            configured_by=configured_by,
            reason="Pilot Stage 2: Recommend Mode Activation",
        )

    def set_prepare_mode(self, organization_id: str, configured_by: str = "SYSTEM") -> TenantAutonomyConfig:
        """
        Stage 3: Prepare / Staging Simulation Mode (Resolves Pilot Lifecycle Gap — Section 72).
        Prepares drafts, plans, and shortlists into review staging. Zero external transmission.
        """
        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=Phase2ExecutionMode.PREPARE,
            default_level_low_risk=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
            default_level_medium_risk=Phase2AutonomyLevel.PREPARE,
            default_level_high_risk=Phase2AutonomyLevel.OBSERVE_ONLY,
            default_level_financial=Phase2AutonomyLevel.OBSERVE_ONLY,
            configured_by=configured_by,
            reason="Pilot Stage 3: Prepare / Staging Simulation Mode Activation",
        )

    def set_approval_mode(self, organization_id: str, configured_by: str = "SYSTEM") -> TenantAutonomyConfig:
        """Puts tenant into Stage 4: Approval-based execution mode."""
        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=Phase2ExecutionMode.APPROVAL,
            default_level_low_risk=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
            default_level_medium_risk=Phase2AutonomyLevel.REQUEST_APPROVAL,
            default_level_high_risk=Phase2AutonomyLevel.REQUEST_APPROVAL,
            default_level_financial=Phase2AutonomyLevel.REQUEST_APPROVAL,
            configured_by=configured_by,
            reason="Pilot Stage 4: Approval Mode Activation",
        )

    def set_live_limited_mode(
        self,
        organization_id: str,
        configured_by: str = "PILOT_LEAD",
        reason: str = "Pilot Stage 5 Activation",
    ) -> TenantAutonomyConfig:
        """
        Stage 5: Limited live autonomous execution (Section 79).
        Requires explicit authorized stakeholder identity.
        """
        if not configured_by or configured_by.strip() == "":
            raise ValueError("Live-limited mode requires explicit authorized stakeholder identity (Section 79).")

        return self.configure_tenant(
            organization_id=organization_id,
            execution_mode=Phase2ExecutionMode.LIVE,
            default_level_low_risk=Phase2AutonomyLevel.AUTONOMOUS_GOVERNED,
            default_level_medium_risk=Phase2AutonomyLevel.CONDITIONALLY_AUTONOMOUS,
            default_level_high_risk=Phase2AutonomyLevel.EXECUTE_APPROVED,
            default_level_financial=Phase2AutonomyLevel.REQUEST_APPROVAL,
            configured_by=configured_by,
            reason=reason,
        )


# ─── 10. Module-level singleton (lazy initialization) ────────────────────────

_policy_engine_instance: Optional[RevenueActionPolicyEngine] = None


def get_policy_engine() -> RevenueActionPolicyEngine:
    """Returns the singleton Revenue Action Policy Engine instance."""
    global _policy_engine_instance
    if _policy_engine_instance is None:
        _policy_engine_instance = RevenueActionPolicyEngine()
    return _policy_engine_instance
