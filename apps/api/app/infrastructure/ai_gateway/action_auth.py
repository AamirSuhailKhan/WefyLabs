"""Server-side authorization for AI-proposed actions.

LLM `confirmed=true` is never sufficient. A human confirmation must create
an authorization record that tools verify before EXECUTE/CONFIRM actions.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.tenancy.scope import require_organization_id
from app.models.ai_foundation_models import AIActionAuthorization

READ = "READ"
SUGGEST = "SUGGEST"
CONFIRM = "CONFIRM"
EXECUTE = "EXECUTE"


class AIActionAuthorizer:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def hash_parameters(parameters: Optional[Dict[str, Any]]) -> str:
        payload = json.dumps(parameters or {}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def create_authorization(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        actor_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        safety_level: str = CONFIRM,
        confirmation_method: str = "human",
        ttl_seconds: int = 900,
        idempotency_key: Optional[str] = None,
    ) -> AIActionAuthorization:
        if safety_level not in {READ, SUGGEST, CONFIRM, EXECUTE}:
            raise ValueError("Invalid safety_level")
        org = require_organization_id(organization_id)
        key = idempotency_key or f"ai-auth:{org}:{action_type}:{resource_id}:{uuid.uuid4()}"
        existing = await self.db.execute(
            select(AIActionAuthorization).where(AIActionAuthorization.idempotency_key == key)
        )
        found = existing.scalars().first()
        if found:
            return found
        record = AIActionAuthorization(
            organization_id=org,
            actor_id=str(actor_id),
            action_type=action_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            parameters_hash=self.hash_parameters(parameters),
            status="authorized",
            confirmation_method=confirmation_method,
            idempotency_key=key,
            safety_level=safety_level,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def issue_authorization(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        actor_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        safety_level: str = CONFIRM,
        confirmation_method: str = "human",
        ttl_seconds: int = 900,
        idempotency_key: Optional[str] = None,
    ) -> str:
        rec = await self.create_authorization(
            organization_id=organization_id,
            actor_id=actor_id,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            parameters=parameters,
            safety_level=safety_level,
            confirmation_method=confirmation_method,
            ttl_seconds=ttl_seconds,
            idempotency_key=idempotency_key,
        )
        return str(rec.id)

    async def verify(
        self,
        *,
        authorization_id: Union[str, uuid.UUID],
        organization_id: Union[str, uuid.UUID],
        action_type: str,
        resource_type: str,
        resource_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        consume: bool = True,
    ) -> AIActionAuthorization:
        org = require_organization_id(organization_id)
        auth_uuid = authorization_id if isinstance(authorization_id, uuid.UUID) else uuid.UUID(str(authorization_id))
        result = await self.db.execute(
            select(AIActionAuthorization).where(
                AIActionAuthorization.id == auth_uuid,
                AIActionAuthorization.organization_id == org,
            )
        )
        record = result.scalars().first()
        if record is None:
            # Check if record belongs to another organization for explicit cross-tenant detection
            other = await self.db.execute(
                select(AIActionAuthorization).where(AIActionAuthorization.id == auth_uuid)
            )
            if other.scalars().first() is not None:
                raise PermissionError("Organization mismatch: AI action authorization belongs to another tenant.")
            raise PermissionError("AI action authorization was not found for this tenant.")
        if record.status == "consumed":
            raise PermissionError("AI action authorization has already been consumed.")
        if record.status != "authorized":
            raise PermissionError("AI action authorization is not usable.")
        if record.expires_at.replace(tzinfo=record.expires_at.tzinfo or timezone.utc) < datetime.now(timezone.utc):
            record.status = "expired"
            raise PermissionError("AI action authorization has expired.")
        if record.action_type != action_type or record.resource_type != resource_type or str(record.resource_id) != str(resource_id):
            raise PermissionError("AI action authorization does not match the requested action.")
        if record.parameters_hash != self.hash_parameters(parameters):
            raise PermissionError("Parameter hash mismatch: AI action parameters do not match the authorized hash.")
        if consume and record.status == "authorized":
            record.status = "consumed"
            record.consumed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return record
