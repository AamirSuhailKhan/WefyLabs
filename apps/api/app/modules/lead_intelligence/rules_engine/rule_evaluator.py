"""
Rule Evaluator — Configurable Rules Engine
==========================================
Evaluates organization-defined scoring rules against extracted feature vectors.
Supports runtime editing without code deployment.
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class RuleEvaluator:
    """
    Evaluates scoring rules against lead feature vectors.
    """

    def evaluate_rules(
        self,
        features: Dict[str, Any],
        custom_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Returns (score_adjustment, rules_fired_list)
        """
        rules = custom_rules or self._default_rules()
        adjustment = 0.0
        fired = []

        for rule in rules:
            rule_id = rule.get("id") or rule.get("name")
            cond = rule.get("condition_json") or rule.get("condition") or {}
            field = cond.get("field")
            op = cond.get("operator", "==")
            target_val = cond.get("value")

            if not field or field not in features:
                continue

            feat_val = features[field]

            if self._check_condition(feat_val, op, target_val):
                act_val = float(rule.get("action_value") or 0.0)
                adjustment += act_val
                fired.append({
                    "rule_id": str(rule_id),
                    "name": rule.get("name") or field,
                    "action_value": act_val,
                    "condition": cond,
                })

        return adjustment, fired

    @staticmethod
    def _check_condition(val: Any, op: str, target: Any) -> bool:
        try:
            if op in ("==", "equals"):
                return val == target
            elif op in ("!=", "not_equals"):
                return val != target
            elif op in (">", "gt"):
                return float(val) > float(target)
            elif op in (">=", "gte"):
                return float(val) >= float(target)
            elif op in ("<", "lt"):
                return float(val) < float(target)
            elif op in ("<=", "lte"):
                return float(val) <= float(target)
            elif op in ("in", "contains"):
                return target in val if isinstance(val, (list, str)) else False
        except Exception:
            return False
        return False

    @staticmethod
    def _default_rules() -> List[Dict[str, Any]]:
        return [
            {
                "name": "High Budget Boost (> 2M AED)",
                "condition_json": {"field": "budget_aed", "operator": ">=", "value": 2000000},
                "action_value": 20.0,
            },
            {
                "name": "Viewing Booked Boost",
                "condition_json": {"field": "has_viewing_booked", "operator": "==", "value": True},
                "action_value": 30.0,
            },
            {
                "name": "Immediate Timeline Boost",
                "condition_json": {"field": "is_immediate", "operator": "==", "value": True},
                "action_value": 15.0,
            },
            {
                "name": "Cash Buyer / Mortgage Pre-approved Boost",
                "condition_json": {"field": "has_mortgage_preapproval", "operator": "==", "value": True},
                "action_value": 15.0,
            },
            {
                "name": "Inactive > 30 Days Penalty",
                "condition_json": {"field": "lead_age_days", "operator": ">", "value": 30},
                "action_value": -25.0,
            },
        ]
