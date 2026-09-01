"""
BeetleLabs Unit of Work
========================
Atomic transaction boundary across all repositories.
Every multi-step operation that must succeed or fail together uses this.

Architecture:
- UnitOfWork wraps a single AsyncSession
- All repositories share the same session (same transaction)
- On clean exit → commit
- On any exception → rollback
- Domain events published AFTER commit (never inside transaction)

Usage:
    async with get_unit_of_work(organization_id=org_id) as uow:
        lead = await uow.leads.create(entity, created_by=user_id)
        await uow.activities.create(activity_entity)
        # auto-commits on exit
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.common.logger.logging_config import get_logger

# Import all module repositories (add new repositories here as modules are built)
from app.infrastructure.persistence.sqlalchemy_lead_repository import SQLAlchemyLeadRepository

logger = get_logger(__name__)


class UnitOfWork:
    """
    Async Unit of Work pattern guaranteeing transaction atomicity across all modules.

    Contains one repository per domain module, all sharing the same session.
    Add a new property for every new module repository.
    """

    def __init__(self, session: AsyncSession, organization_id: str):
        """
        Args:
            session: The shared database session for this transaction
            organization_id: Tenant context — propagated to all repositories
        """
        self.session = session
        self._org_id = organization_id

        # ─── Module Repositories ──────────────────────────────────────────────
        # Each repository receives the shared session and organization_id.
        # This ensures all writes in a single UoW are in one transaction.
        self.leads = SQLAlchemyLeadRepository(session, organization_id)

        # TODO (Phase 2 — add as modules are built):
        # self.contacts = SQLAlchemyContactRepository(session, organization_id)
        # self.tasks = SQLAlchemyTaskRepository(session, organization_id)
        # self.meetings = SQLAlchemyMeetingRepository(session, organization_id)
        # self.activities = SQLAlchemyActivityRepository(session, organization_id)
        # self.notifications = SQLAlchemyNotificationRepository(session, organization_id)
        # self.conversations = SQLAlchemyConversationRepository(session, organization_id)
        # self.pipelines = SQLAlchemyPipelineRepository(session, organization_id)
        # self.properties = SQLAlchemyPropertyRepository(session, organization_id)

    async def commit(self) -> None:
        """Commits the current transaction. Called automatically by context manager."""
        await self.session.commit()
        logger.debug("Transaction committed", extra={"org_id": self._org_id})

    async def rollback(self) -> None:
        """Rolls back the current transaction on error."""
        await self.session.rollback()
        logger.warning("Transaction rolled back", extra={"org_id": self._org_id})

    async def flush(self) -> None:
        """Flushes pending changes to the DB without committing (for ID generation)."""
        await self.session.flush()


@asynccontextmanager
async def get_unit_of_work(organization_id: str) -> AsyncGenerator[UnitOfWork, None]:
    """
    Async context manager providing a transactional UnitOfWork.

    Guarantees:
    - Auto-commit on clean exit
    - Auto-rollback on any exception
    - Session always closed on exit (prevents connection leaks)

    Args:
        organization_id: Required tenant context. Never pass None.

    Example:
        async with get_unit_of_work(organization_id=str(current_org.id)) as uow:
            lead = await uow.leads.create(lead_entity, created_by=str(user.id))
            await uow.activities.create(activity_entity)
            # commits automatically on exit
    """
    if not organization_id:
        raise ValueError("organization_id is required to create a UnitOfWork. Tenant isolation cannot be bypassed.")

    async with AsyncSessionLocal() as session:
        uow = UnitOfWork(session=session, organization_id=organization_id)
        try:
            yield uow
            await uow.commit()
        except Exception as exc:
            await uow.rollback()
            logger.error(
                f"Transaction rolled back due to: {exc.__class__.__name__}: {exc}",
                extra={"org_id": organization_id}
            )
            raise
        finally:
            await session.close()
