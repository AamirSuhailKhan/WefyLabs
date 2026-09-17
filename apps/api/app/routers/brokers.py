from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.schemas.broker import BrokerResponse, BrokerUpdate

router = APIRouter(prefix="/brokers", tags=["Brokers"])

@router.get("/me", response_model=BrokerResponse)
async def get_broker_me(current_broker: Broker = Depends(get_current_broker)):
    """Returns current broker profile including subscription status and trial days remaining."""
    return BrokerResponse.model_validate(current_broker)

@router.patch("/me", response_model=BrokerResponse)
async def update_broker_me(
    update_data: BrokerUpdate,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates broker profile information (name, agency_name, city, whatsapp_number, phone).
    Email cannot be updated. Enforces unique phone and whatsapp_number.
    """
    fields_to_update = update_data.model_dump(exclude_unset=True)

    if not fields_to_update:
        return BrokerResponse.model_validate(current_broker)

    # Validate uniqueness if phone or whatsapp_number is changing
    new_phone = fields_to_update.get("phone")
    new_whatsapp = fields_to_update.get("whatsapp_number")

    if new_phone and new_phone != current_broker.phone:
        stmt = select(Broker).where(Broker.phone == new_phone, Broker.id != current_broker.id)
        if (await db.execute(stmt)).scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already in use by another broker."
            )
        current_broker.phone = new_phone

    if new_whatsapp and new_whatsapp != current_broker.whatsapp_number:
        stmt = select(Broker).where(Broker.whatsapp_number == new_whatsapp, Broker.id != current_broker.id)
        if (await db.execute(stmt)).scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="WhatsApp number is already in use by another broker."
            )
        current_broker.whatsapp_number = new_whatsapp

    if "name" in fields_to_update and fields_to_update["name"]:
        current_broker.name = fields_to_update["name"]

    if "agency_name" in fields_to_update:
        current_broker.agency_name = fields_to_update["agency_name"]

    if "city" in fields_to_update and fields_to_update["city"]:
        current_broker.city = fields_to_update["city"]

    current_broker.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_broker)

    return BrokerResponse.model_validate(current_broker)


@router.delete("/me", summary="Delete current broker account")
async def delete_current_broker(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Deletes current broker account with external Google OAuth token revocation."""
    from app.modules.auth.account_deletion_service import AccountDeletionService
    return await AccountDeletionService.delete_broker_account(
        db=db,
        broker_id=current_broker.id
    )

