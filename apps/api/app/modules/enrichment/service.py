"""
Volume 2 PART 2 — AI Lead Enrichment Service Orchestrator
=========================================================
Enterprise AI Lead Enrichment Pipeline:
Ingests canonical Lead DTOs -> Normalizers -> Extraction Cascade (Rules -> Regex -> Dict -> LLM) ->
External Provider Lookups -> Classifiers -> Confidence Scoring & Provenance Guard -> DB Sync & Events.
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.lead import Lead
from app.models.enrichment_models import LeadEnrichment, ConfidenceScore, EnrichmentHistory
from app.modules.enrichment.validators.enrichment_validator import EnrichmentValidator
from app.modules.enrichment.normalizers import (
    PhoneNormalizer, CurrencyNormalizer, LocationNormalizer, PropertyNormalizer
)
from app.modules.enrichment.extractors import (
    RegexExtractor, DictionaryExtractor, RuleExtractor, LLMExtractor
)
from app.modules.enrichment.classifiers import (
    IntentClassifier, BudgetClassifier, QualityClassifier
)
from app.modules.enrichment.providers import (
    PhoneLookupProvider, GeoIPProvider, EmailVerifyProvider
)
from app.modules.enrichment.confidence import ScoringEngine, ProvenanceManager
from app.modules.enrichment.events import EventPublisher, LeadEnrichmentStarted, LeadEnriched, LeadEnrichmentFailed
from app.modules.enrichment.monitoring import EnrichmentMetricsCollector

logger = logging.getLogger(__name__)


class LeadEnrichmentService:
    def __init__(self, db: AsyncSession, redis_client: Optional[Any] = None):
        self.db = db
        self.event_publisher = EventPublisher(redis_client)
        self.regex_extractor = RegexExtractor()
        self.dict_extractor = DictionaryExtractor()
        self.rule_extractor = RuleExtractor()
        self.llm_extractor = LLMExtractor()
        
        self.phone_provider = PhoneLookupProvider()
        self.geo_provider = GeoIPProvider()
        self.email_provider = EmailVerifyProvider()

    async def enrich_lead(self, lead_dto: Dict[str, Any], trigger_source: str = "LeadNormalized") -> Dict[str, Any]:
        """
        Main pipeline entry point for Lead Enrichment.
        Accepts canonical lead DTO dictionary and performs end-to-end multi-dimensional enrichment.
        """
        start_time = time.time()
        lead_id = str(lead_dto.get("id"))
        org_id = str(lead_dto.get("organization_id") or lead_dto.get("broker_id") or "default_org")

        logger.info(f"[ENRICHMENT_PIPELINE] Starting enrichment for Lead ID: {lead_id} (Trigger: {trigger_source})")

        # 0. Emit Event: LeadEnrichmentStarted
        await self.event_publisher.publish("lead_events", LeadEnrichmentStarted(
            event_id=str(uuid.uuid4()),
            lead_id=lead_id,
            organization_id=org_id,
            trigger_source=trigger_source
        ))

        # 1. Validation Check
        is_valid, validation_errors = EnrichmentValidator.validate_canonical_input(lead_dto)
        if not is_valid:
            err_msg = f"Canonical lead DTO validation failed: {', '.join(validation_errors)}"
            logger.error(f"[ENRICHMENT_PIPELINE] {err_msg}")
            await self.event_publisher.publish("lead_events", LeadEnrichmentFailed(
                event_id=str(uuid.uuid4()),
                lead_id=lead_id,
                organization_id=org_id,
                error_message=err_msg
            ))
            EnrichmentMetricsCollector.record_enrichment(0.0, 0.0, 0.0, success=False)
            return {"status": "failed", "error": err_msg}

        # Retrieve raw lead fields
        raw_phone = lead_dto.get("phone")
        raw_name = lead_dto.get("name")
        raw_email = lead_dto.get("email")
        raw_notes = " ".join([n.get("content", "") if isinstance(n, dict) else str(n) for n in lead_dto.get("notes", [])]) if isinstance(lead_dto.get("notes"), list) else str(lead_dto.get("notes") or "")
        raw_budget = lead_dto.get("budget_max") or lead_dto.get("budget_min")
        raw_prop_type = lead_dto.get("property_type")
        raw_ip = lead_dto.get("ip_address")

        # 2. Stage 1: Extraction Cascade (Rules -> Regex -> Dictionary -> LLM)
        regex_extracted = self.regex_extractor.extract(raw_notes, lead_dto)
        dict_extracted = self.dict_extractor.extract(raw_notes, lead_dto)
        rule_extracted = self.rule_extractor.extract(raw_notes, {"phone": raw_phone, "country": lead_dto.get("country")})
        
        # Merge preliminary extractions
        combined_extracted = {**rule_extracted, **dict_extracted, **regex_extracted}

        # Execute LLM Extractor only if key intent/budget parameters remain missing
        llm_extracted = {}
        if not combined_extracted.get("budget_raw") and not combined_extracted.get("bedrooms") and raw_notes and len(raw_notes) > 10:
            logger.info(f"[ENRICHMENT_PIPELINE] Calling LLM Extractor for unstructured notes on Lead: {lead_id}")
            llm_extracted = self.llm_extractor.extract(raw_notes, lead_dto)

        ai_token_cost = llm_extracted.get("token_cost", 0.0)

        # 3. Stage 2: Normalizers
        phone_norm = PhoneNormalizer.normalize(raw_phone)
        currency_input = combined_extracted.get("budget_raw") or raw_budget
        currency_norm = CurrencyNormalizer.normalize(currency_input, default_currency=combined_extracted.get("default_currency", "AED"))
        
        target_city = combined_extracted.get("city") or lead_dto.get("city")
        target_country = phone_norm.get("country") or rule_extracted.get("country") or lead_dto.get("country")
        location_norm = LocationNormalizer.normalize(city=target_city, country=target_country, raw_location=raw_notes)
        
        property_norm = PropertyNormalizer.normalize(property_type_raw=raw_prop_type or llm_extracted.get("property_type"), bedrooms_raw=combined_extracted.get("bedrooms") or llm_extracted.get("bedrooms"), notes=raw_notes)

        # 4. Stage 3: External Provider Lookups
        phone_prov_res = await self.phone_provider.lookup(raw_phone or "")
        EnrichmentMetricsCollector.record_provider_call(success=phone_prov_res["success"])

        email_prov_res = await self.email_provider.lookup(raw_email or "")
        EnrichmentMetricsCollector.record_provider_call(success=email_prov_res["success"])

        geo_prov_res = await self.geo_provider.lookup(raw_ip or "")
        EnrichmentMetricsCollector.record_provider_call(success=geo_prov_res["success"])

        # 5. Stage 4: Classifiers
        intent_classified = IntentClassifier.classify(combined_extracted, raw_notes)
        budget_classified = BudgetClassifier.classify(currency_norm.get("amount_aed"), property_norm.get("property_type"))

        # Build Multi-dimensional Profiles
        identity_profile = {
            "full_name": raw_name or llm_extracted.get("full_name"),
            "email": raw_email,
            "phone": phone_norm["e164"],
            "country": location_norm["country"],
            "state": location_norm["state"],
            "city": location_norm["city"],
            "timezone": location_norm["timezone"] or phone_norm["timezone"],
            "language": dict_extracted.get("language") or rule_extracted.get("language") or "English",
            "nationality": combined_extracted.get("nationality"),
            "occupation": dict_extracted.get("occupation") or llm_extracted.get("occupation"),
            "company": email_prov_res["data"].get("company") or llm_extracted.get("company"),
            "income_range": combined_extracted.get("income_range")
        }

        location_profile = {
            "country": location_norm["country"],
            "state": location_norm["state"],
            "city": location_norm["city"],
            "iso2": location_norm["iso2"] or phone_norm["iso2"],
            "timezone": location_norm["timezone"] or phone_norm["timezone"],
            "preferred_locations": location_norm["preferred_areas"] or combined_extracted.get("preferred_locations", [])
        }

        financial_profile = {
            "raw_budget": currency_norm["raw"],
            "amount_canonical_aed": currency_norm["amount_aed"],
            "amount_canonical_usd": currency_norm["amount_usd"],
            "currency": currency_norm["currency"],
            "budget_tier": budget_classified["budget_tier"],
            "is_realistic": budget_classified["is_realistic"],
            "financing_required": combined_extracted.get("financing_required", False),
            "mortgage_interest": combined_extracted.get("mortgage_interest", False)
        }

        intent_profile = {
            "purpose": intent_classified["purpose"],
            "timeline": intent_classified["timeline"],
            "urgency": intent_classified["urgency"],
            "intent_score": intent_classified["intent_score"],
            "loan_status": combined_extracted.get("loan_status", "not_started")
        }

        property_interest = {
            "property_type": property_norm["property_type"],
            "bedrooms": property_norm["bedrooms"],
            "bathrooms": property_norm["bathrooms"],
            "preferred_locations": location_norm["preferred_areas"]
        }

        communication_profile = {
            "preferred_channel": lead_dto.get("source", "whatsapp"),
            "preferred_contact_time": "morning",
            "language": identity_profile["language"],
            "referral_source": lead_dto.get("source", "direct")
        }

        # 6. AI Summary & Recommendations Synthesis
        ai_summary = llm_extracted.get("ai_summary") or f"Lead interested in {property_interest['property_type'] or 'property'} in {location_profile['city'] or 'Dubai'} with a budget of {financial_profile['amount_canonical_aed'] or 'undisclosed'} AED."
        ai_recommendations = llm_extracted.get("ai_recommendations") or [
            f"Contact lead via {communication_profile['preferred_channel']} to confirm budget and location requirements.",
            f"Share relevant {property_interest['property_type'] or 'residential'} brochures in {location_profile['city'] or 'Dubai'}."
        ]

        # 7. Quality Classification & Confidence Calculation
        field_completion_rate = ScoringEngine.calculate_field_completion({
            **identity_profile, **financial_profile, **intent_profile, **property_interest
        })

        quality_classified = QualityClassifier.evaluate(
            has_phone=bool(identity_profile["phone"]),
            has_email=bool(identity_profile["email"]),
            budget_aed=financial_profile["amount_canonical_aed"],
            timeline=intent_profile["timeline"],
            urgency=intent_profile["urgency"],
            property_type=property_interest["property_type"],
            intent_score=intent_profile["intent_score"],
            field_completion_rate=field_completion_rate
        )

        overall_confidence = ScoringEngine.calculate_overall_confidence([
            phone_norm["confidence"],
            currency_norm["confidence"],
            location_norm["confidence"],
            property_norm["confidence"],
            intent_classified["confidence"]
        ])

        # 8. Provenance & Field Confidence Scores
        # Check existing lead enrichment record if any
        stmt = select(LeadEnrichment).where(LeadEnrichment.lead_id == lead_id)
        res = await self.db.execute(stmt)
        existing_enrichment = res.scalar_one_or_none()

        fields_to_track = [
            ("phone", identity_profile["phone"], "verified" if phone_prov_res["success"] else "observed", phone_norm["confidence"], "PhoneNormalizer"),
            ("email", identity_profile["email"], "observed" if raw_email else "inferred", 0.95 if raw_email else 0.0, "Input"),
            ("budget_canonical_aed", financial_profile["amount_canonical_aed"], "observed" if raw_budget else "inferred", currency_norm["confidence"], "CurrencyNormalizer"),
            ("city", location_profile["city"], "observed" if lead_dto.get("city") else "inferred", location_norm["confidence"], "LocationNormalizer"),
            ("property_type", property_interest["property_type"], "observed" if raw_prop_type else "inferred", property_norm["confidence"], "PropertyNormalizer"),
            ("purpose", intent_profile["purpose"], "inferred", intent_classified["confidence"], "IntentClassifier"),
        ]

        for fname, fval, stype, conf, method in fields_to_track:
            # Check existing confidence score in DB
            c_stmt = select(ConfidenceScore).where(ConfidenceScore.lead_id == lead_id, ConfidenceScore.field_name == fname)
            c_res = await self.db.execute(c_stmt)
            existing_c = c_res.scalar_one_or_none()

            old_stype = existing_c.source_type if existing_c else None
            old_conf = existing_c.confidence if existing_c else 0.0

            should_upd, reason = ProvenanceManager.should_update_field(old_stype, old_conf, stype, conf)
            if should_upd:
                if existing_c:
                    existing_c.field_value = str(fval) if fval is not None else None
                    existing_c.confidence = conf
                    existing_c.source_type = stype
                    existing_c.method = method
                else:
                    self.db.add(ConfidenceScore(
                        lead_id=lead_id,
                        organization_id=org_id,
                        field_name=fname,
                        field_value=str(fval) if fval is not None else None,
                        confidence=conf,
                        source_type=stype,
                        method=method
                    ))

        # 9. Save or Update LeadEnrichment
        if existing_enrichment:
            existing_enrichment.identity_profile = identity_profile
            existing_enrichment.location_profile = location_profile
            existing_enrichment.financial_profile = financial_profile
            existing_enrichment.intent_profile = intent_profile
            existing_enrichment.property_interest = property_interest
            existing_enrichment.communication_profile = communication_profile
            existing_enrichment.overall_quality_score = quality_classified["overall_quality_score"]
            existing_enrichment.quality_tier = quality_classified["quality_tier"]
            existing_enrichment.overall_confidence = overall_confidence
            existing_enrichment.field_completion_rate = field_completion_rate
            existing_enrichment.ai_summary = ai_summary
            existing_enrichment.ai_recommendations = ai_recommendations
            existing_enrichment.status = "completed"
            enrichment_obj = existing_enrichment
        else:
            enrichment_obj = LeadEnrichment(
                lead_id=lead_id,
                organization_id=org_id,
                identity_profile=identity_profile,
                location_profile=location_profile,
                financial_profile=financial_profile,
                intent_profile=intent_profile,
                property_interest=property_interest,
                communication_profile=communication_profile,
                overall_quality_score=quality_classified["overall_quality_score"],
                quality_tier=quality_classified["quality_tier"],
                overall_confidence=overall_confidence,
                field_completion_rate=field_completion_rate,
                ai_summary=ai_summary,
                ai_recommendations=ai_recommendations,
                status="completed"
            )
            self.db.add(enrichment_obj)

        # 10. Also update core Lead entity score & property_type if unassigned
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
        lead_stmt = select(Lead).where(Lead.id == lead_uuid)
        lead_res = await self.db.execute(lead_stmt)
        lead_record = lead_res.scalar_one_or_none()
        if lead_record:
            lead_record.score = quality_classified["quality_tier"]
            lead_record.score_confidence = overall_confidence
            if not lead_record.property_type and property_interest["property_type"]:
                lead_record.property_type = property_interest["property_type"]

        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        # 11. Record EnrichmentHistory
        history_record = EnrichmentHistory(
            lead_id=lead_id,
            organization_id=org_id,
            trigger_event=trigger_source,
            fields_modified=["identity_profile", "location_profile", "financial_profile", "intent_profile"],
            previous_values={},
            new_values={"quality_tier": quality_classified["quality_tier"], "quality_score": quality_classified["overall_quality_score"]},
            execution_time_ms=execution_time_ms,
            ai_token_cost=ai_token_cost,
            status="success"
        )
        self.db.add(history_record)

        await self.db.commit()

        # 12. Emit Event & Record Monitoring Metrics
        await self.event_publisher.publish("lead_events", LeadEnriched(
            event_id=str(uuid.uuid4()),
            lead_id=lead_id,
            organization_id=org_id,
            quality_tier=quality_classified["quality_tier"],
            quality_score=quality_classified["overall_quality_score"],
            overall_confidence=overall_confidence,
            field_completion_rate=field_completion_rate,
            execution_time_ms=execution_time_ms
        ))

        EnrichmentMetricsCollector.record_enrichment(
            latency_ms=execution_time_ms,
            confidence=overall_confidence,
            completion_rate=field_completion_rate,
            ai_cost=ai_token_cost,
            success=True
        )

        logger.info(f"[ENRICHMENT_PIPELINE] Completed enrichment for Lead {lead_id} in {execution_time_ms}ms. Tier: {quality_classified['quality_tier']}, Score: {quality_classified['overall_quality_score']}")

        return {
            "status": "completed",
            "lead_id": lead_id,
            "quality_tier": quality_classified["quality_tier"],
            "quality_score": quality_classified["overall_quality_score"],
            "overall_confidence": overall_confidence,
            "field_completion_rate": field_completion_rate,
            "execution_time_ms": execution_time_ms,
            "identity_profile": identity_profile,
            "location_profile": location_profile,
            "financial_profile": financial_profile,
            "intent_profile": intent_profile,
            "property_interest": property_interest,
            "communication_profile": communication_profile,
            "ai_summary": ai_summary,
            "ai_recommendations": ai_recommendations
        }
