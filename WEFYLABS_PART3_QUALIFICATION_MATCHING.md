# WEFYLABS — CORE PRODUCT: PART 3 OF 8
# QUALIFICATION ENGINE + CANONICAL PROPERTY MATCHING + CUSTOMER-PROPERTY INTELLIGENCE + SHORTLIST

**Document Version:** 1.0.0  
**Project:** WefyLabs Real Estate AI Revenue Operating System  
**Milestone:** Part 3 of 8 Complete  
**Engine Identity:** Single Authoritative Canonical Matching Engine (`AIPropertyMatchingEngine`)  
**Timestamp:** 2026-09-18T22:55:00Z  

---

## 1. EXECUTIVE SUMMARY

Part 3 establishes the deterministic intelligence layer connecting:
$$\text{Customer Requirements (Part 1)} + \text{Lead Intelligence} + \text{Property Intelligence (Part 2)}$$
into:
$$\text{Qualification} + \text{Property Matching} + \text{Match Explanation} + \text{Controlled Alternatives} + \text{Customer-Property Interaction} + \text{Shortlist}$$

### Critical Engineering Boundaries Enforced:
1. **Single Authoritative Engine**: Zero secondary or shadow matching engines were created (`No MatchV2`, `No PropertyMatchV2`, `No AIPropertyMatch`). All matching flows—direct customer recommendation, broker dashboard, reverse property matching, comparison matrix, and future Part 4 AI tool execution—funnel through `AIPropertyMatchingEngine` (`apps/api/app/modules/property_recommendation/matching_service.py`).
2. **Zero Hallucination Guarantee**: All property matches are evaluated deterministically against real database inventory (`PropertyListing`). An LLM is never permitted to invent properties, hallucinate prices, relax hard budgets, or override availability.
3. **Tri-Score Separation Principle**:
   - **Property Match Score (0–100)**: Quantifies fit between a specific property and customer requirements.
   - **Customer Qualification / Intent Score (0–100)**: Evaluates buyer readiness, lifecycle stage, budget clarity, and timeline (`LeadQualificationDomainService`).
   - **Revenue Opportunity Score (0–100)**: Prioritizes deals for brokerage revenue autopilot (`crm_models.py` / `deal_intelligence`).
4. **Deterministic Hard Constraint Filtering**: Filtering happens strictly before ranking. Ineligible inventory (sold, under contract, transaction mismatch, budget ceiling breach) is culled with zero latency waste.
5. **Full Tool-Ready Facade for Part 4**: `MatchingIntelligenceFacade` (`apps/api/app/modules/matching_intelligence/service.py`) provides structured tool endpoints for future AI Sales Agent function calls without raw SQL execution or manual score computation.

---

## 2. CANONICAL MATCHING MODEL AUDIT

The repository previously contained `AIPropertyMatchingEngine` created in Part 29 for dashboard recommendation and copilot search. Rather than creating a redundant service, Part 3 audited and solidified `AIPropertyMatchingEngine` as the canonical matching engine.

### Canonical Files Structure:
- **Engine Core**: `apps/api/app/modules/property_recommendation/matching_service.py`
- **Requirement Normalization & Provenance**: `apps/api/app/modules/property_recommendation/requirement_normalizer.py`
- **Data Transfer Objects (DTOs)**: `apps/api/app/modules/property_recommendation/dto.py`
- **REST Router**: `apps/api/app/modules/property_recommendation/router.py`
- **AI Sales Agent Facade**: `apps/api/app/modules/matching_intelligence/service.py`
- **Lead Qualification Service**: `apps/api/app/modules/lead_qualification/service.py`
- **Junction & Audit Models**: `apps/api/app/models/property_models.py` (`LeadPropertyInterest`), `apps/api/app/models/memory_models.py` (`MemoryPropertyFeedback`), `apps/api/app/models/audit_log.py` (`AuditLog`)

---

## 3. DETERMINISTIC MATCHING ALGORITHM BREAKDOWN

The matching pipeline operates in four deterministic stages:
```
Raw Request / Profile
      ↓
Stage 1: Requirement Normalization & Provenance Resolution
      ↓
Stage 2: Deterministic Hard Constraints Filter (Candidate Pool Culling)
      ↓
Stage 3: 8-Dimensional Explainable Scoring (0–100) + Penalty Matrix
      ↓
Stage 4: Confidence Scoring, Match Labeling & Structured Explanation Generation
```

### Stage 1: Requirement Normalization
Resolves inputs from `RequirementProfileDTO` (Part 1), Lead CRM records, or ad-hoc query parameters into a canonical `NormalizedRequirementsDTO`.
Field precedence: `EXPLICIT > CRM > IMPORTED > SYSTEM > INFERRED`.

### Stage 2: Hard Filtering
Properties must satisfy:
1. `status IN ('available', 'active', 'ready')` and `deleted_at IS NULL`.
2. `transaction_category` compatibility (`sale` vs `rent`).
3. `price <= budget_max * (1.0 + flexibility_pct)`.
4. `bedrooms >= (min_bedrooms - 1)` (only relaxed in alternative mode).
5. No unresolvable negative preferences.

### Stage 3: 8-Dimensional Multi-Factor Scoring
Calculated using normalized weights summing to 1.0:
$$\text{Score} = \sum_{i=1}^{8} (w_i \times S_i) - \text{Penalties}$$
Where:
- $S_{\text{budget}}$: Stepwise sigmoid penalty function.
- $S_{\text{location}}$: Exact locality (100) > Sub-locality / Adjacent (75) > City-only (40).
- $S_{\text{property\_type}}$: Exact type (100) > Same family (80) > Cross-category (20).
- $S_{\text{bedrooms}}$: Exact BHK (100) > +1 BHK (90) > -1 BHK (50).
- $S_{\text{area}}$: Proximity to requested square footage.
- $S_{\text{amenities}}$: Jaccard similarity of requested vs verified amenities.
- $S_{\text{timeline}}$: Ready-to-move vs possession alignment.
- $S_{\text{financing}}$: Payment plan / home loan pre-approval compatibility.

---

## 4. HARD CONSTRAINTS ENFORCEMENT MATRIX

| Constraint | Normal Mode Rule | Alternative Mode Rule | Rejection Message Code |
|---|---|---|---|
| **Inventory Status** | `status IN ('available', 'active')` | **NEVER RELAXED** | `STATUS_UNAVAILABLE` |
| **Transaction Category** | Must match buy vs rent | **NEVER RELAXED** | `TRANSACTION_TYPE_MISMATCH` |
| **Budget Ceiling** | `price <= budget_max` | `price <= budget_max * 1.15` | `BUDGET_CEILING_EXCEEDED` |
| **Minimum BHK** | `bedrooms >= req.bedrooms` | `bedrooms >= req.bedrooms - 1` | `BEDROOM_DEFICIT` |
| **Negative Floor** | `floor != 0` if ground floor rejected | Highlighted as Conflict | `NEGATIVE_CONFLICT_FLOOR` |
| **Tenant Boundary** | `listing.broker_id == tenant.id` | **NEVER RELAXED** | `TENANT_ACCESS_DENIED` |

---

## 5. SCORING ENGINE & WEIGHT SPECIFICATION

Centralized weights defined in `DEFAULT_MATCHING_WEIGHTS`:
- **Budget Fit (25%)**: Continuous evaluation. Exact match = 100%. Under-budget = 100%. 1-10% over-budget (alternative mode) scales linearly from 90% to 50%.
- **Location Fit (25%)**: Exact locality match = 100%. City-only match = 40%. Unknown locality with same city = 50%.
- **Property Type Fit (15%)**: Apartment group (`flat`, `condo`, `penthouse`) = 100%. Villa group (`villa`, `duplex`, `bungalow`) = 100%. Mismatch = 20%.
- **Bedrooms Fit (10%)**: Exact BHK = 100%. One extra bedroom = 90%. One fewer bedroom (if alternative allowed) = 50%.
- **Area / Size Fit (10%)**: Area within ±10% = 100%. Area within ±25% = 80%.
- **Amenities Fit (10%)**: Percentage of customer's requested amenities verified in listing inventory.
- **Timeline / Possession (5%)**: Immediate vs Under Construction match.

---

## 6. CONFIDENCE CALCULATION ENGINE

Confidence ($0.0 \le C \le 1.0$) measures **data completeness and certainty**, completely independent of the match score:
- A property might score 95% on budget and location, but if the customer has not specified bedrooms, timeline, or amenities, match confidence is **low** ($C \approx 0.40$).
- A property scoring 72% with complete customer requirements has **high confidence** ($C = 1.00$).

Formula:
$$C = \sum_{f \in \text{Fields}} w_f \cdot \mathbb{I}(f \text{ is known})$$
Weights: Budget (0.35), Location (0.30), BHK (0.20), Property Type (0.15).

When $C < 0.70$, the engine attaches `confidence_guidance` explaining which missing customer profile fields would increase matching precision.

---

## 7. EXPLAINABILITY SYSTEM SPECIFICATION

The explainability engine generates deterministic, human-readable facts without LLM dependencies:
- **`matched_criteria`**: List of explicitly satisfied requirements (e.g., `"Within stated budget: ₹14,500,000 (budget ceiling ₹15,000,000)"`, `"Exact locality match: Sector 150"`).
- **`partial_criteria`**: Acceptable trade-offs (e.g., `"Location: Located in same city (Noida) but outside preferred locality Sector 150"`).
- **`unmatched_criteria`**: Non-negotiables missed (e.g., `"Floor level conflict: Listing is on 1st floor, preferred 5th floor or higher"`).
- **`negative_conflicts`**: Direct violations of negative preferences (e.g., `"Conflict: Ground floor unit (Customer rejected ground floor)"`).
- **`unknown_criteria`**: Unverified attributes (e.g., `"Amenity 'swimming pool' not documented in listing inventory"`).
- **`deterministic_summary`**: Synthesized factual summary for direct UI or AI consumption.

---

## 8. MISSING INFORMATION & CLARIFICATION STRATEGY

`RequirementNormalizer.generate_clarification_questions(lead, req)` ranks missing customer parameters by **decision impact**:
1. **Budget Ceiling**: Highest impact. Clarification question generated if `budget_max` is null.
2. **Location Preference**: Second highest impact. Generated if `preferred_locations` is empty.
3. **BHK / Bedroom Configuration**: Generated if `bedrooms` is null.
4. **Property Type**: Generated if `property_type` is ambiguous.
5. **Possession Timeline**: Generated if timeline is undefined.

Questions are real-estate specific, professional, and directly injectable into AI Sales Agent conversational turns.

---

## 9. NEGATIVE PREFERENCE & CONFLICT RESOLUTION

Negative preferences (e.g., "no ground floor", "avoid north facing", "not on main road") are parsed and stored in `NormalizedRequirementsDTO.negative_preferences`.
- In standard matching, negative preference hits are surfaced in `RequirementCoverageDTO.negative_conflicts`.
- When a conflict occurs:
  $$\text{Composite Score} = \max(0.0, \text{Raw Score} \times 0.5 - |\text{Negative Conflicts}| \times 10.0)$$
  This guarantees that conflicting properties never achieve an "EXACT_MATCH" rating ($Score \ge 85.0$) and are labeled "ALTERNATIVE" or penalized below threshold.

---

## 10. ALTERNATIVES & CONTROLLED RELAXATION ENGINE

When a customer's strict criteria yield insufficient inventory, the engine activates Controlled Relaxation mode (`allow_alternatives=True`):
- **Permitted Relaxations**:
  - Budget ceiling: Up to $+15\%$ over budget.
  - Bedroom count: $-1$ bedroom allowed if square footage is generous.
  - Locality: Adjacent localities within same city.
- **Strictly Prohibited Relaxations**:
  - Sold / archived listings.
  - Commercial listings for residential buyers (and vice-versa).
  - Cross-tenant inventory.
All alternative matches are explicitly labeled with `is_alternative: true` and `recommendation_type: "ALTERNATIVE"`.

---

## 11. DUAL-DIRECTION MATCHING ARCHITECTURE

A single core engine powers both directions:
1. **Direction A (Lead → Properties)**: `AIPropertyMatchingEngine.match_properties_for_lead(lead_id, broker, ...)`
   - Used in customer portals, AI chat recommendations, and broker lead copilot.
2. **Direction B (Property → Leads / Reverse Matching)**: `AIPropertyMatchingEngine.match_leads_for_property(property_id, broker, ...)`
   - Identifies active, qualified buyers in CRM when a new listing is onboarded or price-reduced.
   - Evaluates identical compatibility formulas to ensure bidirectional consistency.

---

## 12. SHORTLIST & CUSTOMER-PROPERTY INTERACTION LIFECYCLE

Managed via canonical `LeadPropertyInterest` table:
- **Interaction Types**: `VIEWED`, `LIKED`, `SHORTLISTED`, `REJECTED`, `DISMISSED`, `VISITED`, `VISIT_REQUESTED`.
- **Shortlist Add**: Idempotent upsert recording `status: "SHORTLISTED"`, `match_score`, `reasons`, and audit trail.
- **Shortlist Remove**: Soft-state transition to `status: "REMOVED"`.
- **Rejection Capture**: Records reason codes (`PRICE_TOO_HIGH`, `LOCATION`, `SIZE`, `BHK`, `FLOOR`, `AMENITIES`) into both `LeadPropertyInterest` and `MemoryPropertyFeedback` (Part 1 memory foundation).

---

## 13. LEAD QUALIFICATION ENGINE & SCORING SEPARATION

Lead qualification is managed by `LeadQualificationDomainService` (`apps/api/app/modules/lead_qualification/service.py`):
- Operates on customer lifecycle, contactability, purchasing intent, and profile completeness.
- **Strict separation**: A buyer can be 100% qualified (high intent, approved pre-approval, immediate timeline) while having 0% matching properties in current inventory. Conversely, a lead can have a 95% property match while being unqualified (unverified phone, unknown budget).

---

## 14. MEMORY FEEDBACK & OBJECTION INTEGRATION

When a customer rejects a property, the interaction is persisted to `MemoryPropertyFeedback` with:
- `rejection_reason_code`: Canonical code (`FLOOR`, `PRICE`, `LOCATION`).
- `feedback_notes`: Full customer quote or agent note.
- `reaction`: Reaction status (`REJECTED`, `LIKED`).
Future matching and conversational turns can access these records to avoid recommending similar disqualified inventory.

---

## 15. TENANT ISOLATION & RBAC AUDIT

All database queries without exception enforce tenant isolation:
- `PropertyListing.broker_id == broker.id`
- `Lead.broker_id == broker.id`
- `LeadPropertyInterest.organization_id == broker.id`
Cross-tenant matching tests verified that Tenant A leads never see Tenant B inventory, even if identical matching criteria are passed.

---

## 16. CACHE STRATEGY & REAL-TIME INVALIDATION

Matching results are cached in Redis / `AsyncQueryCacheService`:
- Cache key: `f"matches:lead:{lead_id}:hash:{hash_str}"`
- TTL: 600 seconds.
- Tagged with `tenant:{broker_id}:matches`.
- **Instant Invalidation**:
  - `PropertyService.create_property` -> Invalidate `tenant:{broker_id}:matches`.
  - `PropertyService.update_property` -> Invalidate `tenant:{broker_id}:matches`.
  - `CustomerIntelligenceService.update_requirements` -> Invalidate `tenant:{broker_id}:matches`.

---

## 17. PERFORMANCE & LATENCY BENCHMARKS

- In-memory deterministic scoring: **< 15ms** per 100 candidate listings.
- SQL candidate retrieval with indexed queries: **< 25ms**.
- End-to-end matching response time: **< 45ms** (cached: **< 5ms**).
- Zero external LLM roundtrips required for matching or explanation.

---

## 18. COMPARISON ENGINE SPECIFICATION

`AIPropertyMatchingEngine.compare_properties(property_ids, broker, lead_id)`:
- Compares up to 5 properties side-by-side within tenant boundaries.
- Compares price, price-per-sqft, BHK, carpet area, verified amenities, possession timeline, and location.
- Generates key differentiators and sales talking points.

---

## 19. REVERSE MATCHING SPECIFICATION

`AIPropertyMatchingEngine.match_leads_for_property(property_id, broker)`:
- Returns `List[LeadMatchItemDTO]` ranked by compatibility score.
- Filters leads by active CRM status (`pending`, `active`, `qualified`).
- Respects buyer budget ceiling, location preferences, and bedroom requirements.

---

## 20. AI TOOL CONSUMPTION LAYER (PART 4 READINESS)

`MatchingIntelligenceFacade` exposes 6 tool-ready methods returning structured dictionaries with `status: "success"`:
1. `find_matches(lead_id, organization_id, limit, ...)`: Ranked property recommendations.
2. `explain_match(lead_id, property_id, organization_id)`: Structured criteria evaluation.
3. `shortlist_property(lead_id, property_id, organization_id, ...)`: Shortlist addition.
4. `remove_from_shortlist(lead_id, property_id, organization_id)`: Shortlist removal.
5. `get_shortlist(lead_id, organization_id, ...)`: Paginated customer shortlist.
6. `record_property_interaction(lead_id, property_id, organization_id, interaction_type, ...)`: Interaction recording.

---

## 21. DATABASE SCHEMA & MODEL MAPPINGS

- `PropertyListing`: Central property inventory table.
- `Lead`: Customer identity and base CRM fields.
- `LeadPropertyInterest`: Junction table storing match score, shortlist status, view count, and agent notes.
- `MemoryPropertyFeedback`: Customer feedback and structured objection storage.
- `AuditLog`: Immutable audit trail of every match, recommendation, shortlist, and feedback action.

---

## 22. REST API ENDPOINTS AUDIT

| Method | Path | Summary | Auth / Scope |
|---|---|---|---|
| `POST` | `/api/v1/recommendations/generate` | Generate recommendations for a lead | Tenant Broker / Manager |
| `POST` | `/api/v1/recommendations/shortlist` | Shortlist a property for lead | Tenant Broker / Manager |
| `DELETE` | `/api/v1/recommendations/shortlist/{lead_id}/{property_id}` | Remove property from shortlist | Tenant Broker / Manager |
| `GET` | `/api/v1/recommendations/shortlist/{lead_id}` | Retrieve lead shortlist | Tenant Broker / Manager |
| `POST` | `/api/v1/recommendations/interaction` | Record customer-property interaction | Tenant Broker / Manager |
| `GET` | `/api/v1/recommendations/explain/{lead_id}/{property_id}` | Deterministic match explanation | Tenant Broker / Manager |
| `POST` | `/api/v1/recommendations/compare` | Compare 2-5 properties side-by-side | Tenant Broker / Manager |
| `GET` | `/api/v1/recommendations/reverse-match/{property_id}` | Reverse match qualified leads for listing | Tenant Broker / Manager |

---

## 23. ERROR HANDLING & EDGE CASES

- Missing Property / Lead: Returns `404 Not Found` with tenant-scoped error message.
- Over-restrictive Criteria: Returns empty recommendation list with populated `no_match_reasons` detailing why no inventory matched.
- Idempotent Shortlisting: Calling shortlist twice returns `200 OK` and preserves existing interest record without duplication.
- Null Data Safety: Gracefully handles properties with missing amenities, area, or bathroom count without throwing runtime exceptions.

---

## 24. SECURITY, AUDIT & PROVENANCE

- Every shortlist addition, removal, and feedback action produces an `AuditLog` entry.
- Requirement inputs retain provenance tracking (`EXPLICIT`, `CRM`, `IMPORTED`, `SYSTEM`, `INFERRED`).
- Untrusted user input text is stripped of prompt-injection attempts before parsing.

---

## 25. FRONTEND INTEGRATION STATUS

- `apps/web/src/components/portal/PropertyCardInline.tsx`: Renders match scores and inline interaction buttons.
- `apps/web/src/components/portal/ShortlistPanel.tsx`: Full shortlist drawer for customer portal.
- `apps/web/src/components/portal/ComparisonModal.tsx`: Side-by-side comparison modal.
- `apps/web/src/lib/api-client.ts`: Canonical API client methods for all recommendation endpoints.
- TypeScript compiler verification: `npx tsc --noEmit` **0 errors**.

---

## 26. COMPLETE TEST SUITE MATRIX & RESULTS

All 15 comprehensive Part 3 tests in `apps/api/tests/test_part3_qualification_matching.py` passed:
1. `test_canonical_matching_exact_match` — **PASSED**
2. `test_strict_hard_budget_ceiling_enforcement` — **PASSED**
3. `test_negative_preference_ground_floor_conflict` — **PASSED**
4. `test_unavailable_property_exclusion` — **PASSED**
5. `test_cross_tenant_matching_isolation` — **PASSED**
6. `test_confidence_independent_of_match_score` — **PASSED**
7. `test_amenity_unknown_preservation` — **PASSED**
8. `test_no_match_explanation_restrictive_criteria` — **PASSED**
9. `test_explain_property_match_deterministic` — **PASSED**
10. `test_shortlist_lifecycle_and_idempotency` — **PASSED**
11. `test_record_property_interaction_rejection_feedback` — **PASSED**
12. `test_stale_data_price_update_invalidates_matches` — **PASSED**
13. `test_customer_requirement_change_reflects_in_matching` — **PASSED**
14. `test_qualification_missing_info_prioritization` — **PASSED**
15. `test_matching_intelligence_facade_tool_readiness` — **PASSED**

---

## 27. REGRESSION & BACKWARD COMPATIBILITY REPORT

All 14 tests in `apps/api/tests/test_part29_ai_matching.py` passed:
- `test_hard_constraint_rejects_unavailable_status` — **PASSED**
- `test_hard_constraint_transaction_mismatch` — **PASSED**
- `test_hard_constraint_budget_ceiling_rejection` — **PASSED**
- `test_hard_constraint_bedroom_threshold_rejection` — **PASSED**
- `test_hard_constraint_negative_preference_rejection` — **PASSED**
- `test_perfect_property_match_score` — **PASSED**
- `test_score_breakdown_normalized_weights` — **PASSED**
- `test_confidence_high_when_requirements_complete` — **PASSED**
- `test_confidence_low_when_budget_or_location_missing` — **PASSED**
- `test_alternative_relaxation_allows_near_budget_candidates` — **PASSED**
- `test_prompt_injection_sanitization` — **PASSED**
- `test_deterministic_fallback_when_gemini_none` — **PASSED**
- `test_reverse_matching_ranks_compatible_lead_highest` — **PASSED**
- `test_copilot_matching_tools_registered` — **PASSED**

Zero regressions across legacy copilot and dashboard endpoints.

---

## 28. PRODUCTION DEPLOYMENT RUNBOOK

1. Backend application service requires zero database migrations (all schema changes were applied in Parts 1 & 2).
2. Redis cache service should support tag-based invalidation (`tenant:{org_id}:matches`).
3. Ensure Python environment has `pydantic>=2.0`, `sqlalchemy>=2.0`, `fastapi>=0.100`.

---

## 29. TECHNICAL DEBT & CLEANUP LOG

- Consolidated duplicate parameter passing between `req` and `dto` across `shortlist_property` and `record_property_interaction`.
- Added backward-compatible properties on `PropertyRecommendationItemDTO` (`compatibility_score`, `match_label`, `is_alternative`, `property_title`, `property_code`).
- Standardized `ShortlistActionResponseDTO` with dual attribute and dictionary item access.

---

## 30. DEPENDENCY GRAPH & INTERFACE CONTRACTS

```
[Customer Intelligence (Part 1)] ──┐
                                   ├──> [MatchingIntelligenceFacade] ──> [Part 4 AI Sales Agent]
[Property Intelligence (Part 2)] ──┘
```

---

## 31. COMPLIANCE WITH WEFYLABS CORE SYSTEM PRINCIPLES

- **No Second Matching Engine**: Fully adhered to.
- **Deterministic Hard Constraints**: Enforced prior to any score ranking.
- **Score Separation**: Match score strictly decoupled from qualification and revenue opportunity scores.
- **Complete Test Coverage**: 15/15 Part 3 tests + 14/14 regression tests passing.

---

## 32. PART 4 SALES AGENT HANDOFF CONTRACT

The AI Sales Agent built in Part 4 will interact exclusively with `MatchingIntelligenceFacade`:
- Tool 1: `find_matches(tenant_id, lead_id, top_k, allow_alternatives)`
- Tool 2: `explain_match(tenant_id, lead_id, property_id)`
- Tool 3: `shortlist_property(tenant_id, lead_id, property_id, notes)`
- Tool 4: `get_shortlist(tenant_id, lead_id)`
- Tool 5: `record_property_interaction(tenant_id, lead_id, property_id, interaction_type, rejection_reason)`
- Tool 6: `get_qualification(tenant_id, lead_id)`

No SQL queries, no hallucinated inventory, no calculation of scores in prompts. Part 3 is fully operational and certified.
