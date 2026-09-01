"""
AI Agent Default Configuration Seeder.

Called during FastAPI lifespan startup. Creates a default AgentConfiguration
for any organization that does not yet have one, ensuring every tenant
gets a working agent out of the box.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent_models import AgentConfiguration

logger = logging.getLogger("beetlelabs.ai_agent.seeder")


async def seed_default_agent_configuration(
    db: AsyncSession,
    organization_id: str,
    agent_name: str = "BeetleLabs AI",
) -> AgentConfiguration:
    """
    Ensure a default AgentConfiguration exists for the given organization.
    Called on first message receipt for any org without configuration.
    Idempotent: no-op if configuration already exists.
    """
    result = await db.execute(
        select(AgentConfiguration).where(
            AgentConfiguration.organization_id == organization_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    config = AgentConfiguration(
        organization_id=organization_id,
        agent_name=agent_name,
        enabled_channels_json=["web", "whatsapp", "telegram", "email"],
        llm_provider="openai",
        llm_model="gpt-4o",
        fallback_provider="anthropic",
        fallback_model="claude-3-5-sonnet-20241022",
        max_turns=30,
        max_tokens_per_turn=4096,
        context_window_turns=10,
        summary_every_n_turns=8,
        escalation_confidence_threshold=0.3,
        escalation_high_value_score=85.0,
        strategy_overrides_json=None,
        allow_price_disclosure=True,
        require_tool_grounding=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(config)
    await db.flush()
    logger.info(f"[AgentSeeder] Default configuration created for org: {organization_id}")
    return config
