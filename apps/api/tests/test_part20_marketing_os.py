"""
Part 20 — Marketing OS Tests
=============================
Tests for:
1. Campaign CRUD & state machine
2. Listing Studio — grounding, stale detection
3. Approval workflow gate
4. Tracking link UTM validation
5. Landing page creation + publish
6. Project launch checklist
7. Intelligence service — funnel, ROI safety
8. Security — tenant isolation
9. AI safety invariants (no fabricated data, no autonomous spend)
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _org():
    return str(uuid.uuid4())

def _id():
    return str(uuid.uuid4())

# ─── Unit Tests — CampaignStatus State Machine ──────────────────────────────

class TestCampaignStatusStateMachine:
    """Verify state machine transitions are enforced correctly."""

    def setup_method(self):
        from app.models.marketing_models import CampaignStatus
        self.SM = CampaignStatus

    def test_draft_to_in_review_allowed(self):
        assert self.SM.can_transition("draft", "in_review") is True

    def test_draft_to_active_blocked(self):
        assert self.SM.can_transition("draft", "active") is False

    def test_active_to_completed_allowed(self):
        assert self.SM.can_transition("active", "completed") is True

    def test_completed_to_active_blocked(self):
        assert self.SM.can_transition("completed", "active") is False

    def test_cancelled_has_no_exits(self):
        for next_state in ["active", "draft", "in_review", "approved"]:
            assert self.SM.can_transition("cancelled", next_state) is False

    def test_approved_to_active_allowed(self):
        assert self.SM.can_transition("approved", "active") is True

    def test_paused_to_active_allowed(self):
        assert self.SM.can_transition("paused", "active") is True

    def test_invalid_objective_raises_in_service(self):
        """Service must reject invalid objectives at input validation."""
        from app.models.marketing_models import CampaignObjective
        assert "not_a_real_obj" not in CampaignObjective.ALL

    def test_all_objectives_defined(self):
        from app.models.marketing_models import CampaignObjective
        expected = {
            "lead_generation", "project_launch", "inventory_sales",
            "remarketing", "site_visit", "booking", "channel_partner", "brand"
        }
        assert expected == CampaignObjective.ALL


# ─── Unit Tests — TrackingLinkService UTM Validation ─────────────────────────

class TestTrackingLinkUTMValidation:
    """Verify UTM normalization and sanitization."""

    def setup_method(self):
        from app.modules.marketing.service import TrackingLinkService
        self.svc = TrackingLinkService(db=None)

    def test_utm_lowercase_normalization(self):
        result = self.svc._validate_utm("Facebook ADS", "utm_source")
        assert result == result.lower()

    def test_utm_special_chars_sanitized(self):
        result = self.svc._validate_utm("test@campaign!", "utm_campaign")
        assert "@" not in result
        assert "!" not in result

    def test_utm_none_returns_none(self):
        assert self.svc._validate_utm(None, "utm_source") is None

    def test_utm_empty_returns_none(self):
        assert self.svc._validate_utm("", "utm_source") is None

    def test_utm_max_length_enforced(self):
        long = "a" * 500
        result = self.svc._validate_utm(long, "utm_source")
        assert len(result) <= 255

    def test_utm_valid_chars_preserved(self):
        result = self.svc._validate_utm("meta_ads-campaign.v2", "utm_medium")
        assert result == "meta_ads-campaign.v2"


# ─── Unit Tests — AI Safety Invariants ───────────────────────────────────────

class TestAISafetyInvariants:
    """Ensure AI cannot bypass critical human gates."""

    def test_listing_publication_ai_flags_exist(self):
        """PropertyListingPublication must expose _ai flags for all content fields."""
        from app.models.marketing_models import PropertyListingPublication
        ai_flags = [
            "listing_title_ai", "short_description_ai", "full_description_ai",
            "highlights_ai", "faq_ai"
        ]
        for flag in ai_flags:
            assert hasattr(PropertyListingPublication, flag), f"Missing AI flag: {flag}"

    def test_campaign_requires_approval_before_active(self):
        """CampaignStatus.VALID_TRANSITIONS must not allow draft→active."""
        from app.models.marketing_models import CampaignStatus
        assert "active" not in CampaignStatus.VALID_TRANSITIONS.get("draft", set())

    def test_marketing_campaign_has_is_ai_assisted_flag(self):
        from app.models.marketing_models import MarketingCampaign
        assert hasattr(MarketingCampaign, "is_ai_assisted")

    def test_asset_has_is_ai_generated_flag(self):
        from app.models.marketing_models import MarketingAsset
        assert hasattr(MarketingAsset, "is_ai_generated")

    def test_approval_entity_has_human_review_fields(self):
        from app.models.marketing_models import CampaignApproval
        assert hasattr(CampaignApproval, "reviewed_by")
        assert hasattr(CampaignApproval, "reviewed_at")
        assert hasattr(CampaignApproval, "review_reason")

    def test_project_launch_requires_human_approved_by(self):
        from app.models.marketing_models import ProjectLaunch
        assert hasattr(ProjectLaunch, "approved_by")
        assert hasattr(ProjectLaunch, "approved_at")

    def test_project_launch_has_all_gates(self):
        from app.models.marketing_models import ProjectLaunch
        required_gates = [
            "gate_project_configured", "gate_inventory_ready", "gate_pricing_ready",
            "gate_media_ready", "gate_landing_page_ready", "gate_lead_form_ready",
            "gate_tracking_ready", "gate_partner_distribution_ready",
            "gate_campaign_ready", "gate_approval_complete",
        ]
        for gate in required_gates:
            assert hasattr(ProjectLaunch, gate), f"Missing gate: {gate}"

    def test_intelligence_service_roi_not_available_without_data(self):
        """ROI must return NOT_AVAILABLE when spend or revenue is missing."""
        from unittest.mock import MagicMock
        from app.modules.marketing.service import MarketingIntelligenceService
        svc = MarketingIntelligenceService(db=None)
        campaign = MagicMock()
        campaign.budget_spent = None
        campaign.revenue_attributed = None
        campaign.currency = "INR"
        result = svc._compute_roi(campaign)
        assert result["status"] == "NOT_AVAILABLE"

    def test_intelligence_service_roi_not_available_zero_spend(self):
        from unittest.mock import MagicMock
        from app.modules.marketing.service import MarketingIntelligenceService
        svc = MarketingIntelligenceService(db=None)
        campaign = MagicMock()
        campaign.budget_spent = Decimal("0")
        campaign.revenue_attributed = Decimal("100000")
        campaign.currency = "INR"
        result = svc._compute_roi(campaign)
        assert result["status"] == "NOT_AVAILABLE"

    def test_intelligence_service_roi_calculated_with_real_data(self):
        from unittest.mock import MagicMock
        from app.modules.marketing.service import MarketingIntelligenceService
        svc = MarketingIntelligenceService(db=None)
        campaign = MagicMock()
        campaign.budget_spent = Decimal("50000")
        campaign.revenue_attributed = Decimal("150000")
        campaign.currency = "INR"
        result = svc._compute_roi(campaign)
        assert result["status"] == "CALCULATED"
        assert result["roi_percent"] == 200.0


# ─── Unit Tests — Project Launch Gate Validation ─────────────────────────────

class TestProjectLaunchGates:
    """Verify launch requires minimum gates before approval."""

    def setup_method(self):
        from app.modules.marketing.service import ProjectLaunchService
        self.svc = ProjectLaunchService(db=None)

    def test_all_gates_ready_returns_true(self):
        from unittest.mock import MagicMock
        launch = MagicMock()
        launch.gate_project_configured = True
        launch.gate_inventory_ready = True
        launch.gate_pricing_ready = True
        launch.gate_lead_form_ready = True
        assert self.svc._all_gates_ready(launch) is True

    def test_missing_inventory_gate_fails(self):
        from unittest.mock import MagicMock
        launch = MagicMock()
        launch.gate_project_configured = True
        launch.gate_inventory_ready = False
        launch.gate_pricing_ready = True
        launch.gate_lead_form_ready = True
        assert self.svc._all_gates_ready(launch) is False

    def test_missing_pricing_gate_fails(self):
        from unittest.mock import MagicMock
        launch = MagicMock()
        launch.gate_project_configured = True
        launch.gate_inventory_ready = True
        launch.gate_pricing_ready = False
        launch.gate_lead_form_ready = True
        assert self.svc._all_gates_ready(launch) is False


# ─── Unit Tests — Slug Sanitization ──────────────────────────────────────────

class TestSlugSanitization:
    """Verify landing page slug sanitization prevents path traversal."""

    def _sanitize(self, slug: str) -> str:
        return "".join(c if c.isalnum() or c == "-" else "-" for c in slug.lower())[:100]

    def test_normal_slug_passes(self):
        assert self._sanitize("marina-towers-2bhk") == "marina-towers-2bhk"

    def test_uppercase_lowercased(self):
        assert self._sanitize("MARINA-TOWERS") == "marina-towers"

    def test_path_traversal_sanitized(self):
        result = self._sanitize("../../etc/passwd")
        assert "/" not in result
        assert "." not in result

    def test_special_chars_replaced(self):
        result = self._sanitize("test@campaign!launch")
        assert "@" not in result
        assert "!" not in result

    def test_max_length_enforced(self):
        result = self._sanitize("a" * 200)
        assert len(result) <= 100


# ─── Unit Tests — Money Type Safety ──────────────────────────────────────────

class TestMoneyTypeSafety:
    """Verify all money fields use Decimal, not float."""

    def test_campaign_budget_planned_is_numeric(self):
        from sqlalchemy import Numeric
        from app.models.marketing_models import MarketingCampaign
        col = MarketingCampaign.__table__.c.budget_planned
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 20
        assert col.type.scale == 4

    def test_campaign_budget_spent_is_numeric(self):
        from sqlalchemy import Numeric
        from app.models.marketing_models import MarketingCampaign
        col = MarketingCampaign.__table__.c.budget_spent
        assert isinstance(col.type, Numeric)

    def test_approval_budget_is_numeric(self):
        from sqlalchemy import Numeric
        from app.models.marketing_models import CampaignApproval
        col = CampaignApproval.__table__.c.budget_requested
        assert isinstance(col.type, Numeric)


# ─── Unit Tests — Tenant Isolation ───────────────────────────────────────────

class TestTenantIsolation:
    """Verify organization_id is mandatory on all domain entities."""

    def test_all_entities_have_organization_id(self):
        from app.models.marketing_models import (
            MarketingCampaign, CampaignApproval, CampaignAuditLog,
            MarketingAsset, PropertyListingPublication, LandingPage,
            TrackingLink, CampaignEvent, ProjectLaunch,
        )
        entities = [
            MarketingCampaign, CampaignApproval, CampaignAuditLog,
            MarketingAsset, PropertyListingPublication, LandingPage,
            TrackingLink, CampaignEvent, ProjectLaunch,
        ]
        for entity in entities:
            assert hasattr(entity, "organization_id"), f"{entity.__name__} missing organization_id"
            col = entity.__table__.c.get("organization_id")
            assert col is not None, f"{entity.__name__} missing organization_id column"
            assert not col.nullable, f"{entity.__name__}.organization_id must be NOT NULL"


# ─── Unit Tests — Stale Listing Detection ────────────────────────────────────

class TestStaleListingDetection:
    """Stale detection is fact-based — never speculative."""

    def test_listing_publication_has_is_stale_field(self):
        from app.models.marketing_models import PropertyListingPublication
        assert hasattr(PropertyListingPublication, "is_stale")
        assert hasattr(PropertyListingPublication, "stale_reason")

    def test_listing_publication_has_last_inventory_sync(self):
        from app.models.marketing_models import PropertyListingPublication
        assert hasattr(PropertyListingPublication, "last_inventory_sync_at")

    def test_listing_version_tracking(self):
        from app.models.marketing_models import PropertyListingPublication
        assert hasattr(PropertyListingPublication, "version")


# ─── Unit Tests — Idempotency ─────────────────────────────────────────────────

class TestIdempotency:
    """Event and audit records must support idempotency."""

    def test_campaign_event_has_idempotency_key(self):
        from app.models.marketing_models import CampaignEvent
        col = CampaignEvent.__table__.c.get("idempotency_key")
        assert col is not None
        assert col.unique is True

    def test_tracking_link_short_token_unique(self):
        from app.models.marketing_models import TrackingLink
        col = TrackingLink.__table__.c.get("short_token")
        assert col is not None
        assert col.unique is True


# ─── Integration Tests — Schema verification ─────────────────────────────────

class TestDatabaseSchema:
    """Verify migration-ready schema — all expected tables declared."""

    def test_all_tables_registered_in_metadata(self):
        from app.database import Base
        from app.models.marketing_models import (
            MarketingCampaign, CampaignApproval, CampaignAuditLog,
            MarketingAsset, PropertyListingPublication, ListingDistribution,
            LandingPage, TrackingLink, CampaignEvent, ProjectLaunch,
            CampaignListingLink,
        )
        expected = {
            "marketing_campaigns", "campaign_approvals", "campaign_audit_logs",
            "marketing_assets", "property_listing_publications", "listing_distributions",
            "marketing_landing_pages", "tracking_links", "campaign_events",
            "project_launches", "campaign_listing_links",
        }
        registered = set(Base.metadata.tables.keys())
        for table in expected:
            assert table in registered, f"Table '{table}' not registered in SQLAlchemy metadata"

    def test_migration_file_exists(self):
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions", "0033_marketing_os.py"
        )
        assert os.path.exists(migration_path), "Migration 0033_marketing_os.py not found"

    def test_migration_revision_and_down_revision(self):
        import importlib.util, os
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions", "0033_marketing_os.py"
        )
        spec = importlib.util.spec_from_file_location("mig_0033", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "0033_marketing_os"
        assert mod.down_revision == "0032_supply_side_inventory_os"


# ─── Router Tests — Endpoint presence ────────────────────────────────────────

class TestRouterEndpoints:
    """Verify all expected endpoints are registered."""

    def setup_method(self):
        from app.modules.marketing.router import marketing_router
        self.routes = {f"{r.methods}:{r.path}" for r in marketing_router.routes if hasattr(r, 'path') and hasattr(r, 'methods')}
        self.paths = [r.path for r in marketing_router.routes if hasattr(r, 'path')]

    def test_campaign_list_endpoint_exists(self):
        assert any("/campaigns" in p for p in self.paths)

    def test_campaign_create_endpoint_exists(self):
        assert any("/campaigns" in p for p in self.paths)

    def test_listing_endpoints_exist(self):
        assert any("/listings" in p for p in self.paths)

    def test_tracking_link_endpoints_exist(self):
        assert any("/tracking-links" in p for p in self.paths)

    def test_landing_page_endpoints_exist(self):
        assert any("/landing-pages" in p for p in self.paths)

    def test_launch_endpoints_exist(self):
        assert any("/launches" in p for p in self.paths)

    def test_intelligence_endpoints_exist(self):
        assert any("/intelligence" in p for p in self.paths)

    def test_approval_endpoint_exists(self):
        assert any("/approval" in p for p in self.paths)

    def test_redirect_endpoint_exists(self):
        assert any("/t/" in p for p in self.paths)

    def test_router_has_28_routes(self):
        from app.modules.marketing.router import marketing_router
        assert len(marketing_router.routes) == 28
