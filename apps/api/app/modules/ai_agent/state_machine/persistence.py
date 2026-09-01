"""
FSM Persistence — save and restore ConversationFSM from PostgreSQL.
Uses SQLAlchemy async session. Called by ConversationManager on every turn.
"""
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.modules.ai_agent.state_machine.fsm import ConversationFSM, State
from app.models.agent_models import AgentSession, ConversationState


async def save_state(
    db: AsyncSession,
    session_id: str,
    fsm: ConversationFSM,
    turn_index: int,
    customer_message: Optional[str] = None,
    agent_response: Optional[str] = None,
    tools_called: Optional[dict] = None,
    trigger: Optional[str] = None,
    reason: Optional[str] = None,
) -> ConversationState:
    """
    Persist the current FSM state as an immutable ConversationState row.
    Also updates AgentSession.current_state for fast reads.
    """
    # Determine from_state from history
    from_state = State.NEW
    if fsm.history:
        from_state = fsm.history[-1]["from"]

    # Insert immutable state row
    state_row = ConversationState(
        session_id=session_id,
        turn_index=turn_index,
        from_state=from_state,
        to_state=fsm.current_state,
        trigger=trigger,
        transition_reason=reason,
        customer_message=customer_message,
        agent_response=agent_response,
        tools_called=tools_called,
        metadata_json={"history_length": len(fsm.history)},
    )
    db.add(state_row)

    # Update session snapshot
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(
            current_state=fsm.current_state,
            turn_count=turn_index,
            last_message_at=datetime.now(timezone.utc),
        )
    )

    await db.flush()
    return state_row


async def restore_state(db: AsyncSession, session_id: str) -> ConversationFSM:
    """
    Rebuild a ConversationFSM from the persisted AgentSession current_state
    and ConversationState history. Called on server restart.
    """
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ValueError(f"AgentSession {session_id} not found")

    # Load full history for FSM
    history_result = await db.execute(
        select(ConversationState)
        .where(ConversationState.session_id == session_id)
        .order_by(ConversationState.turn_index)
    )
    rows = history_result.scalars().all()

    history = [
        {
            "from": r.from_state,
            "trigger": r.trigger or "",
            "to": r.to_state,
            "reason": r.transition_reason,
        }
        for r in rows
    ]

    fsm = ConversationFSM(
        current_state=session.current_state,
        history=history,
    )
    return fsm
