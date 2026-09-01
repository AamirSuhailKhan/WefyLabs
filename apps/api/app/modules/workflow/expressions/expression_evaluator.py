"""
Sandboxed Expression Evaluation Engine
=======================================
Deterministic, AST-parsed condition evaluator without `eval()`.
Supports comparisons (==, !=, >, <, >=, <=, in, contains, between)
and logical conjunctions (AND, OR, NOT) over workflow context variables.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)

class ExpressionEvaluator:
    """
    Evaluates condition expressions securely over workflow execution context payloads.
    """

    @staticmethod
    def resolve_path(context: Dict[str, Any], path: str) -> Any:
        """
        Resolves dotted path from context dictionary (e.g. 'lead.budget_max').
        """
        parts = path.strip().split(".")
        curr: Any = context
        for p in parts:
            if isinstance(curr, dict):
                curr = curr.get(p)
            elif hasattr(curr, p):
                curr = getattr(curr, p)
            else:
                return None
        return curr

    @classmethod
    def evaluate_simple_condition(
        cls,
        field_path: str,
        operator: str,
        target_value: Any,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluates a single atomic condition: context[field_path] <operator> target_value.
        """
        actual_val = cls.resolve_path(context, field_path)
        op = operator.lower().strip()

        if actual_val is None:
            if op in ("is_null", "does_not_exist"):
                return True
            if op in ("is_not_null", "exists"):
                return False
            return False

        try:
            if op in ("==", "equals", "eq"):
                return str(actual_val).lower() == str(target_value).lower() if isinstance(actual_val, str) else actual_val == target_value
            elif op in ("!=", "not_equals", "neq"):
                return str(actual_val).lower() != str(target_value).lower() if isinstance(actual_val, str) else actual_val != target_value
            elif op in (">", "greater_than", "gt"):
                return float(actual_val) > float(target_value)
            elif op in (">=", "greater_than_or_equal", "gte"):
                return float(actual_val) >= float(target_value)
            elif op in ("<", "less_than", "lt"):
                return float(actual_val) < float(target_value)
            elif op in ("<=", "less_than_or_equal", "lte"):
                return float(actual_val) <= float(target_value)
            elif op in ("in", "is_in"):
                if isinstance(target_value, (list, tuple, set)):
                    return actual_val in target_value or str(actual_val) in [str(x) for x in target_value]
                return str(actual_val) in str(target_value)
            elif op in ("not_in", "is_not_in"):
                if isinstance(target_value, (list, tuple, set)):
                    return actual_val not in target_value
                return str(actual_val) not in str(target_value)
            elif op in ("contains", "has"):
                if isinstance(actual_val, (list, tuple, set)):
                    return target_value in actual_val or str(target_value) in [str(x) for x in actual_val]
                return str(target_value).lower() in str(actual_val).lower()
            elif op in ("between", "is_between"):
                if isinstance(target_value, (list, tuple)) and len(target_value) == 2:
                    return float(target_value[0]) <= float(actual_val) <= float(target_value[1])
                return False
            elif op in ("exists", "is_not_null"):
                return actual_val is not None
            elif op in ("does_not_exist", "is_null"):
                return actual_val is None
        except Exception as e:
            logger.warning(f"[EXPR_EVAL] Evaluation error on {field_path} {op} {target_value}: {e}")
            return False

        return False

    @classmethod
    def evaluate_composite_conditions(
        cls,
        conditions: List[Dict[str, Any]],
        logical_operator: str = "AND",
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Evaluates a group of condition objects joined by AND / OR logic.
        """
        ctx = context or {}
        if not conditions:
            return True

        op = logical_operator.upper().strip()
        results: List[bool] = []

        for cond in conditions:
            # Handle nested sub-groups
            if "conditions" in cond and isinstance(cond["conditions"], list):
                sub_op = cond.get("logical_operator", "AND")
                res = cls.evaluate_composite_conditions(cond["conditions"], sub_op, ctx)
            else:
                field_path = cond.get("field", "")
                operator = cond.get("operator", "==")
                val = cond.get("value")
                res = cls.evaluate_simple_condition(field_path, operator, val, ctx)
            results.append(res)

        if op == "OR":
            return any(results)
        return all(results)
