"""
Part 21.4.1 — Deterministic Qualification Policy Engine
======================================================
Evaluates structured evidence facts against versioned requirement policies.
Zero LLM black-box writes: Qualification decisions are computed purely deterministically.
"""
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone

from app.models.qualification_models import (
    QualificationFact,
    QualificationConflict,
    QualificationRequirementPolicy,
    QualificationState,
    QualificationIntent,
    QualificationBuyerType,
    QualificationTimeline,
    QualificationFinancing,
    FactStatus,
    ConflictStatus,
)
from app.modules.lead_qualification.dto import (
    QualificationSnapshotDTO,
    QualificationEvaluationResultDTO,
    QualificationMissingInfoDTO,
)
from app.modules.lead_qualification.taxonomies import QualificationTaxonomyNormalizer


class DeterministicQualificationPolicyEngine:
    """
    Pure policy evaluation engine for real-estate lead qualification.
    Decoupled from raw evidence and database state.
    """

    DEFAULT_POLICY_VERSION = "v1.0-standard"
    DEFAULT_REQUIRED_FIELDS = ["intent", "location", "property_type"]
    DEFAULT_RECOMMENDED_FIELDS = ["budget_max", "timeline"]
    DEFAULT_OPTIONAL_FIELDS = ["financing", "bedrooms", "buyer_type", "preferred_amenities"]

    QUESTION_TEMPLATES: Dict[str, str] = {
        "intent": "Are you looking to buy, rent, invest, or sell a property?",
        "property_type": "What property type are you looking for (e.g., Apartment, Villa, Townhouse, Penthouse)?",
        "location": "Which specific neighborhood, community, or area in the city do you prefer?",
        "budget_max": "What is your target budget or maximum purchase price?",
        "budget_min": "What is the minimum budget or starting price you are considering?",
        "timeline": "When are you planning to purchase or move into the property?",
        "bedrooms": "How many bedrooms do you need in the property?",
        "financing": "How do you plan to finance this purchase (e.g., Cash, Mortgage, Payment Plan)?",
        "buyer_type": "Is this property intended for personal use (end-user) or as an investment?",
        "preferred_amenities": "Are there any specific amenities or features you require (e.g., pool, gym, balcony, sea view)?",
    }


    @classmethod
    def evaluate(
        cls,
        organization_id: str,
        lead_id: str,
        active_facts: List[QualificationFact],
        open_conflicts: List[QualificationConflict],
        policy: Optional[QualificationRequirementPolicy] = None,
    ) -> QualificationSnapshotDTO:
        """
        Evaluates active facts and conflicts against policy criteria.
        Returns a strongly-typed, immutable QualificationSnapshotDTO.
        """
        # Resolve policy configuration
        policy_version = policy.policy_version if policy else cls.DEFAULT_POLICY_VERSION
        required_fields = policy.required_fields if policy and policy.required_fields else cls.DEFAULT_REQUIRED_FIELDS
        recommended_fields = policy.recommended_fields if policy and policy.recommended_fields else cls.DEFAULT_RECOMMENDED_FIELDS
        min_completeness = policy.min_completeness_for_qualified if policy else 0.8
        min_confidence = policy.min_confidence_for_qualified if policy else 0.7

        # Index active facts by field_name
        facts_by_field: Dict[str, QualificationFact] = {}
        for f in active_facts:
            if f.status == FactStatus.ACTIVE.value:
                facts_by_field[f.field_name] = f

        # Index conflicting fields
        conflicting_fields: List[str] = [
            c.field_name for c in open_conflicts if c.status == ConflictStatus.OPEN.value
        ]

        # Extract normalized field values (STRICT: default to UNKNOWN or None)
        intent = cls._extract_enum(
            facts_by_field.get("intent"),
            QualificationTaxonomyNormalizer.normalize_intent,
            QualificationIntent.UNKNOWN.value,
        )
        buyer_type = cls._extract_enum(
            facts_by_field.get("buyer_type"),
            QualificationTaxonomyNormalizer.normalize_buyer_type,
            QualificationBuyerType.UNKNOWN.value,
        )
        timeline = cls._extract_enum(
            facts_by_field.get("timeline"),
            QualificationTaxonomyNormalizer.normalize_timeline,
            QualificationTimeline.UNKNOWN.value,
        )
        financing = cls._extract_enum(
            facts_by_field.get("financing"),
            QualificationTaxonomyNormalizer.normalize_financing,
            QualificationFinancing.UNKNOWN.value,
        )

        budget_min = cls._extract_int(facts_by_field.get("budget_min"))
        budget_max = cls._extract_int(facts_by_field.get("budget_max"))
        budget_currency = cls._extract_str(facts_by_field.get("budget_currency"))
        location = cls._extract_str(facts_by_field.get("location")) or "UNKNOWN"
        property_type = cls._extract_str(facts_by_field.get("property_type")) or "UNKNOWN"
        bedrooms = cls._extract_int(facts_by_field.get("bedrooms"))

        # Calculate Completeness and Missing Fields
        all_eval_fields = list(dict.fromkeys(required_fields + recommended_fields))
        missing_fields: List[str] = []
        known_count = 0
        total_eval_count = len(all_eval_fields) if all_eval_fields else 1

        for field in all_eval_fields:
            if cls._is_field_known(field, facts_by_field, {
                "intent": intent,
                "buyer_type": buyer_type,
                "timeline": timeline,
                "financing": financing,
                "budget_min": budget_min,
                "budget_max": budget_max,
                "budget_currency": budget_currency,
                "location": location,
                "property_type": property_type,
                "bedrooms": bedrooms,
            }):
                known_count += 1
            else:
                missing_fields.append(field)

        completeness_score = round(known_count / total_eval_count, 4) if total_eval_count > 0 else 0.0

        # Calculate Confidence Score (average confidence of known facts)
        confidence_values = [
            f.confidence for f in facts_by_field.values() if f.confidence is not None
        ]
        confidence_score = round(
            sum(confidence_values) / len(confidence_values), 4
        ) if confidence_values else 0.0

        # Check required fields specifically
        required_missing = [
            rf for rf in required_fields if rf in missing_fields
        ]

        # Determine Qualification State deterministically
        state = cls._determine_state(
            facts_by_field=facts_by_field,
            conflicting_fields=conflicting_fields,
            required_missing=required_missing,
            missing_fields=missing_fields,
            completeness_score=completeness_score,
            confidence_score=confidence_score,
            min_completeness=min_completeness,
            min_confidence=min_confidence,
            intent=intent,
            timeline=timeline,
        )

        return QualificationSnapshotDTO(
            organization_id=organization_id,
            lead_id=lead_id,
            state=state.value,
            intent=intent,
            buyer_type=buyer_type,
            budget_min=budget_min,
            budget_max=budget_max,
            budget_currency=budget_currency,
            location=location,
            property_type=property_type,
            bedrooms=bedrooms,
            timeline=timeline,
            financing=financing,
            completeness_score=completeness_score,
            confidence_score=confidence_score,
            missing_fields=missing_fields,
            conflicting_fields=conflicting_fields,
            policy_version=policy_version,
            summary_notes=cls._build_summary_notes(state, completeness_score, confidence_score, missing_fields, conflicting_fields),
            generated_at=datetime.now(timezone.utc),
        )

    @classmethod
    def _is_field_known(
        cls,
        field_name: str,
        facts_by_field: Dict[str, QualificationFact],
        extracted_values: Dict[str, Any],
    ) -> bool:
        if field_name in extracted_values:
            val = extracted_values[field_name]
            if val is not None and val != "UNKNOWN" and val != "":
                return True
            return False
        # Generic check on facts
        fact = facts_by_field.get(field_name)
        if not fact or fact.raw_value in (None, "", "UNKNOWN"):
            return False
        return True

    @classmethod
    def _determine_state(
        cls,
        facts_by_field: Dict[str, QualificationFact],
        conflicting_fields: List[str],
        required_missing: List[str],
        missing_fields: List[str],
        completeness_score: float,
        confidence_score: float,
        min_completeness: float,
        min_confidence: float,
        intent: str,
        timeline: str,
    ) -> QualificationState:
        # 1. Human review required if there are open contradictory conflicts
        if conflicting_fields:
            return QualificationState.NEEDS_HUMAN_REVIEW

        # 2. If no active facts exist at all
        if not facts_by_field:
            return QualificationState.NEW

        # 3. Disqualification check (explicit out-of-scope intent, explicit disqualification fact)
        disqualified_fact = facts_by_field.get("disqualified") or facts_by_field.get("disqualification_reason")
        if disqualified_fact and disqualified_fact.raw_value and str(disqualified_fact.raw_value).lower() not in ("false", "no", "none", "unknown"):
            return QualificationState.DISQUALIFIED
        if intent == "DISQUALIFIED":
            return QualificationState.DISQUALIFIED

        if intent == "UNKNOWN" and len(facts_by_field) == 1 and "intent" in facts_by_field:
            # Only unparseable intent present
            return QualificationState.COLLECTING_INFORMATION

        # 4. Nurture check: Long horizon timeline (> 12 months) or exploratory
        if timeline in (QualificationTimeline.MORE_THAN_12_MONTHS.value,):
            return QualificationState.NURTURE

        # 5. Qualified check: ALL required fields known + completeness & confidence meet policy
        if (
            len(required_missing) == 0
            and completeness_score >= min_completeness
            and confidence_score >= min_confidence
            and intent in (QualificationIntent.BUY.value, QualificationIntent.RENT.value, QualificationIntent.INVEST.value, QualificationIntent.SELL.value)
        ):
            return QualificationState.QUALIFIED

        # 6. Partially Qualified: At least one core required field known (e.g. intent or location)
        if len(required_missing) < len(cls.DEFAULT_REQUIRED_FIELDS) or completeness_score >= 0.4:
            return QualificationState.PARTIALLY_QUALIFIED

        # 7. Default active state while information is being gathered
        return QualificationState.COLLECTING_INFORMATION

    @classmethod
    def evaluate_detailed(
        cls,
        organization_id: str,
        lead_id: str,
        active_facts: List[QualificationFact],
        open_conflicts: List[QualificationConflict],
        policy: Optional[QualificationRequirementPolicy] = None,
    ) -> QualificationEvaluationResultDTO:
        """
        Runs deterministic policy evaluation and builds full evaluation DTO with missing information
        and next best qualification question.
        """
        snapshot = cls.evaluate(
            organization_id=organization_id,
            lead_id=lead_id,
            active_facts=active_facts,
            open_conflicts=open_conflicts,
            policy=policy,
        )

        required_fields = policy.required_fields if policy and policy.required_fields else cls.DEFAULT_REQUIRED_FIELDS
        recommended_fields = policy.recommended_fields if policy and policy.recommended_fields else cls.DEFAULT_RECOMMENDED_FIELDS

        missing_required = [rf for rf in required_fields if rf in snapshot.missing_fields]
        missing_recommended = [rf for rf in recommended_fields if rf in snapshot.missing_fields]

        next_q_field = None
        if missing_required:
            next_q_field = missing_required[0]
        elif missing_recommended:
            next_q_field = missing_recommended[0]

        next_q = cls.QUESTION_TEMPLATES.get(next_q_field) if next_q_field else None

        return QualificationEvaluationResultDTO(
            lead_id=lead_id,
            organization_id=organization_id,
            qualification_state=snapshot.state,
            completeness_score=snapshot.completeness_score,
            confidence_score=snapshot.confidence_score,
            policy_version=snapshot.policy_version,
            missing_required_information=missing_required,
            missing_recommended_information=missing_recommended,
            blocking_conflicts=snapshot.conflicting_fields,
            next_best_question_field=next_q_field,
            next_best_question=next_q,
            snapshot=snapshot,
            evaluated_at=snapshot.generated_at,
        )

    @classmethod
    def get_missing_info(
        cls,
        organization_id: str,
        lead_id: str,
        active_facts: List[QualificationFact],
        open_conflicts: List[QualificationConflict],
        policy: Optional[QualificationRequirementPolicy] = None,
    ) -> QualificationMissingInfoDTO:
        """Computes missing qualification fields and question templates."""
        eval_res = cls.evaluate_detailed(
            organization_id=organization_id,
            lead_id=lead_id,
            active_facts=active_facts,
            open_conflicts=open_conflicts,
            policy=policy,
        )
        return QualificationMissingInfoDTO(
            lead_id=lead_id,
            organization_id=organization_id,
            missing_required_fields=eval_res.missing_required_information,
            missing_recommended_fields=eval_res.missing_recommended_information,
            next_best_question_field=eval_res.next_best_question_field,
            next_best_question=eval_res.next_best_question,
            field_questions={
                f: cls.QUESTION_TEMPLATES[f]
                for f in (eval_res.missing_required_information + eval_res.missing_recommended_information)
                if f in cls.QUESTION_TEMPLATES
            },
        )

    @staticmethod
    def _extract_enum(
        fact: Optional[QualificationFact],
        normalizer_fn: Any,
        default_val: str,
    ) -> str:
        if not fact:
            return default_val
        val = fact.normalized_value or fact.raw_value
        if not val or str(val).strip().upper() == "UNKNOWN":
            return default_val
        normalized = normalizer_fn(str(val))
        return normalized.value if hasattr(normalized, "value") else default_val

    @staticmethod
    def _extract_str(fact: Optional[QualificationFact]) -> Optional[str]:
        if not fact:
            return None
        val = fact.normalized_value or fact.raw_value
        if not val or str(val).strip().upper() == "UNKNOWN":
            return None
        if isinstance(val, dict):
            val = val.get("name") or val.get("value") or val.get("currency")
        if not val:
            return None
        return str(val).strip()

    @staticmethod
    def _extract_int(fact: Optional[QualificationFact]) -> Optional[int]:
        if not fact:
            return None
        val = fact.normalized_value if fact.normalized_value is not None else fact.raw_value
        if val is None:
            return None
        if isinstance(val, dict):
            val = val.get("amount") if "amount" in val else val.get("value")
        if val is None:
            return None
        try:
            cleaned = str(val).strip().replace(",", "").replace("_", "")
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _build_summary_notes(
        state: QualificationState,
        completeness: float,
        confidence: float,
        missing: List[str],
        conflicts: List[str],
    ) -> str:
        parts = [f"State: {state.value} (Completeness: {completeness * 100:.0f}%, Confidence: {confidence * 100:.0f}%)"]
        if missing:
            parts.append(f"Missing: {', '.join(missing)}")
        if conflicts:
            parts.append(f"Conflicts: {', '.join(conflicts)}")
        return "; ".join(parts)
