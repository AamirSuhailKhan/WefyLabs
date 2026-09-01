import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.marketplace_models import MarketplaceItem, MarketplaceInstallation

router = APIRouter(prefix="/marketplace", tags=["BeetleLabs Marketplace & Developer Ecosystem"])

# --- Schemas ---
class PublishItemRequest(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=100)
    category: str = Field("workflow", max_length=50)
    description: str
    version: str = "1.0.0"
    price_usd: float = Field(0.0, ge=0.0)
    manifest_data: Optional[Dict[str, Any]] = None

class MarketplaceItemResponse(BaseModel):
    id: str
    publisher_name: str
    name: str
    slug: str
    category: str
    description: str
    version: str
    price_usd: float
    downloads_count: int
    rating: float
    security_status: str
    manifest_data: Optional[Dict[str, Any]] = None

class InstallationResponse(BaseModel):
    installation_id: str
    item_id: str
    item_name: str
    category: str
    status: str


# Default Catalog Items for Initial Marketplace Bootstrapping
DEFAULT_MARKETPLACE_CATALOG = [
    {
        "name": "Dubai DLD Off-Plan AI Qualification Pack",
        "slug": "dubai-dld-offplan-pack",
        "publisher_name": "BeetleLabs Official",
        "category": "ai_prompt",
        "description": "Pre-built AI prompt pack for Dubai off-plan buyers, covering payment plans, DLD fees, and Escrow approvals.",
        "version": "1.2.0",
        "price_usd": 0.0,
        "rating": 4.9,
        "security_status": "verified"
    },
    {
        "name": "US RESO MLS Automated Listing Sync",
        "slug": "us-reso-mls-sync",
        "publisher_name": "PropTech Solutions Inc",
        "category": "portal_integration",
        "description": "Bi-directional RESO Web API MLS connector for Zillow, Realtor.com, and local MLS boards.",
        "version": "2.0.1",
        "price_usd": 29.0,
        "rating": 4.8,
        "security_status": "verified"
    },
    {
        "name": "Indian Commercial Lease GCI Calculator Workflow",
        "slug": "in-commercial-lease-workflow",
        "publisher_name": "Apex Real Estate Labs",
        "category": "workflow",
        "description": "Automated workflow DAG for calculating 9-year commercial lease lock-ins and brokerage commission splits.",
        "version": "1.0.0",
        "price_usd": 0.0,
        "rating": 5.0,
        "security_status": "verified"
    }
]

# --- Endpoints ---

@router.get("/items", response_model=List[MarketplaceItemResponse])
async def list_marketplace_items(
    category: Optional[str] = Query(None, description="Filter by category: workflow, ai_prompt, portal_integration, analytics, country_pack"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns verified marketplace developer packages, workflow templates, and country packs.
    """
    stmt = select(MarketplaceItem).where(MarketplaceItem.security_status == "verified")
    if category:
        stmt = stmt.where(MarketplaceItem.category == category.lower())

    res = await db.execute(stmt)
    items = res.scalars().all()

    # If DB catalog is empty, return initial bootstrapped items
    if not items:
        bootstrapped = []
        for idx, item in enumerate(DEFAULT_MARKETPLACE_CATALOG):
            bootstrapped.append(MarketplaceItemResponse(
                id=f"item_{idx+1}",
                publisher_name=item["publisher_name"],
                name=item["name"],
                slug=item["slug"],
                category=item["category"],
                description=item["description"],
                version=item["version"],
                price_usd=item["price_usd"],
                downloads_count=1420 + (idx * 350),
                rating=item["rating"],
                security_status=item["security_status"]
            ))
        return bootstrapped

    return [
        MarketplaceItemResponse(
            id=str(i.id),
            publisher_name=i.publisher_name,
            name=i.name,
            slug=i.slug,
            category=i.category,
            description=i.description,
            version=i.version,
            price_usd=i.price_usd,
            downloads_count=i.downloads_count,
            rating=i.rating,
            security_status=i.security_status,
            manifest_data=i.manifest_data
        )
        for i in items
    ]


@router.post("/publish", response_model=MarketplaceItemResponse, status_code=status.HTTP_201_CREATED)
async def publish_marketplace_item(
    req: PublishItemRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Developer Publishing Endpoint: Submits a custom workflow, AI prompt pack, or integration.
    Performs automated security verification before approval.
    """
    existing_stmt = select(MarketplaceItem).where(MarketplaceItem.slug == req.slug.lower())
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalars().first():
        raise HTTPException(status_code=400, detail="Slug already registered in Marketplace catalog")

    # Automated Security Verification Pass
    security_flag = "verified"
    if "eval(" in str(req.manifest_data) or "exec(" in str(req.manifest_data):
        security_flag = "flagged"

    item = MarketplaceItem(
        publisher_name=current_broker.name or "Community Developer",
        name=req.name,
        slug=req.slug.lower(),
        category=req.category.lower(),
        description=req.description,
        version=req.version,
        price_usd=req.price_usd,
        security_status=security_flag,
        manifest_data=req.manifest_data or {}
    )

    db.add(item)
    await db.commit()
    await db.refresh(item)

    return MarketplaceItemResponse(
        id=str(item.id),
        publisher_name=item.publisher_name,
        name=item.name,
        slug=item.slug,
        category=item.category,
        description=item.description,
        version=item.version,
        price_usd=item.price_usd,
        downloads_count=0,
        rating=5.0,
        security_status=item.security_status,
        manifest_data=item.manifest_data
    )


@router.post("/install/{item_id}", response_model=InstallationResponse)
async def install_marketplace_item(
    item_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Installs a verified marketplace package into the current broker's active workspace.
    """
    item_stmt = select(MarketplaceItem).where(MarketplaceItem.id == item_id)
    item_res = await db.execute(item_stmt)
    item = item_res.scalars().first()

    if not item:
        # Check if matching bootstrapped item
        raise HTTPException(status_code=404, detail="Marketplace package not found")

    if item.security_status == "flagged":
        raise HTTPException(status_code=403, detail="Item flagged by automated security review")

    inst_stmt = select(MarketplaceInstallation).where(
        MarketplaceInstallation.broker_id == current_broker.id,
        MarketplaceInstallation.item_id == item_id
    )
    inst_res = await db.execute(inst_stmt)
    existing_inst = inst_res.scalars().first()

    if existing_inst:
        existing_inst.status = "active"
        await db.commit()
        return InstallationResponse(
            installation_id=str(existing_inst.id),
            item_id=str(item.id),
            item_name=item.name,
            category=item.category,
            status="active"
        )

    installation = MarketplaceInstallation(
        broker_id=current_broker.id,
        item_id=item.id,
        status="active"
    )

    item.downloads_count += 1
    db.add(installation)
    await db.commit()
    await db.refresh(installation)

    return InstallationResponse(
        installation_id=str(installation.id),
        item_id=str(item.id),
        item_name=item.name,
        category=item.category,
        status=installation.status
    )


@router.get("/installed", response_model=List[InstallationResponse])
async def list_installed_items(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all active installed marketplace extensions for the current broker workspace.
    """
    stmt = (
        select(MarketplaceInstallation)
        .where(
            MarketplaceInstallation.broker_id == current_broker.id,
            MarketplaceInstallation.status == "active"
        )
    )
    res = await db.execute(stmt)
    installations = res.scalars().all()

    return [
        InstallationResponse(
            installation_id=str(inst.id),
            item_id=str(inst.item_id),
            item_name=inst.item.name if inst.item else "Custom Package",
            category=inst.item.category if inst.item else "extension",
            status=inst.status
        )
        for inst in installations
    ]
