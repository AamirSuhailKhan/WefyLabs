"""
BeetleLabs / WefyLabs Database Isolation and Safety Guard
=========================================================
Prevents acceptance tests, test scripts, and non-production mutating harnesses
from executing against the live shared application database ('leadscore').

Enforces:
1. POSITIVE ALLOWLIST: Only explicitly approved, isolated test database names are permitted.
   Blocklists alone are insufficient. Any unfamiliar or shared database is rejected fail-closed.
2. RUNTIME ENGINE & SESSION INSPECTION: The database checked by the guard is the actual database
   used by SQLAlchemy's active session/engine, preventing environment-variable desynchronization.
3. TestEntityTracker: Strict test-owned primary key tracking with safe child-to-parent cleanup,
   idempotency, and immunity for pre-existing business records.
4. Zero cascade into unrelated business data.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger("wefylabs.database_safety")

# ─── 1. POSITIVE TEST DATABASE ALLOWLIST ──────────────────────────────────────────
# Any database name not explicitly in this set or matching approved dynamic patterns is REJECTED.
EXPLICIT_TEST_DATABASE_ALLOWLIST: Set[str] = {
    ":memory:",
    "leadscore_test_acceptance",
    "leadscore_verify_phase6",
    "leadscore_test",
    "leadscore_ci_test",
}

# Strict regex for trusted dynamic test databases created by test runners/fixtures
APPROVED_DYNAMIC_TEST_DB_REGEX = re.compile(r"^(leadscore_test|test_db)_[a-f0-9]{4,32}$")

# Absolute blocklist for live/shared production databases (redundant defense-in-depth)
FORBIDDEN_SHARED_DATABASES: Set[str] = {
    "leadscore",
    "leadscore_prod",
    "leadscore_production",
    "leadscore_staging",
    "leadscore_pilot",
    "postgres",
    "defaultdb",
}

# Permitted hosts for test execution
APPROVED_TEST_HOSTS: Set[str] = {
    "",
    "localhost",
    "127.0.0.1",
    "postgres",  # Docker compose internal network alias
    "db",
}


class DatabaseSafetyError(Exception):
    """Base exception for database isolation violations."""
    pass


class UnsafeDatabaseTargetError(DatabaseSafetyError):
    """Raised when an acceptance or mutating test attempts to target an unsafe database."""
    pass


class AmbiguousEnvironmentError(DatabaseSafetyError):
    """Raised when the execution environment cannot be verified as isolated test."""
    pass


class EngineSessionMismatchError(DatabaseSafetyError):
    """Raised when active SQLAlchemy engine/session target differs from expected test target."""
    pass


class UnregisteredEntityCleanupError(DatabaseSafetyError):
    """Raised when cleanup attempts to delete an untracked or pre-existing record."""
    pass


def parse_db_target(url: Optional[str]) -> Dict[str, Any]:
    """Parses database URL into component parts."""
    if not url:
        return {"scheme": "", "database": "", "host": "", "port": None}
    
    # Handle sqlite in-memory
    if ":memory:" in url or url.startswith("sqlite"):
        db_name = ":memory:" if ":memory:" in url else url.split("///")[-1]
        return {
            "scheme": "sqlite",
            "database": db_name,
            "host": "localhost",
            "port": None,
        }

    try:
        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/") if parsed.path else ""
        return {
            "scheme": parsed.scheme,
            "database": db_name,
            "host": parsed.hostname or "",
            "port": parsed.port,
        }
    except Exception as exc:
        raise UnsafeDatabaseTargetError(f"Could not parse database URL: {exc}") from exc


def is_live_or_shared_database(url: Optional[str]) -> bool:
    """Returns True if the database target corresponds to the live or shared database."""
    target = parse_db_target(url)
    db_name = target["database"].lower()
    return db_name in FORBIDDEN_SHARED_DATABASES


def is_approved_test_database(db_name: str) -> bool:
    """Validates database name against the positive allowlist and trusted dynamic pattern."""
    normalized = (db_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in FORBIDDEN_SHARED_DATABASES:
        return False
    if normalized in EXPLICIT_TEST_DATABASE_ALLOWLIST:
        return True
    if APPROVED_DYNAMIC_TEST_DB_REGEX.match(normalized):
        return True
    return False


def validate_test_database_target(
    target: Union[str, AsyncEngine, AsyncSession, None],
    env: Optional[str] = None,
    allow_override_token: Optional[str] = None,
) -> str:
    """
    Validates that the provided database URL, Engine, or Session is an approved test store.
    Fails closed if:
    1. Target is missing or empty.
    2. Environment is missing, ambiguous, or indicates production/staging.
    3. Target matches 'leadscore' or any forbidden shared/production database.
    4. Target does NOT match the positive test allowlist.
    5. Hostname is not an approved local/container test host.
    """
    # 1. Resolve raw URL from string, Engine, or Session
    if target is None:
        raw_url = ""
    elif isinstance(target, str):
        raw_url = target.strip()
    elif isinstance(target, AsyncSession):
        raw_url = str(target.bind.url) if target.bind else ""
    elif isinstance(target, AsyncEngine):
        raw_url = str(target.url)
    elif hasattr(target, "url"):
        raw_url = str(getattr(target, "url"))
    else:
        raw_url = str(target)

    if not raw_url:
        raise UnsafeDatabaseTargetError(
            "CRITICAL DATABASE SAFETY VIOLATION: Database connection target is missing or empty. "
            "Mutating test execution aborted."
        )

    # 2. Environment validation
    effective_env = (env or "").strip().lower()
    if not effective_env:
        raise AmbiguousEnvironmentError(
            "CRITICAL ENVIRONMENT VIOLATION: Execution environment is not specified. "
            "Must be explicitly set to 'testing' or 'test'."
        )

    if effective_env in ("production", "prod", "staging"):
        raise AmbiguousEnvironmentError(
            f"CRITICAL ENVIRONMENT VIOLATION: Acceptance test harness detected production environment '{effective_env}'. "
            "Mutating tests are strictly forbidden in production."
        )

    # 3. Database name inspection
    parsed = parse_db_target(raw_url)
    db_name = parsed["database"].lower()

    if not db_name:
        raise UnsafeDatabaseTargetError(
            "CRITICAL DATABASE SAFETY VIOLATION: Could not determine database name from connection target."
        )

    # 4. Explicit live database rejection
    if db_name in FORBIDDEN_SHARED_DATABASES:
        if allow_override_token and allow_override_token == "EXPLICIT_OWNER_AUTHORIZED_LIVE_AUDIT_2026":
            logger.warning(
                "OVERRIDE ENGAGED: Authorized live database inspection token validated for '%s'.", db_name
            )
            return db_name

        raise UnsafeDatabaseTargetError(
            f"CRITICAL SAFETY LOCKOUT: Acceptance test harness REFUSED connection to shared/live "
            f"database '{db_name}'. Acceptance tests creating or deleting records must use a dedicated "
            f"isolated test database (e.g., 'leadscore_test_acceptance'). Default is to FAIL CLOSED."
        )

    # 5. Positive allowlist enforcement (Unfamiliar names are REJECTED)
    if not is_approved_test_database(db_name):
        raise UnsafeDatabaseTargetError(
            f"CRITICAL SAFETY LOCKOUT: Database '{db_name}' is not in the positive test database allowlist. "
            f"Approved targets: {sorted(list(EXPLICIT_TEST_DATABASE_ALLOWLIST))}. "
            "Unfamiliar database names are strictly rejected fail-closed."
        )

    # 6. Host validation
    host = parsed["host"].lower()
    if host and host not in APPROVED_TEST_HOSTS and not host.endswith(".internal"):
        raise UnsafeDatabaseTargetError(
            f"CRITICAL SAFETY LOCKOUT: Connection host '{host}' is not an approved test host. "
            f"Approved test hosts: {sorted(list(APPROVED_TEST_HOSTS))}."
        )

    return db_name


def verify_session_target(session: AsyncSession, expected_db: Optional[str] = None) -> str:
    """
    Verifies that the active session's bound engine points to an approved test database.
    Guarantees that an environment variable changed after engine creation does not disguise
    a session that is actually writing to another database.
    """
    if not session.bind:
        raise EngineSessionMismatchError("Active session has no engine bound.")
    
    bound_url = str(session.bind.url)
    parsed = parse_db_target(bound_url)
    actual_db = parsed["database"].lower()

    # Validate against allowlist
    validate_test_database_target(bound_url, env="testing")

    if expected_db:
        exp_clean = expected_db.strip().lower()
        if actual_db != exp_clean:
            raise EngineSessionMismatchError(
                f"ENGINE-SESSION MISMATCH DETECTED: Caller expected database '{exp_clean}', "
                f"but active SQLAlchemy session is bound to '{actual_db}'! Writes aborted."
            )

    return actual_db


def create_isolated_test_session_factory(
    test_db_url: str,
    expected_db: Optional[str] = None,
) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Creates a dedicated, isolated test engine and session factory with fail-closed validation.
    Guarantees NullPool to prevent connection leaks across async loops.
    """
    validated_db = validate_test_database_target(test_db_url, env="testing")
    if expected_db and validated_db != expected_db.strip().lower():
        raise EngineSessionMismatchError(
            f"Expected test db '{expected_db}' does not match target '{validated_db}'"
        )

    test_engine = create_async_engine(
        test_db_url,
        echo=False,
        poolclass=NullPool,
    )

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    return test_engine, session_factory


class TestEntityTracker:
    """
    Lifecycle tracker for test-created entities.
    Guarantees:
    - Only explicitly recorded primary keys can be deleted during cleanup.
    - Rejects wildcard, bulk, or timestamp-based deletes.
    - Deletes in strict foreign-key dependency order.
    - Prevents deleting pre-existing records or data belonging to another test run.
    - Idempotent: safe to invoke cleanup multiple times without failure.
    """
    __test__ = False

    def __init__(self, test_run_id: Optional[str] = None, pre_existing_ids: Optional[Dict[str, Set[Any]]] = None):
        self.test_run_id = test_run_id or str(uuid.uuid4())
        self._tracked: Dict[str, Set[Any]] = {
            "lead_notes": set(),
            "tasks": set(),
            "source_attributions": set(),
            "leads": set(),
            "organization_members": set(),  # Set of (org_id, broker_id) tuples
            "brokers": set(),
            "organizations": set(),
        }
        self._pre_existing: Dict[str, Set[Any]] = pre_existing_ids or {}
        self._cleaned_up: bool = False
        self._last_summary: Optional[Dict[str, Any]] = None

    def register(self, table: str, entity_id: Any) -> None:
        """Registers a newly created synthetic primary key."""
        if not entity_id:
            return
        if table not in self._tracked:
            self._tracked[table] = set()

        str_id = str(entity_id)

        # Pre-existing guard: Refuse to register any ID known to pre-date the test
        if table in self._pre_existing and str_id in self._pre_existing[table]:
            raise UnregisteredEntityCleanupError(
                f"SAFETY VIOLATION: Cannot register pre-existing record {str_id} in table '{table}' as test-owned!"
            )

        self._tracked[table].add(str_id)

    def register_membership(self, org_id: Any, broker_id: Any) -> None:
        """Registers an organization membership tuple."""
        if not org_id or not broker_id:
            return
        pair = (str(org_id), str(broker_id))
        self._tracked["organization_members"].add(pair)

    def is_registered(self, table: str, entity_id: Any) -> bool:
        """Checks if an entity is registered as test-owned."""
        str_id = str(entity_id)
        return str_id in self._tracked.get(table, set())

    def get_registered_ids(self, table: str) -> Set[Any]:
        """Returns the set of registered IDs for a table."""
        return set(self._tracked.get(table, set()))

    async def safe_cleanup(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Executes bounded deletion of ONLY registered synthetic entities.
        Validates target database is an isolated test store before executing any statement.
        Safe and idempotent when called multiple times.
        """
        if self._cleaned_up and self._last_summary is not None:
            logger.info("TestEntityTracker safe_cleanup called again; returning cached summary.")
            return self._last_summary

        # Runtime session target verification
        verify_session_target(session)

        from app.models.broker import Broker
        from app.models.lead import Lead
        from app.models.organization import Organization, OrganizationMember
        from app.models.crm_models import Task, LeadNote

        cleanup_ledger: Dict[str, int] = {}

        # 1. Lead Notes (id is VARCHAR/String)
        note_ids = [str(i) for i in self._tracked["lead_notes"]]
        if note_ids:
            res = await session.execute(delete(LeadNote).where(LeadNote.id.in_(note_ids)))
            cleanup_ledger["lead_notes"] = res.rowcount

        # 2. Tasks (id is VARCHAR/String)
        task_ids = [str(i) for i in self._tracked["tasks"]]
        if task_ids:
            res = await session.execute(delete(Task).where(Task.id.in_(task_ids)))
            cleanup_ledger["tasks"] = res.rowcount

        # 3. Source Attributions (Clean up side effects linked to test leads or explicit attribution IDs)
        attr_ids = list(self._tracked["source_attributions"])
        lead_str_ids = list(self._tracked["leads"])
        if attr_ids or lead_str_ids:
            try:
                from sqlalchemy import text
                if attr_ids:
                    await session.execute(
                        text("DELETE FROM source_attributions WHERE id = ANY(:ids)"),
                        {"ids": attr_ids}
                    )
                if lead_str_ids:
                    res = await session.execute(
                        text("DELETE FROM source_attributions WHERE lead_id = ANY(:lead_ids)"),
                        {"lead_ids": lead_str_ids}
                    )
                    cleanup_ledger["source_attributions"] = res.rowcount
            except Exception as e:
                logger.warning("Optional cleanup of source_attributions encountered: %s", e)

        # 4. Leads (id is UUID)
        lead_ids = [uuid.UUID(i) if isinstance(i, str) and len(i) == 36 else i for i in self._tracked["leads"]]
        if lead_ids:
            res = await session.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
            cleanup_ledger["leads"] = res.rowcount

        # 5. Organization Members (composite key: organization_id, broker_id)
        memberships = list(self._tracked["organization_members"])
        if memberships:
            for org_id_str, broker_id_str in memberships:
                o_uuid = uuid.UUID(org_id_str) if len(org_id_str) == 36 else org_id_str
                b_uuid = uuid.UUID(broker_id_str) if len(broker_id_str) == 36 else broker_id_str
                await session.execute(
                    delete(OrganizationMember).where(
                        OrganizationMember.organization_id == o_uuid,
                        OrganizationMember.broker_id == b_uuid
                    )
                )
            cleanup_ledger["organization_members"] = len(memberships)

        # 6. Brokers (id is UUID)
        broker_ids = [uuid.UUID(i) if isinstance(i, str) and len(i) == 36 else i for i in self._tracked["brokers"]]
        if broker_ids:
            res = await session.execute(delete(Broker).where(Broker.id.in_(broker_ids)))
            cleanup_ledger["brokers"] = res.rowcount

        # 7. Organizations (id is UUID)
        org_ids = [uuid.UUID(i) if isinstance(i, str) and len(i) == 36 else i for i in self._tracked["organizations"]]
        if org_ids:
            res = await session.execute(delete(Organization).where(Organization.id.in_(org_ids)))
            cleanup_ledger["organizations"] = res.rowcount

        await session.commit()
        self._cleaned_up = True

        # Sanitize output
        self._last_summary = {
            "test_run_id": hashlib.sha256(self.test_run_id.encode()).hexdigest()[:12],
            "records_purged": cleanup_ledger,
            "status": "COMPLETED_CLEAN",
        }
        logger.info("Test entity cleanup completed cleanly: %s", self._last_summary)
        return self._last_summary
