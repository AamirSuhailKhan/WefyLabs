"""
Conversation State Machine — FSM transitions for the Autonomous AI Sales Agent.

States (12):
  new → greeting → discovering → qualifying → explaining → recommending →
  negotiating → booking → waiting → follow_up → human_handoff → closed

Triggers (9):
  GREETING_SENT | INFO_COLLECTED | QUALIFIED | PROPERTY_SHOWN |
  OBJECTION_RAISED | BOOKING_CONFIRMED | HUMAN_REQUESTED |
  INACTIVITY_TIMEOUT | CONVERSATION_ENDED
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional


# ─── State Definitions ────────────────────────────────────────────────────────

class State:
    NEW = "new"
    GREETING = "greeting"
    DISCOVERING = "discovering"
    QUALIFYING = "qualifying"
    EXPLAINING = "explaining"
    RECOMMENDING = "recommending"
    NEGOTIATING = "negotiating"
    BOOKING = "booking"
    WAITING = "waiting"
    FOLLOW_UP = "follow_up"
    HUMAN_HANDOFF = "human_handoff"
    CLOSED = "closed"

    ALL: Set[str] = {
        NEW, GREETING, DISCOVERING, QUALIFYING, EXPLAINING,
        RECOMMENDING, NEGOTIATING, BOOKING, WAITING, FOLLOW_UP,
        HUMAN_HANDOFF, CLOSED
    }
    TERMINAL: Set[str] = {HUMAN_HANDOFF, CLOSED}


# ─── Trigger Definitions ─────────────────────────────────────────────────────

class Trigger:
    GREETING_SENT = "GREETING_SENT"
    INFO_COLLECTED = "INFO_COLLECTED"
    QUALIFIED = "QUALIFIED"
    PROPERTY_SHOWN = "PROPERTY_SHOWN"
    OBJECTION_RAISED = "OBJECTION_RAISED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    INACTIVITY_TIMEOUT = "INACTIVITY_TIMEOUT"
    CONVERSATION_ENDED = "CONVERSATION_ENDED"
    FOLLOW_UP_INITIATED = "FOLLOW_UP_INITIATED"
    NEGOTIATION_STARTED = "NEGOTIATION_STARTED"
    RECOMMENDATION_ACCEPTED = "RECOMMENDATION_ACCEPTED"
    WAITING_RESOLVED = "WAITING_RESOLVED"


# ─── Transition Table ─────────────────────────────────────────────────────────
# (from_state, trigger) → to_state
# Any (from_state, trigger) not in this table is an invalid transition.

TRANSITION_TABLE: Dict[Tuple[str, str], str] = {
    # From NEW
    (State.NEW,           Trigger.GREETING_SENT):          State.GREETING,
    (State.NEW,           Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,

    # From GREETING
    (State.GREETING,      Trigger.INFO_COLLECTED):          State.DISCOVERING,
    (State.GREETING,      Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.GREETING,      Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From DISCOVERING
    (State.DISCOVERING,   Trigger.INFO_COLLECTED):          State.QUALIFYING,
    (State.DISCOVERING,   Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.DISCOVERING,   Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From QUALIFYING
    (State.QUALIFYING,    Trigger.QUALIFIED):                State.RECOMMENDING,
    (State.QUALIFYING,    Trigger.PROPERTY_SHOWN):          State.EXPLAINING,
    (State.QUALIFYING,    Trigger.INFO_COLLECTED):          State.QUALIFYING,    # self-loop: more info
    (State.QUALIFYING,    Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.QUALIFYING,    Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From EXPLAINING
    (State.EXPLAINING,    Trigger.QUALIFIED):                State.RECOMMENDING,
    (State.EXPLAINING,    Trigger.OBJECTION_RAISED):        State.NEGOTIATING,
    (State.EXPLAINING,    Trigger.RECOMMENDATION_ACCEPTED): State.BOOKING,
    (State.EXPLAINING,    Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.EXPLAINING,    Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From RECOMMENDING
    (State.RECOMMENDING,  Trigger.PROPERTY_SHOWN):          State.EXPLAINING,
    (State.RECOMMENDING,  Trigger.RECOMMENDATION_ACCEPTED): State.BOOKING,
    (State.RECOMMENDING,  Trigger.NEGOTIATION_STARTED):     State.NEGOTIATING,
    (State.RECOMMENDING,  Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.RECOMMENDING,  Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From NEGOTIATING
    (State.NEGOTIATING,   Trigger.BOOKING_CONFIRMED):       State.BOOKING,
    (State.NEGOTIATING,   Trigger.PROPERTY_SHOWN):          State.EXPLAINING,
    (State.NEGOTIATING,   Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.NEGOTIATING,   Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From BOOKING
    (State.BOOKING,       Trigger.BOOKING_CONFIRMED):       State.CLOSED,
    (State.BOOKING,       Trigger.OBJECTION_RAISED):        State.NEGOTIATING,
    (State.BOOKING,       Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.BOOKING,       Trigger.INACTIVITY_TIMEOUT):      State.WAITING,

    # From WAITING
    (State.WAITING,       Trigger.WAITING_RESOLVED):        State.FOLLOW_UP,
    (State.WAITING,       Trigger.CONVERSATION_ENDED):      State.CLOSED,
    (State.WAITING,       Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,

    # From FOLLOW_UP
    (State.FOLLOW_UP,     Trigger.INFO_COLLECTED):          State.QUALIFYING,
    (State.FOLLOW_UP,     Trigger.BOOKING_CONFIRMED):       State.CLOSED,
    (State.FOLLOW_UP,     Trigger.HUMAN_REQUESTED):         State.HUMAN_HANDOFF,
    (State.FOLLOW_UP,     Trigger.CONVERSATION_ENDED):      State.CLOSED,

    # Terminal states — only allow forced close
    (State.HUMAN_HANDOFF, Trigger.CONVERSATION_ENDED):      State.CLOSED,
}


# ─── FSM Error ───────────────────────────────────────────────────────────────

class InvalidTransitionError(Exception):
    """Raised when an illegal FSM transition is attempted."""
    def __init__(self, from_state: str, trigger: str) -> None:
        super().__init__(
            f"Invalid FSM transition: '{from_state}' + trigger '{trigger}' has no valid target state."
        )
        self.from_state = from_state
        self.trigger = trigger


# ─── FSM Dataclass ───────────────────────────────────────────────────────────

@dataclass
class ConversationFSM:
    """
    Conversation Finite State Machine.
    Lightweight, serialisable dataclass — no async I/O here.
    Persistence is handled by state_machine.persistence.
    """
    current_state: str = State.NEW
    history: list = field(default_factory=list)

    def can_transition(self, trigger: str) -> bool:
        """Return True if the trigger is valid from the current state."""
        return (self.current_state, trigger) in TRANSITION_TABLE

    def transition(self, trigger: str, reason: Optional[str] = None) -> str:
        """
        Apply trigger and advance to next state.
        Returns the new state name.
        Raises InvalidTransitionError on illegal transition.
        """
        key = (self.current_state, trigger)
        if key not in TRANSITION_TABLE:
            raise InvalidTransitionError(self.current_state, trigger)
        next_state = TRANSITION_TABLE[key]
        self.history.append({
            "from": self.current_state,
            "trigger": trigger,
            "to": next_state,
            "reason": reason,
        })
        self.current_state = next_state
        return next_state

    def is_terminal(self) -> bool:
        return self.current_state in State.TERMINAL

    def valid_triggers(self) -> list:
        """Return list of triggers valid from the current state."""
        return [t for (s, t) in TRANSITION_TABLE if s == self.current_state]
