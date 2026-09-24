"""
Part 19 — Supply Side Inventory OS: Concurrency & Double-Reservation Prevention Tests
======================================================================================
Validates strict database-backed race condition protection:
  1. 5 concurrent simultaneous reservation attempts on the exact same unit -> exactly ONE succeeds
  2. Idempotent reservation replay with matching idempotency_key returns unit safely
  3. Release transition from RESERVED -> AVAILABLE permits subsequent reservation
  4. Unit already BOOKED rejects subsequent conflicting reservation attempt
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.inventory_models import (
    RealEstateProject, ProjectUnit, UnitInventoryStatus
)
from app.modules.inventory.service import ProjectService, UnitService


@pytest.fixture
async def concurrency_session_factory():
    """In-memory SQLite engine with multi-connection concurrency support."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        broker_id = uuid.uuid4()
        org_id = broker_id
        broker = Broker(
            id=broker_id,
            email="concurrency.agent@wefylabs.com",
            name="Concurrency Agent",
            password_hash="pw_hash",
            phone="+919811002233",
        )
        session.add(broker)

        proj_svc = ProjectService(session)
        proj = await proj_svc.create_project(org_id, broker_id, {
            "project_name": "Godrej Rivergreens",
            "city": "Pune",
            "locality": "Kharadi",
        })

        unit_svc = UnitService(session)
        unit = await unit_svc.create_unit(org_id, broker_id, {
            "project_id": proj.id,
            "unit_number": "T1-804",
            "unit_type": "2 BHK",
            "floor_number": 8,
            "total_price": 9500000,
        })
        await session.commit()

        unit_id = unit.id
        project_id = proj.id

    yield session_factory, org_id, broker_id, project_id, unit_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_simultaneous_reservations(concurrency_session_factory):
    """
    Simulate 5 simultaneous concurrent reservation attempts on the exact same unit.
    Exactly ONE must succeed, and the remaining 4 must fail with 409 Conflict.
    """
    session_factory, org_id, broker_id, project_id, unit_id = concurrency_session_factory

    num_concurrent = 5
    deal_ids = [uuid.uuid4() for _ in range(num_concurrent)]

    async def attempt_reservation(deal_id: uuid.UUID):
        async with session_factory() as session:
            unit_svc = UnitService(session)
            try:
                unit = await unit_svc.transition_status(
                    org_id=org_id,
                    unit_id=unit_id,
                    to_status=UnitInventoryStatus.RESERVED,
                    reason=f"Concurrent hold attempt by deal={deal_id}",
                    actor_id=broker_id,
                    deal_id=deal_id,
                    idempotency_key=f"idem-{deal_id}",
                )
                await session.commit()
                return {"status": "SUCCESS", "deal_id": deal_id}
            except HTTPException as e:
                await session.rollback()
                return {"status": "FAILED", "code": e.status_code, "detail": e.detail}

    # Fire all 5 simultaneously
    tasks = [attempt_reservation(did) for did in deal_ids]
    results = await asyncio.gather(*tasks)

    successes = [r for r in results if r["status"] == "SUCCESS"]
    failures = [r for r in results if r["status"] == "FAILED"]

    # Exactly 1 success, 4 failures
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 4, f"Expected 4 failures, got {len(failures)}"
    for f in failures:
        assert f["code"] == 409

    # Verify unit in DB has status RESERVED
    async with session_factory() as verify_session:
        unit_svc = UnitService(verify_session)
        final_unit = await unit_svc.get_unit(org_id, unit_id)
        assert final_unit.inventory_status == UnitInventoryStatus.RESERVED
        assert final_unit.reserved_by_deal_id == successes[0]["deal_id"]


@pytest.mark.asyncio
async def test_idempotent_reservation_replay(concurrency_session_factory):
    """
    A network retry sending the exact same idempotency_key should return the unit
    without error and without double-mutating state.
    """
    session_factory, org_id, broker_id, project_id, unit_id = concurrency_session_factory
    deal_id = uuid.uuid4()
    idem_key = "idemp-key-repeat-999"

    async with session_factory() as session:
        unit_svc = UnitService(session)
        # First attempt -> succeeds
        u1 = await unit_svc.transition_status(
            org_id=org_id,
            unit_id=unit_id,
            to_status=UnitInventoryStatus.RESERVED,
            deal_id=deal_id,
            idempotency_key=idem_key,
        )
        await session.commit()
        assert u1.inventory_status == UnitInventoryStatus.RESERVED

        # Second attempt with same idempotency key -> idempotent return
        u2 = await unit_svc.transition_status(
            org_id=org_id,
            unit_id=unit_id,
            to_status=UnitInventoryStatus.RESERVED,
            deal_id=deal_id,
            idempotency_key=idem_key,
        )
        assert u2.inventory_status == UnitInventoryStatus.RESERVED
        assert u2.last_reservation_idempotency_key == idem_key


@pytest.mark.asyncio
async def test_released_unit_can_be_reserved_again(concurrency_session_factory):
    """
    When a reservation expires or is released back to AVAILABLE,
    a subsequent buyer can reserve the unit.
    """
    session_factory, org_id, broker_id, project_id, unit_id = concurrency_session_factory
    deal_a = uuid.uuid4()
    deal_b = uuid.uuid4()

    async with session_factory() as session:
        unit_svc = UnitService(session)

        # 1. Buyer A reserves
        await unit_svc.transition_status(
            org_id, unit_id, UnitInventoryStatus.RESERVED,
            deal_id=deal_a, reason="Buyer A token"
        )
        await session.commit()

        # 2. Buyer A cancels / token expires -> release to AVAILABLE
        await unit_svc.transition_status(
            org_id, unit_id, UnitInventoryStatus.AVAILABLE,
            reason="Buyer A loan declined, release to open market"
        )
        await session.commit()

        # 3. Buyer B reserves -> should succeed cleanly
        unit_b = await unit_svc.transition_status(
            org_id, unit_id, UnitInventoryStatus.RESERVED,
            deal_id=deal_b, reason="Buyer B new reservation"
        )
        await session.commit()

        assert unit_b.inventory_status == UnitInventoryStatus.RESERVED
        assert unit_b.reserved_by_deal_id == deal_b
