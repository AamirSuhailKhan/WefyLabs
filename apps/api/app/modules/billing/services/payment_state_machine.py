"""
BeetleLabs Payment State Machine
================================
Defines the authoritative lifecycle states and immutable transition guards
for the Razorpay payment, order, and refund subsystem.

Guarantees:
- Terminal states (e.g. PAYMENT_CAPTURED, REFUNDED, PAYMENT_CANCELLED) cannot regress.
- Invalid state transitions (e.g. CAPTURED -> FAILED) are rejected with custom exceptions.
- Idempotent: Requesting the same transition on an entity already in that state is a safe no-op.
"""
from __future__ import annotations

import logging
from typing import Dict, Set, Optional
from app.models.payment_models import PaymentStatus, RefundStatus

logger = logging.getLogger("beetlelabs.billing.state_machine")


class InvalidPaymentStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted on a payment entity."""
    def __init__(self, current_state: str, target_state: str, entity_id: Optional[str] = None):
        self.current_state = current_state
        self.target_state = target_state
        self.entity_id = entity_id
        msg = f"Invalid payment state transition from '{current_state}' to '{target_state}'"
        if entity_id:
            msg += f" for entity ID '{entity_id}'"
        super().__init__(msg)


class PaymentStateMachine:
    """
    Authoritative state machine governing payment orders and transactions.
    """

    # Explicit allowed forward transitions
    VALID_TRANSITIONS: Dict[PaymentStatus, Set[PaymentStatus]] = {
        PaymentStatus.ORDER_CREATED: {
            PaymentStatus.PAYMENT_ATTEMPTED,
            PaymentStatus.PAYMENT_AUTHORIZED,
            PaymentStatus.PAYMENT_CAPTURED,
            PaymentStatus.PAYMENT_FAILED,
            PaymentStatus.PAYMENT_CANCELLED,
        },
        PaymentStatus.PAYMENT_ATTEMPTED: {
            PaymentStatus.PAYMENT_AUTHORIZED,
            PaymentStatus.PAYMENT_CAPTURED,
            PaymentStatus.PAYMENT_FAILED,
            PaymentStatus.PAYMENT_CANCELLED,
        },
        PaymentStatus.PAYMENT_AUTHORIZED: {
            PaymentStatus.PAYMENT_CAPTURED,
            PaymentStatus.PAYMENT_FAILED,
            PaymentStatus.PAYMENT_CANCELLED,
        },
        PaymentStatus.PAYMENT_CAPTURED: {
            PaymentStatus.REFUND_REQUESTED,
            PaymentStatus.REFUND_PROCESSING,
            PaymentStatus.REFUNDED,
        },
        PaymentStatus.PAYMENT_FAILED: {
            # Allows customer to re-attempt checkout on the same order before cancellation
            PaymentStatus.PAYMENT_ATTEMPTED,
            PaymentStatus.PAYMENT_AUTHORIZED,
            PaymentStatus.PAYMENT_CAPTURED,
            PaymentStatus.PAYMENT_CANCELLED,
        },
        PaymentStatus.PAYMENT_CANCELLED: set(),  # Terminal
        PaymentStatus.REFUND_REQUESTED: {
            PaymentStatus.REFUND_PROCESSING,
            PaymentStatus.REFUNDED,
            PaymentStatus.REFUND_FAILED,
        },
        PaymentStatus.REFUND_PROCESSING: {
            PaymentStatus.REFUNDED,
            PaymentStatus.REFUND_FAILED,
        },
        PaymentStatus.REFUNDED: set(),  # Terminal
        PaymentStatus.REFUND_FAILED: {
            PaymentStatus.REFUND_REQUESTED,
        },
    }

    # Refund-specific state transitions
    VALID_REFUND_TRANSITIONS: Dict[RefundStatus, Set[RefundStatus]] = {
        RefundStatus.REFUND_REQUESTED: {
            RefundStatus.REFUND_PROCESSING,
            RefundStatus.REFUNDED,
            RefundStatus.REFUND_FAILED,
        },
        RefundStatus.REFUND_PROCESSING: {
            RefundStatus.REFUNDED,
            RefundStatus.REFUND_FAILED,
        },
        RefundStatus.REFUNDED: set(),  # Terminal
        RefundStatus.REFUND_FAILED: {
            RefundStatus.REFUND_REQUESTED,
        },
    }

    @classmethod
    def can_transition(cls, current_state: str, target_state: str) -> bool:
        """
        Returns True if transition is valid or is an idempotent no-op.
        """
        # Idempotent match
        if current_state == target_state:
            return True

        try:
            curr_enum = PaymentStatus(current_state)
            target_enum = PaymentStatus(target_state)
        except ValueError:
            return False

        allowed = cls.VALID_TRANSITIONS.get(curr_enum, set())
        return target_enum in allowed

    @classmethod
    def validate_transition(cls, current_state: str, target_state: str, entity_id: Optional[str] = None) -> bool:
        """
        Validates transition. Returns True if state changed, False if already in target state (idempotent).
        Raises InvalidPaymentStateTransitionError if transition is forbidden.
        """
        if current_state == target_state:
            logger.debug(f"[StateMachine] Idempotent transition request: {current_state} -> {target_state}")
            return False  # No change needed

        if not cls.can_transition(current_state, target_state):
            logger.error(
                f"[StateMachine REJECTED] Illegal state transition: {current_state} -> {target_state} (entity: {entity_id})"
            )
            raise InvalidPaymentStateTransitionError(current_state, target_state, entity_id)

        logger.info(f"[StateMachine TRANSITION] {current_state} -> {target_state} (entity: {entity_id})")
        return True

    @classmethod
    def can_refund_transition(cls, current_state: str, target_state: str) -> bool:
        if current_state == target_state:
            return True
        try:
            curr_enum = RefundStatus(current_state)
            target_enum = RefundStatus(target_state)
        except ValueError:
            return False
        return target_enum in cls.VALID_REFUND_TRANSITIONS.get(curr_enum, set())

    @classmethod
    def validate_refund_transition(cls, current_state: str, target_state: str, refund_id: Optional[str] = None) -> bool:
        if current_state == target_state:
            return False
        if not cls.can_refund_transition(current_state, target_state):
            raise InvalidPaymentStateTransitionError(current_state, target_state, refund_id)
        return True
