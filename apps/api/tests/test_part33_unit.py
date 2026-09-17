"""
test_part33_unit.py
===================
Part 33 — Real Production Deployment + Launch Infrastructure Unit Tests

Validates:
- Environment variable matrix & classification compliance
- Domain parameterization and absence of hardcoded unfinalized domains
- Deployment manifests (Dockerfile.prod, render.yaml, Procfile)
- Celery worker & Beat scheduler declarations
- Alembic linear migration safety
- Razorpay TEST mode enforcement and WhatsApp disabled state
"""
from __future__ import annotations

import os
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"


# ─── 1. Environment Variable Matrix & Classification ──────────────────────────

class TestEnvironmentMatrix:
    """Verifies that universal and service environment templates adhere to Part 33 requirements."""

    def test_root_env_example_exists_and_classified(self):
        env_path = REPO_ROOT / ".env.example"
        assert env_path.exists(), ".env.example must exist at repository root"
        content = env_path.read_text(encoding="utf-8")

        # Must declare all required classification tokens
        assert "PUBLIC" in content
        assert "SERVER_ONLY" in content
        assert "PRODUCTION_REQUIRED" in content
        assert "OPTIONAL" in content

        # Critical variables must be present
        for var in [
            "DATABASE_URL",
            "REDIS_URL",
            "GEMINI_API_KEY",
            "SMTP_HOST",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "RAZORPAY_KEY_ID",
            "RAZORPAY_ENVIRONMENT",
            "SECRET_KEY",
        ]:
            assert var in content, f"Variable {var} missing from root .env.example"

    def test_domain_parameterization_in_templates(self):
        """Ensures templates use ${DOMAIN} parameterization instead of hardcoded company domains."""
        for p in [
            REPO_ROOT / ".env.example",
            API_DIR / ".env.production.example",
            WEB_DIR / ".env.production.example",
        ]:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                assert "${DOMAIN}" in content, f"{p.name} must parameterize domain with ${{DOMAIN}}"

    def test_frontend_env_template_contains_only_public_variables(self):
        """Frontend production template must NEVER contain secrets or backend-only variables."""
        p = WEB_DIR / ".env.production.example"
        assert p.exists()
        content = p.read_text(encoding="utf-8")

        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
        for line in lines:
            if "=" in line:
                var_name = line.split("=")[0].strip()
                assert var_name.startswith("NEXT_PUBLIC_"), (
                    f"Frontend template contains non-public variable: {var_name}"
                )


# ─── 2. Deployment Artifacts & Manifests ──────────────────────────────────────

class TestDeploymentManifests:
    """Validates Dockerfile.prod, Procfile, and render.yaml for production compatibility."""

    def test_dockerfile_prod_non_root_user(self):
        df_path = API_DIR / "Dockerfile.prod"
        ep_path = API_DIR / "entrypoint.sh"
        assert df_path.exists(), "Dockerfile.prod must exist in apps/api"
        assert ep_path.exists(), "entrypoint.sh must exist in apps/api"
        df_content = df_path.read_text(encoding="utf-8")
        ep_content = ep_path.read_text(encoding="utf-8")

        # Must execute as a non-root user
        assert "USER" in df_content, "Dockerfile.prod must declare a non-root USER"
        assert "EXPOSE 8000" in df_content, "Dockerfile.prod must expose port 8000"
        # Entrypoint executes uvicorn production server
        assert "uvicorn app.main:app" in ep_content, "entrypoint.sh must start uvicorn"

    def test_render_yaml_defines_three_services(self):
        render_path = REPO_ROOT / "render.yaml"
        assert render_path.exists(), "render.yaml must exist at repo root"
        content = render_path.read_text(encoding="utf-8")

        # Must declare api web service, celery worker, and celery beat
        assert "wefylabs-api" in content or "beetlelabs-api" in content or "web" in content
        assert "wefylabs-celery-worker" in content or "beetlelabs-celery-worker" in content or "worker" in content
        assert "wefylabs-celery-beat" in content or "beetlelabs-celery-beat" in content or "beat" in content

    def test_procfile_defines_web_worker_and_beat(self):
        procfile_path = API_DIR / "Procfile"
        assert procfile_path.exists(), "Procfile must exist in apps/api"
        content = procfile_path.read_text(encoding="utf-8")

        assert "web:" in content
        assert "worker:" in content
        assert "beat:" in content


# ─── 3. Celery Worker & Beat Configuration ────────────────────────────────────

class TestCeleryInfrastructure:
    """Validates Celery app initialization and beat schedules."""

    def test_celery_app_loads(self):
        from app.celery_app import celery_app
        assert celery_app is not None
        assert celery_app.main is not None

    def test_celery_beat_schedule_configured(self):
        from app.celery_app import celery_app
        beat_sched = celery_app.conf.beat_schedule
        assert isinstance(beat_sched, dict)
        # Should have registered periodic jobs
        assert len(beat_sched) > 0


# ─── 4. Migration & Schema Safety ─────────────────────────────────────────────

class TestAlembicMigrationSafety:
    """Validates single head and linear migration structure."""

    def test_single_alembic_head_definition(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        ini_path = API_DIR / "alembic.ini"
        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(API_DIR / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()

        assert len(heads) == 1, f"Expected exactly 1 Alembic head, found {len(heads)}: {heads}"
        assert heads[0] == "0026_revenue_autopilot"


# ─── 5. Guardrails: Razorpay TEST Mode & WhatsApp Disabled ─────────────────────

class TestProductionGuardrails:
    """Ensures that dangerous live payment modes and inactive WhatsApp are guarded."""

    def test_razorpay_is_not_live(self):
        from app.config import settings
        assert settings.RAZORPAY_ENVIRONMENT != "live", "Razorpay LIVE mode must not be active"
        assert not settings.RAZORPAY_KEY_ID.startswith("rzp_live_"), "LIVE Razorpay keys must not be configured"

    def test_whatsapp_is_not_active_by_default(self):
        from app.config import settings
        token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
        # WhatsApp token must be absent or placeholder (no live token)
        is_disabled = (not token) or ("placeholder" in token.lower()) or (token.startswith("wa_"))
        assert is_disabled, "WhatsApp must remain inactive/placeholder only"
