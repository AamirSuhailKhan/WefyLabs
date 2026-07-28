import hashlib
import os
from datetime import datetime, timezone, timedelta
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker, default_trial_ends_at
from app.modules.auth.schemas import RegisterRequest, OAuthCallbackRequest

def hash_password(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}${key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verifies password against stored PBKDF2 hash."""
    if not hashed or '$' not in hashed:
        return False
    salt_hex, key_hex = hashed.split('$', 1)
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return new_key.hex() == key_hex

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

async def register_broker(db: AsyncSession, req: RegisterRequest) -> Broker:
    # Check for duplicate email, phone, or whatsapp_number
    stmt = select(Broker).where(
        (Broker.email == req.email) | 
        (Broker.phone == req.phone) | 
        (Broker.whatsapp_number == req.whatsapp_number)
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        if existing.email == req.email:
            msg = "A broker with this email already exists."
        elif existing.phone == req.phone:
            msg = "A broker with this phone number already exists."
        else:
            msg = "A broker with this WhatsApp number already exists."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=msg
        )

    broker = Broker(
        email=req.email,
        phone=req.phone,
        name=req.name,
        agency_name=req.agency_name,
        city=req.city or "Bengaluru",
        whatsapp_number=req.whatsapp_number,
        password_hash=hash_password(req.password),
        subscription_status="trial",
        trial_ends_at=default_trial_ends_at()
    )
    db.add(broker)
    await db.commit()
    await db.refresh(broker)
    return broker

async def authenticate_broker(db: AsyncSession, email: str, password: str) -> Broker:
    stmt = select(Broker).where(Broker.email == email)
    result = await db.execute(stmt)
    broker = result.scalars().first()

    if not broker or not broker.password_hash or not verify_password(password, broker.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    return broker

async def sync_oauth_broker(db: AsyncSession, req: OAuthCallbackRequest) -> Broker:
    stmt = select(Broker).where(Broker.email == req.email)
    existing = (await db.execute(stmt)).scalars().first()

    if existing:
        # Broker already registered via OAuth or email
        if req.name and req.name != existing.name:
            existing.name = req.name
        if req.agency_name:
            existing.agency_name = req.agency_name
        if req.city:
            existing.city = req.city
        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new broker for first-time OAuth callback
    # Default phone/whatsapp fallback if not provided in OAuth payload
    phone = req.phone or f"+919{abs(hash(req.email)) % 1000000000:09d}"
    whatsapp = req.whatsapp_number or phone

    # Verify phone / whatsapp uniqueness
    check_stmt = select(Broker).where((Broker.phone == phone) | (Broker.whatsapp_number == whatsapp))
    conflict = (await db.execute(check_stmt)).scalars().first()
    if conflict:
        phone = f"+919{abs(hash(req.email + str(datetime.now().timestamp()))) % 1000000000:09d}"
        whatsapp = phone

    new_broker = Broker(
        email=req.email,
        phone=phone,
        name=req.name,
        agency_name=req.agency_name,
        city=req.city or "Bengaluru",
        whatsapp_number=whatsapp,
        subscription_status="trial",
        trial_ends_at=default_trial_ends_at()
    )
    db.add(new_broker)
    await db.commit()
    await db.refresh(new_broker)
    return new_broker
