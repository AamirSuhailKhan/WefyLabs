"""
Part 19 — Real Estate Supply, Project & Unit Inventory OS: Core Tests
=====================================================================
Tests:
  1. RealEstateDeveloper CRUD, code generation, and updates
  2. RealEstateProject creation, search filtering, and inventory counter recalculation
  3. ProjectUnit creation with high Decimal financial precision
  4. UnitInventoryStatus state machine transitions & forbidden transition rejection
  5. Append-only ProjectUnitStatusLog verification on each mutation
  6. PriceBook creation, version increments, entry addition, and publication lifecycle
  7. InventoryAvailabilitySnapshot materialization and aggregation
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from fastapi import HTTPException

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.inventory_models import (
    RealEstateDeveloper, RealEstateProject, ProjectUnit, ProjectUnitStatusLog,
    ProjectPriceBook, PriceBookEntry, InventoryAvailabilitySnapshot,
    DeveloperStatus, ProjectStatus, UnitInventoryStatus, PriceBookStatus,
)
from app.modules.inventory.service import (
    DeveloperService, ProjectService, UnitService,
    PriceBookService, InventorySnapshotService,
)


@pytest.fixture
async def inventory_session():
    """In-memory SQLite database session with full Base metadata schema."""
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
            email="inventory.lead@wefylabs.com",
            name="Inventory Director",
            password_hash="hashed_pw",
            phone="+919876543210",
        )
        session.add(broker)
        await session.commit()
        yield session, org_id, broker_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_developer_crud(inventory_session):
    session, org_id, broker_id = inventory_session
    dev_svc = DeveloperService(session)

    # 1. Create Developer
    dev_data = {
        "legal_name": "Emaar Properties India Pvt Ltd",
        "trade_name": "Emaar India",
        "rera_number": "RERA-IND-9988",
        "city": "Gurugram",
        "state": "Haryana",
        "country_code": "IN",
        "years_in_business": 25,
    }
    dev = await dev_svc.create_developer(org_id, broker_id, dev_data)
    await session.commit()

    assert dev.id is not None
    assert dev.legal_name == "Emaar Properties India Pvt Ltd"
    assert dev.developer_code.startswith("DEV-")
    assert dev.status == DeveloperStatus.ACTIVE

    # 2. Get Developer
    fetched = await dev_svc.get_developer(org_id, dev.id)
    assert fetched.id == dev.id
    assert fetched.city == "Gurugram"

    # 3. Update Developer
    updated = await dev_svc.update_developer(org_id, dev.id, {"city": "New Delhi", "trade_name": "Emaar NCR"})
    await session.commit()
    assert updated.city == "New Delhi"
    assert updated.trade_name == "Emaar NCR"

    # 4. List Developers
    items, total = await dev_svc.list_developers(org_id)
    assert total >= 1
    assert any(d.id == dev.id for d in items)


@pytest.mark.asyncio
async def test_project_crud_and_counters(inventory_session):
    session, org_id, broker_id = inventory_session
    dev_svc = DeveloperService(session)
    proj_svc = ProjectService(session)
    unit_svc = UnitService(session)

    dev = await dev_svc.create_developer(org_id, broker_id, {"legal_name": "DLF Limited"})
    await session.commit()

    # 1. Create Project
    proj_data = {
        "developer_id": dev.id,
        "project_name": "DLF The Camellias",
        "project_type": "residential",
        "city": "Gurugram",
        "locality": "Golf Course Road",
        "rera_number": "HRERA-101-2017",
        "price_min": 150000000,
        "price_max": 450000000,
    }
    proj = await proj_svc.create_project(org_id, broker_id, proj_data)
    await session.commit()

    assert proj.id is not None
    assert proj.project_name == "DLF The Camellias"
    assert proj.project_code.startswith("PRJ-")
    assert proj.status == ProjectStatus.ANNOUNCED

    # 2. Add units and test inventory counters
    u1 = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id,
        "unit_number": "T1-1001",
        "unit_type": "4 BHK",
        "floor_number": 10,
        "carpet_area": 4500,
        "total_price": 200000000,
    })
    u2 = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id,
        "unit_number": "T1-1002",
        "unit_type": "4 BHK",
        "floor_number": 10,
        "carpet_area": 4500,
        "total_price": 205000000,
    })
    await session.commit()

    # Transition u1 to RESERVED
    await unit_svc.transition_status(org_id, u1.id, UnitInventoryStatus.RESERVED, reason="Token hold")
    await session.commit()

    # Recompute counters
    await proj_svc.update_project_inventory_counters(proj.id)
    await session.commit()

    proj_refreshed = await proj_svc.get_project(org_id, proj.id)
    assert proj_refreshed.total_units == 2
    assert proj_refreshed.available_units == 1
    assert proj_refreshed.reserved_units == 1


@pytest.mark.asyncio
async def test_unit_state_machine_and_audit_log(inventory_session):
    session, org_id, broker_id = inventory_session
    proj_svc = ProjectService(session)
    unit_svc = UnitService(session)

    proj = await proj_svc.create_project(org_id, broker_id, {
        "project_name": "Lodha World One",
        "city": "Mumbai",
        "locality": "Lower Parel",
    })
    await session.commit()

    unit = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id,
        "unit_number": "WO-4501",
        "unit_type": "3 BHK",
        "floor_number": 45,
        "carpet_area": 1850,
        "base_price": 45000000,
        "total_price": 48500000,
    })
    await session.commit()

    assert unit.inventory_status == UnitInventoryStatus.AVAILABLE

    # Initial log exists
    logs_res = (await session.execute(
        select(ProjectUnitStatusLog).where(ProjectUnitStatusLog.unit_id == unit.id)
    )).scalars().all()
    assert len(logs_res) == 1
    assert logs_res[0].new_status == UnitInventoryStatus.AVAILABLE

    # Valid Transition 1: AVAILABLE -> RESERVED
    deal_id = uuid.uuid4()
    unit = await unit_svc.transition_status(
        org_id, unit.id, UnitInventoryStatus.RESERVED,
        reason="Client token placed",
        deal_id=deal_id,
        idempotency_key="tok-1234",
    )
    await session.commit()
    assert unit.inventory_status == UnitInventoryStatus.RESERVED
    assert unit.reserved_by_deal_id == deal_id
    assert unit.reservation_expires_at is not None

    # Valid Transition 2: RESERVED -> BOOKED
    unit = await unit_svc.transition_status(
        org_id, unit.id, UnitInventoryStatus.BOOKED,
        reason="10% booking agreement executed",
        deal_id=deal_id,
    )
    await session.commit()
    assert unit.inventory_status == UnitInventoryStatus.BOOKED
    assert unit.booked_by_deal_id == deal_id

    # Valid Transition 3: BOOKED -> SOLD
    unit = await unit_svc.transition_status(
        org_id, unit.id, UnitInventoryStatus.SOLD,
        reason="Sale deed registered",
        deal_id=deal_id,
    )
    await session.commit()
    assert unit.inventory_status == UnitInventoryStatus.SOLD
    assert unit.sold_at is not None

    # Forbidden Transition: SOLD -> AVAILABLE (SOLD is terminal in valid transitions)
    with pytest.raises(HTTPException) as exc_info:
        await unit_svc.transition_status(
            org_id, unit.id, UnitInventoryStatus.AVAILABLE,
            reason="Illegal reactivation attempt",
        )
    assert exc_info.value.status_code == 409

    # Verify all audit logs recorded in order
    logs = (await session.execute(
        select(ProjectUnitStatusLog)
        .where(ProjectUnitStatusLog.unit_id == unit.id)
        .order_by(ProjectUnitStatusLog.created_at.asc())
    )).scalars().all()
    assert len(logs) == 4
    statuses = [l.new_status for l in logs]
    assert statuses == [
        UnitInventoryStatus.AVAILABLE,
        UnitInventoryStatus.RESERVED,
        UnitInventoryStatus.BOOKED,
        UnitInventoryStatus.SOLD,
    ]


@pytest.mark.asyncio
async def test_price_book_versioning_and_publishing(inventory_session):
    session, org_id, broker_id = inventory_session
    proj_svc = ProjectService(session)
    pb_svc = PriceBookService(session)

    proj = await proj_svc.create_project(org_id, broker_id, {
        "project_name": "Godrej Woods",
        "city": "Noida",
    })
    await session.commit()

    # 1. Create Price Book v1
    pb1 = await pb_svc.create_price_book(org_id, {
        "project_id": proj.id,
        "title": "Phase 1 Launch Pricing",
        "effective_from": date.today(),
        "base_price_floor": 12000,
        "floor_rise_per_floor": 150,
    })
    await session.commit()
    assert pb1.version == 1
    assert pb1.status == PriceBookStatus.DRAFT

    # Add entry to v1
    entry1 = await pb_svc.add_entry(pb1.id, {
        "unit_type": "3 BHK",
        "base_price": 18000000,
        "price_per_sqft": 12000,
        "total_price": 19500000,
    })
    await session.commit()
    assert entry1.base_price == Decimal("18000000")

    # Publish v1
    published_pb1 = await pb_svc.publish_price_book(org_id, pb1.id, publisher_id=broker_id)
    await session.commit()
    assert published_pb1.status == PriceBookStatus.ACTIVE
    assert published_pb1.published_at is not None

    # 2. Create Price Book v2 (should increment version)
    pb2 = await pb_svc.create_price_book(org_id, {
        "project_id": proj.id,
        "title": "Post-RERA Revision",
        "effective_from": date.today(),
        "base_price_floor": 13500,
    })
    await session.commit()
    assert pb2.version == 2
    assert pb2.status == PriceBookStatus.DRAFT

    # Publish v2 -> Should automatically supersede v1
    published_pb2 = await pb_svc.publish_price_book(org_id, pb2.id, publisher_id=broker_id)
    await session.commit()
    assert published_pb2.status == PriceBookStatus.ACTIVE

    # Check v1 status is now SUPERSEDED
    v1_check = (await session.execute(
        select(ProjectPriceBook).where(ProjectPriceBook.id == pb1.id)
    )).scalar_one()
    assert v1_check.status == PriceBookStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_inventory_snapshot_materialization(inventory_session):
    session, org_id, broker_id = inventory_session
    proj_svc = ProjectService(session)
    unit_svc = UnitService(session)
    snap_svc = InventorySnapshotService(session)

    proj = await proj_svc.create_project(org_id, broker_id, {
        "project_name": "Oberoi Sky City",
        "city": "Mumbai",
        "locality": "Borivali",
    })
    await session.commit()

    # Create 3 units
    u1 = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id, "unit_number": "A-101", "unit_type": "2 BHK", "total_price": 22000000
    })
    u2 = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id, "unit_number": "A-102", "unit_type": "3 BHK", "total_price": 31000000
    })
    u3 = await unit_svc.create_unit(org_id, broker_id, {
        "project_id": proj.id, "unit_number": "A-103", "unit_type": "3 BHK", "total_price": 32500000
    })
    await session.commit()

    # Reserve u2
    await unit_svc.transition_status(org_id, u2.id, UnitInventoryStatus.RESERVED, reason="Hold")
    await session.commit()

    # Materialize snapshot
    snapshot = await snap_svc.materialize_snapshot(org_id, proj.id)
    await session.commit()

    assert snapshot.total_units == 3
    assert snapshot.available_units == 2
    assert snapshot.reserved_units == 1
    assert snapshot.sold_units == 0
    assert snapshot.by_unit_type["2 BHK"]["available"] == 1
    assert snapshot.by_unit_type["3 BHK"]["reserved"] == 1
    assert snapshot.price_range_available["min"] == 22000000.0
    assert snapshot.price_range_available["max"] == 32500000.0

    # Retrieve latest snapshot
    retrieved = await snap_svc.get_latest_snapshot(org_id, proj.id)
    assert retrieved.id == snapshot.id
    assert retrieved.available_units == 2
