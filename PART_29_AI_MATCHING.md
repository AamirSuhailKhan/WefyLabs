# PART 29 — PRODUCTION AI LEAD ↔ PROPERTY MATCHING ENGINE
## Production-Grade / Multi-Tenant / Explainable AI / Zero-Hallucination Architecture

---

## 1. Architecture Overview

Part 29 delivers an explainable, bidirectional AI Lead ↔ Property Matching Engine natively integrated into the existing Next.js 15 App Router frontend and FastAPI / SQLAlchemy backend.

### Architectural Principle: Zero Hallucinated CRM Facts
Authoritative database facts are never determined or invented by AI:
- **Property Price, BHK, Area, Locality, Status, Availability:** Verified from PostgreSQL `property_listings` table.
- **Lead Budget, Preferred Localities, Timeline, Target BHK:** Sourced from CRM `leads` and `prospect_intelligence` records.
- **Tenant/Org Access & Resource Ownership:** Enforced at database layer through strict `broker_id` / `organization_id` scoping and RBAC filters.
- **AI Layer Responsibility:** Natural language preference extraction, text normalization, and grounded contextual summaries using *only* verified database attributes.

```
+-------------------------------------------------------------------------------+
|                             CRM DATABASE TRUTH                                |
|   Leads, Property Listings, Prospect Intelligence, Lead Property Interests   |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                       REQUIREMENT NORMALIZATION                               |
|   - Indian pricing language: 1.2 Cr, 80L, 120 lakh, 45k -> Canonical INR     |
|   - Area normalization: sqft, sqm, acre, cent -> Canonical sqft              |
|   - Negative preferences: 'No ground floor', 'avoid Sarjapur', 'unfurnished'  |
|   - Field-level provenance tracking: EXPLICIT vs AI_INFERRED                  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                       HARD CONSTRAINT FILTERING                               |
|   - Availability (available / active only; sold / reserved excluded)          |
|   - Transaction category (Buy vs Rent compatibility)                         |
|   - Property type group matching (apartment vs villa vs commercial vs land)  |
|   - Budget ceiling (+10% strict tolerance; +25% in controlled alternative)    |
|   - Minimum BHK / Bedroom threshold                                           |
|   - Negative exclusions: Locality avoidance, floor avoidance, parking mandate |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                       SOFT PREFERENCE SCORING (0-100)                         |
|   Configurable 8-Dimensional Compatibility Model:                            |
|   - Budget Fit (25%)                                                          |
|   - Location Fit (25%)                                                        |
|   - Property Type Fit (15%)                                                   |
|   - Bedrooms / BHK Fit (10%)                                                  |
|   - Area Size Fit (10%)                                                       |
|   - Amenities & Parking Fit (10%)                                             |
|   - Possession / Timeline Fit (5%)                                            |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                  CONFIDENCE & EXPLAINABILITY ENGINE                           |
|   - Match Score separated from Data Completeness Confidence (0.0 - 1.0)       |
|   - Grounded why_matches and trade_offs facts                                 |
|   - Dynamic clarification questions for incomplete lead profiles              |
|   - Deterministic template fallback when Gemini AI is disabled/offline        |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                     CRM LIFECYCLE ACTION ORCHESTRATION                        |
|   - Shortlist -> Upsert LeadPropertyInterest (SHORTLISTED)                    |
|   - Recommend -> Upsert LeadPropertyInterest (MATCHED) + Create Follow-up Task|
|   - Feedback -> Record Broker Feedback & AuditLog                             |
|   - Compare -> Side-by-side comparison matrix (up to 5 properties)            |
+-------------------------------------------------------------------------------+
```

---

## 2. Database & Migrations

- **Migration Head:** `0022_ai_matching_engine`
- **Alembic Status:** Single-head state maintained.
- **Models & Tables Integrated:**
  - `PropertyListing` (`property_listings`): Inventory master with strict nullability, indexes on `broker_id`, `status`, `property_type`, `price`, `locality`.
  - `Lead` (`leads`): Primary lead entity with budget min/max, preferred locations, property type, notes.
  - `LeadPropertyInterest` (`lead_property_interests`): Canonical relationship record tracking interest level, match scores, deterministic scores, confidence, and audit trail.
  - `Task` (`tasks`): Automated follow-up task generation upon property recommendation.
  - `Activity` (`activities`): Timeline audit events for property shortlisting and recommendations.
  - `AuditLog` (`audit_logs`): Immutable compliance log for matching actions (`match.shortlist`, `match.recommend`, `match.feedback`).

---

## 3. Requirement Normalization & Parsing

Located in `app.modules.property_recommendation.requirement_normalizer`:
1. **Indian Currency Parser (`parse_indian_budget`):**
   - Handles `1 crore`, `1.2 crore`, `₹1.2 Cr`, `1.2 cr`, `120 lakh`, `1.2L`, `₹80 lakhs`, `80L`, `45k`, `50 thousand`, and raw numeric strings.
   - Normalizes to canonical floating-point amounts in `INR`.
2. **Area Normalization (`normalize_area_value`):**
   - Converts `sqft`, `sq ft`, `square feet`, `sqm` (multiplier 10.7639), `acre` (43,560 sqft), `cent` (435.6 sqft), and `guntha` (1,089 sqft).
3. **Negative Preference Extraction (`extract_negative_preferences`):**
   - Detects negative constraints: ground floor exclusion, unfurnished avoidance, mandatory parking requirements, excluded localities ("strictly avoid Sarjapur"), and hard budget caps ("must be under 1.5 crore").
4. **Clarification Question Generator (`generate_clarification_questions`):**
   - Identifies missing critical parameters and suggests natural clarification questions to the agent.

---

## 4. Matching Service Engine

Located in `app.modules.property_recommendation.matching_service.AIPropertyMatchingEngine`:
- **Dual Directionality:**
  - **Lead -> Properties (`match_properties_for_lead`):** Identifies top matching properties for a lead, supporting filters (`availability`, `property_type`, `location`, `transaction_type`, `minimum_score`), pagination (`limit`, `offset`), sorting (`score_desc`, `score_asc`, `price_asc`, `price_desc`), and controlled alternative relaxation (`allow_alternatives`).
  - **Property -> Leads (`match_leads_for_property`):** Reverse matching identifying qualified buyers in the CRM for new or existing inventory.
- **Side-by-Side Comparison (`compare_properties`):** Generates comparative matrix across up to 5 properties with grounded match scores against an optional lead profile.
- **Match Feedback (`record_match_feedback`):** Stores agent feedback (`good_match`, `bad_match`, `wrong_budget`, `wrong_location`, `reject`, `shortlist`) and updates interest status.
- **Requirement Extraction (`extract_requirements_from_text`):** Parses raw conversation or notes text with prompt injection defense and provenance tracking.

---

## 5. Copilot Tool Registry

All 11 matching tools are registered in `COPILOT_TOOL_REGISTRY` in `app/modules/copilot/tools/tool_registry.py`:
1. `find_matching_properties`: Finds and ranks best property candidates for a lead.
2. `get_property_matches`: Retrieves ranked property matches.
3. `find_matching_leads`: Reverse matching finding qualified buyer leads for a property.
4. `get_match_explanation`: Explains why a property matches using grounded database facts.
5. `compare_matched_properties`: Compares 2 to 5 matched properties side-by-side.
6. `shortlist_property_for_lead`: Shortlists a property for a lead.
7. `remove_property_from_shortlist`: Removes a property from shortlist.
8. `record_match_feedback`: Records broker or client feedback on a match.
9. `get_match_score_breakdown`: Retrieves granular 8-dimensional scores.
10. `suggest_alternatives`: Finds alternative properties with relaxed soft preferences.
11. `improve_lead_requirements`: Generates targeted clarification questions for incomplete leads.

---

## 6. Frontend Experiences

1. **Matching Dashboard (`/dashboard/matching`):**
   - Dual tabs: "Lead -> Properties" and "Property -> Leads".
   - Search, filter by property type, location, min score, and alternative relaxation toggle.
   - Grounded score badges, confidence indicators, reasons, and trade-offs.
   - Quick CTAs: View, Shortlist, Compare, Schedule Visit.
2. **Lead Details Page (`/leads/[id]`):**
   - Dedicated "Recommended Properties" tab with real-time match cards.
   - Immediate shortlisting and visit scheduling workflows.
3. **Property Inventory Page (`/dashboard/properties`):**
   - "Matching Leads" panel on property drawer displaying reverse-matched buyer leads.

---

## 7. Security & Compliance Invariants

- **Multi-Tenant Isolation:** Every query enforces `PropertyListing.broker_id == broker.id` and `Lead.broker_id == broker.id`.
- **IDOR Protection:** Access to foreign tenant leads or properties is denied with 404 / 403.
- **Prompt Injection Defense:** Untrusted text in lead notes, property descriptions, or requirement extraction is treated strictly as data; instruction override strings (`ignore all previous instructions`) are sanitized and disregarded.
- **PII & Secret Protection:** Credentials, tokens, and passwords are never included in normalization or sent to external LLMs.
- **WhatsApp Disabled:** WhatsApp integrations remain disabled per explicit instruction.
- **Razorpay Test Mode:** Live payments remain strictly disabled.

---

## 8. Verification & Test Metrics

- **Unit Tests:** 34 / 34 PASSED
- **Integration Tests:** 18 / 18 PASSED
- **Security Tests:** 12 / 12 PASSED
- **API Tests:** 17 / 17 PASSED
- **Copilot Tests:** 12 / 12 PASSED
- **True Database E2E Test:** 1 / 1 PASSED
- **Part 27 Follow-Up Automation Regression:** 12 / 12 PASSED
- **Part 28 Property Inventory Regression:** 17 / 17 PASSED
- **Total Part 29 Test Suite:** 108 / 108 PASSED (0 failures)
- **Frontend TypeScript (`tsc --noEmit`):** CLEAN (0 errors)
- **Frontend Production Build (`next build`):** CLEAN (33/33 pages compiled)
- **Alembic Single-Head Status:** Verified (`0022_ai_matching_engine`)
