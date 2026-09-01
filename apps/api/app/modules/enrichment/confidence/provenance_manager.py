"""
Volume 2 PART 2 — Data Provenance Manager
Enforces strict field update guardrails based on source type precedence:
verified > observed > inferred
Never overwrites observed data with inferred data automatically.
"""
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Precedence rank
SOURCE_PRECEDENCE = {
    "verified": 3,
    "observed": 2,
    "inferred": 1
}


class ProvenanceManager:
    @staticmethod
    def should_update_field(
        existing_source_type: Optional[str],
        existing_confidence: float,
        new_source_type: str,
        new_confidence: float
    ) -> Tuple[bool, str]:
        """
        Determines whether a target field should be updated.
        Returns (should_update: bool, reason: str).
        """
        if not existing_source_type:
            return True, "Initial field value assignment"

        old_rank = SOURCE_PRECEDENCE.get(existing_source_type.lower(), 1)
        new_rank = SOURCE_PRECEDENCE.get(new_source_type.lower(), 1)

        # Rule 1: Never overwrite observed or verified with inferred data
        if old_rank > new_rank:
            msg = f"Rejected: Cannot overwrite higher precedence '{existing_source_type}' data with '{new_source_type}' data."
            logger.info(f"[PROVENANCE_GUARD] {msg}")
            return False, msg

        # Rule 2: Same precedence rank -> Update only if new confidence is higher
        if old_rank == new_rank:
            if new_confidence > existing_confidence:
                return True, f"Updated: New confidence ({new_confidence}) exceeds existing confidence ({existing_confidence})."
            else:
                msg = f"Rejected: New confidence ({new_confidence}) is not higher than existing confidence ({existing_confidence})."
                return False, msg

        # Rule 3: Higher rank replaces lower rank (e.g. observed/verified replacing inferred)
        return True, f"Updated: Higher precedence '{new_source_type}' replaces '{existing_source_type}'."
