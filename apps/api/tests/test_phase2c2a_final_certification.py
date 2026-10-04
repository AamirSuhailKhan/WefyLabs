"""
Phase 2C.2A — Residual Shadow Evidence Window & Final Certification Suite
==========================================================================
Test sections:
  A: Precise provider telemetry terminology (Sections 14-16)
  B: Human decision completeness & SLA (Sections 6-7)
  C: Daily snapshot persistence with hash locking (Sections 5, 27-28)
  D: Material change tracking (Section 13)
  E: Incident register from audit chain (Section 18)
  F: Stage-1 gate evaluation matrix E13-E24 (Section 35)
  G: Evidence reproducibility: application == DB reconstruction (Section 23)
  H: Final evidence snapshot (Sections 29-30)
  I: No auto-promotion (Sections 37, 43, 45)
  J: Final certification vocabulary (Section 42)
"""
import asyncio
import hashlib
import inspect
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.autonomous_loop.phase2c_durable_models import (
    PilotTenant,
    PilotObservation,
    PilotAuditEvent,
    PilotMetricSnapshot,
    PilotActionRecord,
    PilotStageTransition,
    PilotEvidenceRecord,
)
from app.modules.autonomous_loop.phase2c_pilot_repository import (
    PilotRepository,
    MINIMUM_SHADOW_SAMPLE,
    MINIMUM_STAGE_DAYS,
)

# ---------------------------------------------------------------------------
# Mock helpers — each returns an object that replicates the AsyncSession return
# ---------------------------------------------------------------------------

def _scalar(value):
    """Returns a mock where .scalar() == value (for scalar COUNT queries)."""
    m = MagicMock()
    m.scalar.return_value = value
    return m


def _scalars_all(items):
    """Returns a mock where .scalars().all() == items (for select queries)."""
    m = MagicMock()
    m.scalars.return_value.all.return_value = items
    return m


def _scalar_one(value):
    """Returns a mock where .scalar_one_or_none() == value."""
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


def _all(rows):
    """Returns a mock where .all() == rows (for .distinct() result sets)."""
    m = MagicMock()
    m.all.return_value = rows
    return m


def _make_pilot(org_id: str = "org-2a", pilot_id: str = "p-2a",
                days_elapsed: int = 0) -> PilotTenant:
    enrolled = datetime.now(timezone.utc) - timedelta(days=days_elapsed)
    return PilotTenant(
        id=pilot_id,
        organization_id=org_id,
        current_stage="STAGE_1_SHADOW",
        pilot_status="ACTIVE",
        enrolled_by="admin",
        enrolled_at=enrolled,
        stage_entered_at=enrolled,
        policy_version="phase2-v1.0",
    )


def _audit_mocks():
    """2 mocks needed by _append_audit_event: seq lookup + count."""
    return [_scalar_one(None), _scalar(0)]


# ===========================================================================
# SECTION A - Precise Provider Telemetry (Sections 14-16)
# ===========================================================================

class TestPreciseProviderTelemetry:

    def test_a1_all_shadow_blocked_satisfies_stage1_invariant(self):
        """
        A1: 14 SHADOW_PROJECTED records.
          dispatch_requests=14, boundary_blocks=14, network_calls=0
          -> stage_1_invariant_satisfied = True
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            records = []
            for _ in range(14):
                r = MagicMock()
                r.semantic_state = "SHADOW_PROJECTED"
                r.provider_request_id = None
                records.append(r)

            mock_db.execute = AsyncMock(return_value=_scalars_all(records))

            telem = await repo.get_precise_provider_telemetry("org-a1", "p-a1")

            assert telem["provider_dispatch_requests"] == 14
            assert telem["provider_boundary_blocks"] == 14
            assert telem["provider_network_calls"] == 0
            assert telem["provider_acceptances"] == 0
            assert telem["provider_deliveries"] == 0
            assert telem["stage_1_invariant_satisfied"] is True

        asyncio.run(run())

    def test_a2_executed_state_registers_network_call(self):
        """
        A2: EXECUTED state -> network_call=1, invariant=False.
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            r = MagicMock()
            r.semantic_state = "EXECUTED"
            r.provider_request_id = "prov-req-001"

            mock_db.execute = AsyncMock(return_value=_scalars_all([r]))

            telem = await repo.get_precise_provider_telemetry("org-a2")

            assert telem["provider_dispatch_requests"] == 1
            assert telem["provider_boundary_blocks"] == 0
            assert telem["provider_network_calls"] == 1
            assert telem["stage_1_invariant_satisfied"] is False

        asyncio.run(run())

    def test_a3_delivered_increments_all_three_downstream_counters(self):
        """
        A3: PROVIDER_DELIVERED increments network_calls, acceptances, deliveries.
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            r = MagicMock()
            r.semantic_state = "PROVIDER_DELIVERED"
            r.provider_request_id = "prov-req-002"

            mock_db.execute = AsyncMock(return_value=_scalars_all([r]))

            telem = await repo.get_precise_provider_telemetry("org-a3")

            assert telem["provider_dispatch_requests"] == 1
            assert telem["provider_network_calls"] == 1
            assert telem["provider_acceptances"] == 1
            assert telem["provider_deliveries"] == 1
            assert telem["stage_1_invariant_satisfied"] is False

        asyncio.run(run())

    def test_a4_mixed_states_produce_correct_segregated_counts(self):
        """
        A4: 10 blocked + 2 executing/executed + 1 accepted + 1 delivered
            -> dispatch=14, blocked=10, network=4, accepted=2, delivered=1
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            records = []
            for _ in range(10):
                r = MagicMock()
                r.semantic_state = "BLOCKED_STAGE1"
                r.provider_request_id = None
                records.append(r)
            for state in ["EXECUTING", "EXECUTED", "PROVIDER_ACCEPTED", "PROVIDER_DELIVERED"]:
                r = MagicMock()
                r.semantic_state = state
                r.provider_request_id = f"req-{state}"
                records.append(r)

            mock_db.execute = AsyncMock(return_value=_scalars_all(records))

            telem = await repo.get_precise_provider_telemetry("org-a4")

            assert telem["provider_dispatch_requests"] == 14
            assert telem["provider_boundary_blocks"] == 10
            assert telem["provider_network_calls"] == 4
            assert telem["provider_acceptances"] == 2  # ACCEPTED + DELIVERED
            assert telem["provider_deliveries"] == 1
            assert telem["stage_1_invariant_satisfied"] is False

        asyncio.run(run())

    def test_a5_zero_records_satisfies_stage1_invariant(self):
        """A5: No action records -> all-zero telemetry, invariant satisfied."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.execute = AsyncMock(return_value=_scalars_all([]))

            telem = await repo.get_precise_provider_telemetry("org-a5")

            assert telem["total_action_records"] == 0
            assert telem["stage_1_invariant_satisfied"] is True

        asyncio.run(run())


# ===========================================================================
# SECTION B - Human Decision Completeness & SLA (Sections 6-7)
# ===========================================================================

class TestHumanDecisionCompleteness:

    def test_b1_below_50pct_is_accumulating(self):
        """B1: 6/14 = 42.9% -> ACCUMULATING."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(14),  # total
                _scalar(6),   # decided
                _scalar(0),   # overdue
            ])

            result = await repo.get_human_decision_completeness("org-b1", "p-b1")

            assert result["total_observations"] == 14
            assert result["decisions_recorded"] == 6
            assert result["pending_decisions"] == 8
            assert result["decision_completeness_pct"] == 42.9
            assert result["status"] == "ACCUMULATING"

        asyncio.run(run())

    def test_b2_exactly_50pct_satisfies_threshold(self):
        """B2: 7/14 = 50.0% -> THRESHOLD_SATISFIED (boundary condition)."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(14),
                _scalar(7),
                _scalar(0),
            ])

            result = await repo.get_human_decision_completeness("org-b2", "p-b2")

            assert result["decision_completeness_pct"] == 50.0
            assert result["status"] == "THRESHOLD_SATISFIED"

        asyncio.run(run())

    def test_b3_overdue_tracked_independently_from_abandoned(self):
        """B3: Overdue pending != abandoned — separate tracking."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(20),
                _scalar(8),
                _scalar(5),  # overdue > 4h
            ])

            result = await repo.get_human_decision_completeness(
                "org-b3", "p-b3", overdue_threshold_hours=4
            )

            assert result["pending_decisions"] == 12
            assert result["overdue_decisions"] == 5
            assert result["abandoned_decisions"] == 0
            assert result["overdue_threshold_hours"] == 4

        asyncio.run(run())

    def test_b4_zero_observations_returns_no_observations_status(self):
        """B4: Zero observations -> NO_OBSERVATIONS (not a false pass)."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(0), _scalar(0), _scalar(0),
            ])

            result = await repo.get_human_decision_completeness("org-b4")

            assert result["status"] == "NO_OBSERVATIONS"
            assert result["decision_completeness_pct"] == 0.0

        asyncio.run(run())

    def test_b5_above_50pct_returns_threshold_satisfied(self):
        """B5: 80% -> THRESHOLD_SATISFIED."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(100), _scalar(80), _scalar(3),
            ])

            result = await repo.get_human_decision_completeness("org-b5")

            assert result["decision_completeness_pct"] == 80.0
            assert result["status"] == "THRESHOLD_SATISFIED"

        asyncio.run(run())


# ===========================================================================
# SECTION C - Daily Snapshot Persistence & Hash Locking (Sections 5, 27-28)
# ===========================================================================

class TestDailySnapshotPersistence:

    def test_c1_daily_snapshot_persisted_with_locked_hash(self):
        """C1: Snapshot returns locked=True with 64-char SHA-256 hash."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()

            result = await repo.persist_daily_snapshot(
                organization_id="org-c1",
                pilot_id="p-c1",
                snapshot_date="2026-10-01",
                snapshot_data={
                    "stage": "STAGE_1_SHADOW",
                    "eligible_observations": 6,
                    "exact_agreement": 4,
                    "semantic_agreement": 1,
                    "abstention": 0,
                    "shadow_accuracy": 0.8333,
                    "provider_boundary_blocks": 14,
                    "provider_network_calls": 0,
                },
            )

            assert result["locked"] is True
            assert len(result["snapshot_hash"]) == 64
            assert result["snapshot_date"] == "2026-10-01"
            assert result["metric_name"] == "daily_evidence_snapshot:2026-10-01"
            mock_db.add.assert_called_once()

        asyncio.run(run())

    def test_c2_hash_is_deterministic_and_tamper_detectable(self):
        """C2: Same input -> same hash. Any change -> different hash."""
        base = {"eligible_observations": 6, "shadow_accuracy": 0.8333}
        p1 = {"pilot_id": "p", "organization_id": "o", "snapshot_date": "2026-10-01", **base}
        p2 = dict(p1)
        p2["eligible_observations"] = 7

        h1 = hashlib.sha256(json.dumps(p1, sort_keys=True, default=str).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(p2, sort_keys=True, default=str).encode()).hexdigest()

        assert h1 != h2
        assert len(h1) == 64

    def test_c3_metric_name_includes_date(self):
        """C3: metric_name == 'daily_evidence_snapshot:YYYY-MM-DD'."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()

            result = await repo.persist_daily_snapshot(
                "org-c3", "p-c3", "2026-10-14",
                {"shadow_accuracy": 0.72, "eligible_observations": 52},
            )

            assert result["metric_name"] == "daily_evidence_snapshot:2026-10-14"

        asyncio.run(run())

    def test_c4_numerator_sums_exact_plus_semantic_plus_abstention(self):
        """C4: numerator = exact + semantic + abstention."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()

            await repo.persist_daily_snapshot(
                "org-c4", "p-c4", "2026-10-02",
                {"eligible_observations": 10, "exact_agreement": 5,
                 "semantic_agreement": 2, "abstention": 1, "shadow_accuracy": 0.8},
            )
            added = mock_db.add.call_args[0][0]
            assert added.numerator == 8  # 5 + 2 + 1

        asyncio.run(run())


# ===========================================================================
# SECTION D - Material Change Protocol (Section 13)
# ===========================================================================

class TestMaterialChangeProtocol:

    def test_d1_policy_version_change_recorded(self):
        """D1: Policy version change captured with full metadata."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=_audit_mocks())

            change = await repo.record_material_change(
                organization_id="org-d1", pilot_id="p-d1",
                change_type="POLICY_VERSION",
                from_version="phase2-v1.0", to_version="phase2-v1.1",
                changed_by="platform-engineer", notes="Threshold adjustment.",
            )

            assert change["change_type"] == "POLICY_VERSION"
            assert change["from_version"] == "phase2-v1.0"
            assert change["to_version"] == "phase2-v1.1"
            assert "changed_at" in change
            assert "affected_observations_from" in change

        asyncio.run(run())

    def test_d2_affected_observation_timestamp_preserved(self):
        """D2: affected_observations_after stored for evidence segmentation."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=_audit_mocks())

            boundary = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
            change = await repo.record_material_change(
                "org-d2", "p-d2", "AGENT_VERSION",
                "2.1.0", "2.1.1", "engineer",
                affected_observations_after=boundary,
            )

            assert "2026-10-05" in change["affected_observations_from"]

        asyncio.run(run())


# ===========================================================================
# SECTION E - Incident Register (Section 18)
# ===========================================================================

class TestIncidentRegister:

    def test_e1_qualifying_incident_recorded(self):
        """E1: Safety incident recorded in audit chain with full classification."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=_audit_mocks())

            incident = await repo.record_incident(
                organization_id="org-e1", pilot_id="p-e1",
                incident_type="UNAUTHORIZED_OUTBOUND_COMMUNICATION",
                description="WhatsApp message sent despite Stage-1 boundary.",
                reported_by="sre-oncall", severity="CRITICAL",
            )

            assert incident["incident_type"] == "UNAUTHORIZED_OUTBOUND_COMMUNICATION"
            assert incident["severity"] == "CRITICAL"
            assert incident["status"] == "OPEN"
            assert "incident_id" in incident

        asyncio.run(run())

    def test_e2_zero_incidents_stage1_safe(self):
        """E2: Empty register -> stage_1_safe = True."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.execute = AsyncMock(return_value=_scalars_all([]))

            reg = await repo.get_incident_register("org-e2", "p-e2")

            assert reg["qualifying_incidents"] == 0
            assert reg["stage_1_safe"] is True

        asyncio.run(run())

    def test_e3_open_incident_fails_stage1_safety(self):
        """E3: One open incident -> stage_1_safe = False."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            evt = MagicMock()
            evt.payload = {"incident_type": "CROSS_TENANT_ACCESS", "status": "OPEN"}
            evt.occurred_at = datetime.now(timezone.utc)

            mock_db.execute = AsyncMock(return_value=_scalars_all([evt]))

            reg = await repo.get_incident_register("org-e3", "p-e3")

            assert reg["qualifying_incidents"] == 1
            assert reg["open_incidents"] == 1
            assert reg["stage_1_safe"] is False

        asyncio.run(run())

    def test_e4_incident_source_is_immutable_audit_chain(self):
        """E4: Register reads from pilot_audit_events (immutable, append-only)."""
        src = inspect.getsource(PilotRepository.get_incident_register)
        assert "SAFETY_INCIDENT_RECORDED" in src
        assert "PilotAuditEvent" in src


# ===========================================================================
# SECTION F - Stage-1 Gate Evaluation Matrix (Section 35)
# ===========================================================================

class TestStage1GateEvaluation:
    """
    Mock side-effect layout for evaluate_stage1_gates:
      [0]  get_pilot_tenant              -> _scalar_one(pilot)
      [1]  compute_shadow_accuracy total -> _scalar(N)
              if N < 50: early return, numerator query skipped
              if N >= 50: [2] numerator -> _scalar(M)
      [next] get_human_decision_completeness:
               total, decided, overdue   -> 3x _scalar
      [next] harmful count               -> _scalar
      [next] get_incident_register       -> _scalars_all
      [next] get_precise_provider_telemetry -> _scalars_all
      [next] snapshot count (E20)        -> _scalar
      [next] verify_evidence_reproducibility:
               compute_shadow_accuracy total -> _scalar (early-return if < 50)
               db_numerator                 -> _scalar
               db_denominator               -> _scalar
      [next] _verify_outcome_linkage_schema -> _scalars_all (limit 1)
      [next] review count (E23)          -> _scalar
    """

    def _side_effects_sub50_sample(self, pilot, obs_total=6, obs_eligible=6,
                                   numerator=5, hd_total=14, hd_decided=6, hd_overdue=0,
                                   harmful=0, incidents=None, prov_records=None,
                                   snapshots=1, vr_db_num=5, vr_db_denom=6,
                                   linkage=None, reviews=0):
        """
        Side effects when compute_shadow_accuracy total < 50 (early returns after 1 query).
        """
        return [
            _scalar_one(pilot),      # get_pilot_tenant
            _scalar(obs_total),      # compute_shadow_accuracy: total (< 50, early return)
            _scalar(hd_total),       # decision completeness: total
            _scalar(hd_decided),     # decision completeness: decided
            _scalar(hd_overdue),     # decision completeness: overdue
            _scalar(harmful),        # harmful count
            _scalars_all(incidents or []),   # incident register
            _scalars_all(prov_records or []), # provider telemetry
            _scalar(snapshots),      # snapshot count E20
            _scalar(obs_total),      # reproducibility: compute_shadow_accuracy total (early return)
            _scalar(vr_db_num),      # reproducibility: db numerator
            _scalar(vr_db_denom),    # reproducibility: db denominator
            _scalars_all(linkage or []),  # outcome linkage schema
            _scalar(reviews),        # review count E23
        ]

    def _side_effects_gte50_sample(self, pilot, obs_total=52, numerator=40,
                                   hd_total=52, hd_decided=30, hd_overdue=0,
                                   harmful=0, incidents=None, prov_records=None,
                                   snapshots=14, vr_db_num=40, vr_db_denom=52,
                                   linkage=None, reviews=0):
        """
        Side effects when compute_shadow_accuracy total >= 50 (2 queries: total + numerator).
        """
        return [
            _scalar_one(pilot),       # get_pilot_tenant
            _scalar(obs_total),       # compute_shadow_accuracy: total (>= 50)
            _scalar(numerator),       # compute_shadow_accuracy: numerator
            _scalar(hd_total),        # decision completeness: total
            _scalar(hd_decided),      # decision completeness: decided
            _scalar(hd_overdue),      # decision completeness: overdue
            _scalar(harmful),         # harmful count
            _scalars_all(incidents or []),    # incident register
            _scalars_all(prov_records or []), # provider telemetry
            _scalar(snapshots),       # snapshot count E20
            _scalar(obs_total),       # reproducibility: compute total (>= 50)
            _scalar(numerator),       # reproducibility: compute numerator
            _scalar(vr_db_num),       # reproducibility: db numerator
            _scalar(vr_db_denom),     # reproducibility: db denominator
            _scalars_all(linkage or []),  # outcome linkage schema
            _scalar(reviews),         # review count E23
        ]

    def test_f1_day0_fails_e13_window_gate(self):
        """F1: Day 0 fails E13, overall_eligible=False, status=BLOCKED."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-f1", "p-f1", days_elapsed=0)

            mock_db.execute = AsyncMock(
                side_effect=self._side_effects_sub50_sample(pilot)
            )

            result = await repo.evaluate_stage1_gates("org-f1")

            assert result["overall_eligible"] is False
            assert result["stage_2_approval_status"] == "BLOCKED"
            gates = {g["gate_id"]: g for g in result["gates"]}
            assert gates["E13"]["status"] == "INSUFFICIENT_EVIDENCE"
            assert gates["E13"]["observed_value"] == 0
            assert gates["E24"]["status"] != "ELIGIBLE"

        asyncio.run(run())

    def test_f2_e23_blocked_without_human_review(self):
        """F2: No REVIEW_DECISION transition -> E23 = BLOCKED."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-f2", "p-f2", days_elapsed=15)

            mock_db.execute = AsyncMock(
                side_effect=self._side_effects_gte50_sample(pilot, reviews=0)
            )

            result = await repo.evaluate_stage1_gates("org-f2")
            gates = {g["gate_id"]: g for g in result["gates"]}

            assert gates["E23"]["status"] == "BLOCKED"

        asyncio.run(run())

    def test_f3_e19_fails_on_network_calls(self):
        """F3: One EXECUTED action record -> E19 = FAIL."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-f3", "p-f3", days_elapsed=15)

            bad_action = MagicMock()
            bad_action.semantic_state = "EXECUTED"
            bad_action.provider_request_id = "req-000"

            mock_db.execute = AsyncMock(
                side_effect=self._side_effects_gte50_sample(
                    pilot, prov_records=[bad_action], reviews=1
                )
            )

            result = await repo.evaluate_stage1_gates("org-f3")
            gates = {g["gate_id"]: g for g in result["gates"]}

            assert gates["E19"]["status"] == "FAIL"
            assert gates["E19"]["observed_value"] == 1
            assert result["overall_eligible"] is False

        asyncio.run(run())

    def test_f4_unenrolled_tenant_returns_invalid(self):
        """F4: Unenrolled tenant -> status=INVALID, gates=[], overall_eligible=False."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.execute = AsyncMock(return_value=_scalar_one(None))

            result = await repo.evaluate_stage1_gates("org-nonexistent")

            assert result["status"] == "INVALID"
            assert result["gates"] == []
            assert result["overall_eligible"] is False

        asyncio.run(run())

    def test_f5_e18_fails_with_open_safety_incident(self):
        """F5: One qualifying incident -> E18 = FAIL."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-f5", "p-f5", days_elapsed=15)

            bad_evt = MagicMock()
            bad_evt.payload = {"status": "OPEN", "incident_type": "CONSENT_VIOLATION"}
            bad_evt.occurred_at = datetime.now(timezone.utc)

            mock_db.execute = AsyncMock(
                side_effect=self._side_effects_gte50_sample(
                    pilot, incidents=[bad_evt], reviews=1
                )
            )

            result = await repo.evaluate_stage1_gates("org-f5")
            gates = {g["gate_id"]: g for g in result["gates"]}

            assert gates["E18"]["status"] == "FAIL"
            assert result["overall_eligible"] is False

        asyncio.run(run())

    def test_f6_all_required_gate_ids_present(self):
        """F6: Gate IDs E13-E24 all present in evaluation result."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-f6", "p-f6", days_elapsed=0)

            mock_db.execute = AsyncMock(
                side_effect=self._side_effects_sub50_sample(pilot)
            )

            result = await repo.evaluate_stage1_gates("org-f6")
            gate_ids = {g["gate_id"] for g in result["gates"]}

            expected = {"E13","E14","E15","E16","E17","E18","E19","E20","E21","E22","E23","E24"}
            assert gate_ids == expected

        asyncio.run(run())


# ===========================================================================
# SECTION G - Evidence Reproducibility (Section 23)
# ===========================================================================

class TestEvidenceReproducibility:
    """
    verify_evidence_reproducibility side-effects:
      compute_shadow_accuracy: 1 query (total < 50, early return) -> INSUFFICIENT_DATA
        returned, numerator=0, denominator=total
      OR
      compute_shadow_accuracy: 2 queries (total >= 50) -> full result
      Then 2 independent DB queries: db_num, db_denom
    """

    def test_g1_matching_counts_produce_pass(self):
        """G1: App and DB agree on 40/52 -> match=True, status=PASS."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # compute_shadow_accuracy: total=52 (>= 50), numerator=40
            # then: db_num=40, db_denom=52
            mock_db.execute = AsyncMock(side_effect=[
                _scalar(52),  # compute total
                _scalar(40),  # compute numerator
                _scalar(40),  # db numerator
                _scalar(52),  # db denominator
            ])

            result = await repo.verify_evidence_reproducibility("org-g1", "p-g1")

            assert result["match"] is True
            assert result["status"] == "PASS"
            assert result["application_numerator"] == 40
            assert result["db_reconstruction_numerator"] == 40
            assert result["discrepancy"] is None

        asyncio.run(run())

    def test_g2_numerator_mismatch_produces_fail_with_discrepancy(self):
        """G2: App=40, DB=38 -> match=False, discrepancy recorded."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(52),
                _scalar(40),  # app numerator
                _scalar(38),  # db numerator (MISMATCH)
                _scalar(52),
            ])

            result = await repo.verify_evidence_reproducibility("org-g2", "p-g2")

            assert result["match"] is False
            assert result["status"] == "FAIL"
            assert result["discrepancy"] is not None
            assert result["discrepancy"]["numerator_delta"] == -2  # 38 - 40

        asyncio.run(run())

    def test_g3_zero_observations_both_sides_agree(self):
        """G3: Total < 50 -> early return, app_num=0. DB returns 0. match=True."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            # compute_shadow_accuracy returns early (total=0 < 50)
            # app_numerator=0, app_denominator=0 from early return
            mock_db.execute = AsyncMock(side_effect=[
                _scalar(0),  # compute total (< 50, early return)
                _scalar(0),  # db_numerator
                _scalar(0),  # db_denominator
            ])

            result = await repo.verify_evidence_reproducibility("org-g3", "p-g3")

            assert result["match"] is True
            assert result["application_accuracy"] == 0.0
            assert result["db_reconstruction_accuracy"] == 0.0

        asyncio.run(run())

    def test_g4_denominator_mismatch_produces_fail(self):
        """G4: Same numerator, different denominators -> FAIL."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar(52),  # app total (denom)
                _scalar(40),  # app numerator
                _scalar(40),  # db num (same)
                _scalar(53),  # db denom (off by one!)
            ])

            result = await repo.verify_evidence_reproducibility("org-g4", "p-g4")

            assert result["match"] is False
            assert result["discrepancy"]["denominator_delta"] == 1  # 53 - 52

        asyncio.run(run())


# ===========================================================================
# SECTION H - Final Evidence Snapshot (Sections 29-30)
# ===========================================================================

class TestFinalEvidenceSnapshot:

    def test_h1_unenrolled_tenant_returns_invalid(self):
        """H1: Unenrolled tenant -> status=INVALID."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.execute = AsyncMock(return_value=_scalar_one(None))

            result = await repo.generate_final_evidence_snapshot("org-missing")

            assert result["status"] == "INVALID"
            assert "reason" in result

        asyncio.run(run())

    def test_h2_evidence_hash_is_64char_sha256(self):
        """H2: SHA-256 always produces 64-char hex output."""
        snap = {"pilot_id": "p-h2", "eligible_observations": 55}
        h = hashlib.sha256(
            json.dumps(snap, sort_keys=True, default=str).encode()
        ).hexdigest()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_h3_tampered_snapshot_changes_hash(self):
        """H3: Any field change -> different hash (tamper detection)."""
        base = {"eligible_observations": 55, "shadow_accuracy": 0.7636}
        h1 = hashlib.sha256(json.dumps(base, sort_keys=True, default=str).encode()).hexdigest()
        base["shadow_accuracy"] = 0.9999
        h2 = hashlib.sha256(json.dumps(base, sort_keys=True, default=str).encode()).hexdigest()
        assert h1 != h2

    def test_h4_to_stage_proposed_is_stage2_recommend(self):
        """
        H4: to_stage_proposed == STAGE_2_RECOMMEND.
        Never STAGE_3 or any autonomous execution stage.
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()

            pilot = _make_pilot("org-h4", "p-h4", days_elapsed=14)

            # generate_final_evidence_snapshot query order:
            # 1. get_pilot_tenant -> scalar_one
            # 2. get_pilot_stats: total_obs, eligible_obs, pending -> 3 scalars
            # 3. comparison breakdown: 6 categories -> 6 scalars
            # 4. compute_shadow_accuracy: total (< 50 -> early return, 1 query)
            # 5. get_precise_provider_telemetry -> scalars_all
            # 6. get_incident_register -> scalars_all
            # 7. agent domains distinct query -> _all([])
            # 8. get_human_decision_completeness: total, decided, overdue -> 3 scalars
            # 9. sealed snapshot count -> scalar
            # 10. _append_audit_event: seq, count -> _scalar_one, _scalar
            mock_db.execute = AsyncMock(side_effect=[
                _scalar_one(pilot),             # get_pilot_tenant
                _scalar(60), _scalar(6), _scalar(0),  # get_pilot_stats (6 eligible < 50)
                *[_scalar(v) for v in [38, 12, 2, 1, 0, 2]],  # 6 category counts
                _scalar(6),                     # compute_shadow_accuracy total (< 50, early)
                _scalars_all([]),               # provider telemetry
                _scalars_all([]),               # incident register
                _all([]),                       # agent domains distinct
                _scalar(60), _scalar(40), _scalar(0),  # decision completeness
                _scalar(14),                    # sealed snapshots
                *_audit_mocks(),                # _append_audit_event
            ])

            snapshot = await repo.generate_final_evidence_snapshot("org-h4")

            assert snapshot["to_stage_proposed"] == "STAGE_2_RECOMMEND"
            assert "STAGE_3" not in snapshot["to_stage_proposed"]
            assert "AUTONOMOUS" not in snapshot["to_stage_proposed"]
            assert "evidence_hash" in snapshot
            assert len(snapshot["evidence_hash"]) == 64

        asyncio.run(run())

    def test_h5_required_fields_present_in_snapshot(self):
        """H5: Final snapshot contains all Section-29 required fields."""
        required = [
            "pilot_id", "organization_id", "from_stage", "to_stage_proposed",
            "window_start", "window_end", "elapsed_days",
            "total_observations", "eligible_observations",
            "human_decision_count", "decision_completeness_pct",
            "exact_agreement", "semantic_agreement", "abstention",
            "acceptable_disagreement", "harmful_disagreement",
            "shadow_accuracy", "minimum_required_accuracy", "minimum_required_sample",
            "provider_dispatch_requests", "provider_boundary_blocks",
            "provider_network_calls", "provider_acceptances", "provider_deliveries",
            "stage_1_provider_invariant",
            "qualifying_safety_incidents", "stage_1_safe",
            "agent_coverage_count", "agents_with_real_observations",
            "application_version", "policy_version", "calculation_version",
            "evidence_hash",
        ]

        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            mock_db.flush = AsyncMock()

            pilot = _make_pilot("org-h5", "p-h5", days_elapsed=14)

            mock_db.execute = AsyncMock(side_effect=[
                _scalar_one(pilot),
                _scalar(60), _scalar(6), _scalar(0),
                *[_scalar(v) for v in [38, 12, 2, 1, 0, 2]],
                _scalar(6),  # shadow accuracy total (early return)
                _scalars_all([]),
                _scalars_all([]),
                _all([]),
                _scalar(60), _scalar(40), _scalar(0),
                _scalar(14),
                *_audit_mocks(),
            ])

            snapshot = await repo.generate_final_evidence_snapshot("org-h5")

            for field in required:
                assert field in snapshot, f"Missing required field: {field}"

        asyncio.run(run())


# ===========================================================================
# SECTION I - No Auto-Promotion (Sections 37, 43, 45)
# ===========================================================================

class TestNoAutopromotion:

    def test_i1_blocked_status_when_day1(self):
        """I1: Day 1 -> BLOCKED. No PilotStageTransition created."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-i1", "p-i1", days_elapsed=1)

            mock_db.execute = AsyncMock(
                side_effect=[
                    _scalar_one(pilot),
                    _scalar(14),     # compute_shadow_accuracy total (< 50, early return)
                    _scalar(14), _scalar(6), _scalar(0),
                    _scalar(0),
                    _scalars_all([]), _scalars_all([]),
                    _scalar(1),
                    _scalar(14),     # repro: compute total (< 50, early return)
                    _scalar(5), _scalar(6),
                    _scalars_all([]),
                    _scalar(0),
                ]
            )

            result = await repo.evaluate_stage1_gates("org-i1")

            assert result["stage_2_approval_status"] == "BLOCKED"
            assert result["overall_eligible"] is False
            mock_db.add.assert_not_called()

        asyncio.run(run())

    def test_i2_15_days_but_sample_below_50_still_blocked(self):
        """
        I2: 15 days elapsed, 30 eligible (< 50).
          E13=PASS, E14=INSUFFICIENT_EVIDENCE, overall_eligible=False.
        """
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-i2", "p-i2", days_elapsed=15)

            mock_db.execute = AsyncMock(
                side_effect=[
                    _scalar_one(pilot),
                    _scalar(30),     # compute total (< 50, early return)
                    _scalar(30), _scalar(20), _scalar(0),
                    _scalar(0),
                    _scalars_all([]), _scalars_all([]),
                    _scalar(15),
                    _scalar(30),     # repro total (< 50, early return)
                    _scalar(22), _scalar(30),
                    _scalars_all([]),
                    _scalar(0),
                ]
            )

            result = await repo.evaluate_stage1_gates("org-i2")
            gates = {g["gate_id"]: g for g in result["gates"]}

            assert gates["E13"]["status"] == "PASS"
            assert gates["E14"]["status"] == "INSUFFICIENT_EVIDENCE"
            assert result["overall_eligible"] is False

        asyncio.run(run())

    def test_i3_eligible_not_equal_to_approved(self):
        """I3: record_stage2_review requires decision + reviewer_id + evidence_hash."""
        sig = inspect.signature(PilotRepository.record_stage2_review)
        assert "decision" in sig.parameters
        assert "reviewer_id" in sig.parameters
        assert "evidence_hash" in sig.parameters

    def test_i4_four_independent_question_methods_exist(self):
        """I4: Q1-Q4 independently answerable via separate methods."""
        assert hasattr(PilotRepository, "evaluate_stage1_gates")
        assert hasattr(PilotRepository, "record_stage2_review")
        assert hasattr(PilotRepository, "verify_evidence_reproducibility")
        assert hasattr(PilotRepository, "get_precise_provider_telemetry")
        assert hasattr(PilotRepository, "generate_final_evidence_snapshot")
        assert hasattr(PilotRepository, "get_incident_register")
        assert hasattr(PilotRepository, "persist_daily_snapshot")
        assert hasattr(PilotRepository, "record_material_change")


# ===========================================================================
# SECTION J - Final Certification Vocabulary (Section 42)
# ===========================================================================

class TestFinalCertificationVocabulary:

    def test_j1_gate_statuses_from_allowed_vocabulary(self):
        """J1: All gate statuses must be from the approved vocabulary."""
        async def run():
            mock_db = AsyncMock()
            repo = PilotRepository(mock_db)
            pilot = _make_pilot("org-j1", "p-j1", days_elapsed=1)

            mock_db.execute = AsyncMock(
                side_effect=[
                    _scalar_one(pilot),
                    _scalar(6),  # compute total < 50, early return
                    _scalar(14), _scalar(6), _scalar(0),
                    _scalar(0),
                    _scalars_all([]), _scalars_all([]),
                    _scalar(0),
                    _scalar(6),  # repro compute total (early return)
                    _scalar(5), _scalar(6),
                    _scalars_all([]),
                    _scalar(0),
                ]
            )

            result = await repo.evaluate_stage1_gates("org-j1")

            VALID = {"PASS","FAIL","INSUFFICIENT_EVIDENCE","BLOCKED","ELIGIBLE","NOT_ELIGIBLE"}
            for gate in result["gates"]:
                assert gate["status"] in VALID, \
                    f"Gate {gate['gate_id']} has invalid status: {gate['status']}"

            assert result["stage_2_approval_status"] in {"BLOCKED","PENDING_HUMAN_REVIEW"}

        asyncio.run(run())

    def test_j2_minimum_stage_days_is_14(self):
        """J2: MINIMUM_STAGE_DAYS for Stage 1 == 14. Must not be weakened."""
        assert MINIMUM_STAGE_DAYS["STAGE_1_SHADOW"] == 14

    def test_j3_minimum_shadow_sample_is_50(self):
        """J3: MINIMUM_SHADOW_SAMPLE == 50. Must not be weakened."""
        assert MINIMUM_SHADOW_SAMPLE == 50

    def test_j4_decision_completeness_filters_synthetic(self):
        """J4: Synthetic observations excluded from completeness calculation."""
        src = inspect.getsource(PilotRepository.get_human_decision_completeness)
        assert "is_synthetic" in src

    def test_j5_reproducibility_filters_synthetic(self):
        """J5: Evidence reproducibility excludes synthetic observations."""
        src = inspect.getsource(PilotRepository.verify_evidence_reproducibility)
        assert "is_synthetic" in src

    def test_j6_compute_shadow_accuracy_filters_synthetic(self):
        """J6: Shadow accuracy computation excludes synthetic observations."""
        src = inspect.getsource(PilotRepository.compute_shadow_accuracy)
        assert "is_synthetic" in src

    def test_j7_stage2_review_never_auto_fires(self):
        """J7: evaluate_stage1_gates must never CALL record_stage2_review.
        A docstring reference is permitted; an actual invocation is not."""
        src = inspect.getsource(PilotRepository.evaluate_stage1_gates)
        # These patterns represent actual call invocations — neither may appear
        assert "await self.record_stage2_review(" not in src, \
            "evaluate_stage1_gates must not await self.record_stage2_review()"
        assert "self.record_stage2_review(" not in src, \
            "evaluate_stage1_gates must not call self.record_stage2_review()"
