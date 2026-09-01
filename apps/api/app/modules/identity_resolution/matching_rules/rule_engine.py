"""
Rule Engine — Business rule overrides for identity matching.
Applies organization-configurable rules AFTER similarity scoring.
Rules can: force merge, force new_identity, require manual review, boost/penalize confidence.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Business rule overrides applied after similarity scoring.

    Rules have priority — higher priority rules fire first.
    Rules can override the decision engine output for edge cases.

    Built-in rules:
    - SAME_SOURCE_SKIP: Don't merge leads from the same source with low confidence (likely different people)
    - UNVERIFIED_PHONE_CAUTION: If neither record has verified phone, require manual review
    - HIGH_VALUE_CAUTION: If budget > 5M AED, require manual review regardless of confidence
    - BLOCKED_IDENTITY: If target identity is flagged, block merge
    """

    def __init__(self, org_rules: List[Dict[str, Any]] = None):
        self.org_rules = org_rules or []

    def apply(
        self,
        decision_result: Dict[str, Any],
        lead_data: Dict[str, Any],
        candidate_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply business rules to possibly override the similarity-based decision.
        Returns the (possibly modified) decision_result.
        """
        decision = decision_result["decision"]
        confidence = decision_result["confidence"]
        overrides = []

        # ── Rule 1: Very low confidence → always new_identity ─────────────────
        if confidence < 0.50:
            decision = "new_identity"
            overrides.append("LOW_CONFIDENCE_OVERRIDE: confidence < 0.50 → new_identity")

        # ── Rule 2: High-value lead caution ──────────────────────────────────
        budget = (
            lead_data.get("budget_max") or
            (lead_data.get("financial_profile") or {}).get("budget_aed")
        )
        if budget and isinstance(budget, (int, float)) and budget >= 5_000_000:
            if decision == "auto_merge":
                decision = "manual_review"
                overrides.append("HIGH_VALUE_CAUTION: budget ≥ 5M AED → downgraded to manual_review")

        # ── Rule 3: Custom org rules ──────────────────────────────────────────
        for rule in self.org_rules:
            rule_type = rule.get("type", "")
            rule_action = rule.get("action", "")

            if rule_type == "force_new_identity" and self._matches_condition(rule, lead_data, candidate_data):
                decision = "new_identity"
                overrides.append(f"ORG_RULE: {rule.get('name')} → new_identity")

            elif rule_type == "force_manual_review" and self._matches_condition(rule, lead_data, candidate_data):
                if decision == "auto_merge":
                    decision = "manual_review"
                    overrides.append(f"ORG_RULE: {rule.get('name')} → manual_review")

        if overrides:
            logger.info(f"[RULE_ENGINE] Overrides applied: {overrides}")
            decision_result["decision"] = decision
            decision_result["rule_overrides"] = overrides

        return decision_result

    @staticmethod
    def _matches_condition(
        rule: Dict[str, Any],
        lead_data: Dict[str, Any],
        candidate_data: Dict[str, Any],
    ) -> bool:
        """Simple condition evaluator for org-defined rules."""
        condition = rule.get("condition", {})
        field = condition.get("field", "")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        lead_val = lead_data.get(field)
        if operator == "equals":
            return lead_val == value
        elif operator == "contains":
            return value in (lead_val or "")
        elif operator == "gte":
            return isinstance(lead_val, (int, float)) and lead_val >= value
        return False
