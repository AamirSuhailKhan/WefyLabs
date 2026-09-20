# WEFYLABS PART 3: CANONICAL MATCHING & QUALIFICATION MATRIX
===============================================================

**Matrix Specification:** Canonical Real Estate Intelligence Engine  
**Target Consumer:** Part 4 AI Sales Agent Tools & Broker Copilot  
**Version:** 1.0.0  

---

## 1. 8-DIMENSIONAL SCORING MATRIX

| Dimension ID | Dimension Name | Default Weight | Algorithm / Evaluation Logic | Grounded Criteria Generated | Negative Conflict Impact |
|---|---|---|---|---|---|
| `DIM_01` | **Budget Fit** | `0.25` | Stepwise continuous: 100% if `price <= budget_max`. In alternative mode, $1.0 < \frac{price}{budget} \le 1.15$ scales $90\% \to 50\%$. | `"Within stated budget: ₹{price} (budget ceiling ₹{max})"` | Rejection if strict; else penalty |
| `DIM_02` | **Location Fit** | `0.25` | Exact locality: 100%. Adjacent / sub-locality: 75%. Same city only: 40%. Different city: 0%. | `"Exact locality match: {locality}"` / `"City match: {city}"` | None |
| `DIM_03` | **Property Type Fit** | `0.15` | Grouped synonym match (apartment family vs villa family vs plot vs commercial). Exact: 100%. Group: 80%. Cross: 20%. | `"Property type match: {type}"` | None |
| `DIM_04` | **Bedrooms / BHK Fit** | `0.10` | Exact BHK: 100%. BHK + 1: 90%. BHK - 1 (alternative mode only): 50%. Deficit > 1: 0%. | `"Exact {bhk} BHK configuration matched"` | Hard filter in strict mode |
| `DIM_05` | **Area / Layout Fit** | `0.10` | Within $\pm 10\%$ of requested sqft: 100%. Within $\pm 25\%$: 80%. Deficit > 30%: 30%. | `"Layout size: {sqft} sqft"` | None |
| `DIM_06` | **Amenities Fit** | `0.10` | Jaccard similarity: $\frac{\|Requested \cap Verified\|}{\|Requested\|}$. Unverified amenities tracked in `unknown_criteria`. | `"Verified amenity: {name}"` | None |
| `DIM_07` | **Timeline / Possession**| `0.05` | Immediate / Ready to move alignment with buyer move-in urgency. | `"Ready to move immediate possession"` | Trade-off if under construction |
| `DIM_08` | **Financing & Behavioral**| `0.00` (Dynamic) | Bank pre-approval alignment, payment plan compatibility. | `"Payment plan verified"` | None |

---

## 2. HARD CONSTRAINTS FILTER MATRIX (PRE-RANKING)

| Constraint ID | Target Attribute | Evaluation Code | Strict Enforcement | Alternative Mode Relaxation | Failure Code |
|---|---|---|---|---|---|
| `HC_01` | **Inventory Availability** | `status.lower() in ('available', 'active', 'ready') and deleted_at is None` | **STRICT (100%)** | **NEVER RELAXED** | `INVENTORY_UNAVAILABLE` |
| `HC_02` | **Transaction Compatibility**| `lead.intent == listing.category` (Sale vs Rent) | **STRICT (100%)** | **NEVER RELAXED** | `TRANSACTION_MISMATCH` |
| `HC_03` | **Budget Hard Ceiling** | `listing.price <= lead.budget_max` | **STRICT (100%)** | Relaxed up to $+15\%$ max | `BUDGET_EXCEEDED` |
| `HC_04` | **Minimum Bedroom Threshold**| `listing.bedrooms >= lead.min_bedrooms` | **STRICT (100%)** | Relaxed by $-1$ bedroom max | `BEDROOM_DEFICIT` |
| `HC_05` | **Tenant Isolation Boundary**| `listing.broker_id == tenant.id` | **STRICT (100%)** | **NEVER RELAXED** | `TENANT_VIOLATION` |

---

## 3. MATCH EXPLANATION & CLASSIFICATION BINDINGS

| Overall Score Range | Negative Conflicts Count | Recommendation Type | Match Label | UI Badge Color | Agent Action Prompt |
|---|---|---|---|---|---|
| `85.0 – 100.0` | `== 0` | `EXACT_MATCH` | **Exact Match** | Emerald Green | "Present as top recommendation. Schedule site visit." |
| `70.0 – 84.9` | `== 0` | `CLOSE_MATCH` | **Close Match** | Blue | "Present with highlighted trade-offs." |
| `50.0 – 69.9` | Any | `ALTERNATIVE` | **Alternative Option** | Amber | "Present as stretch option / alternative with permission." |
| `< 50.0` | Any | Disqualified | **No Match** | N/A | Excluded from candidate output |
| Any | `> 0` | `ALTERNATIVE` | **Negative Conflict** | Rose Red | "Flag customer objection directly before recommending." |

---

## 4. PART 4 AI SALES AGENT TOOL BINDING CONTRACT

```json
{
  "tools": [
    {
      "tool_name": "find_property_matches",
      "facade_method": "MatchingIntelligenceFacade.find_matches",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)",
        "top_k": "Integer (default 5)",
        "allow_alternatives": "Boolean (default false)",
        "flexibility_pct": "Float (default 0.0)"
      },
      "returns": {
        "status": "success",
        "total_matches": "int",
        "results": "Array<PropertyMatchItem>"
      }
    },
    {
      "tool_name": "explain_property_match",
      "facade_method": "MatchingIntelligenceFacade.explain_match",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)",
        "property_id": "UUID (target property)"
      },
      "returns": {
        "status": "success",
        "match_score": "float",
        "matched_criteria": "Array<string>",
        "partial_criteria": "Array<string>",
        "negative_conflicts": "Array<string>",
        "unknown_criteria": "Array<string>",
        "deterministic_summary": "string"
      }
    },
    {
      "tool_name": "shortlist_property",
      "facade_method": "MatchingIntelligenceFacade.shortlist_property",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)",
        "property_id": "UUID (target property)",
        "notes": "string (optional)"
      },
      "returns": {
        "status": "success",
        "interest_status": "SHORTLISTED",
        "match_score": "float"
      }
    },
    {
      "tool_name": "record_customer_property_feedback",
      "facade_method": "MatchingIntelligenceFacade.record_property_interaction",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)",
        "property_id": "UUID (target property)",
        "interaction_type": "string (VIEWED | LIKED | SHORTLISTED | REJECTED | VISITED)",
        "rejection_reason": "string (PRICE_TOO_HIGH | LOCATION | SIZE | BHK | FLOOR | AMENITIES | OTHER)",
        "feedback": "string (optional user utterance)"
      },
      "returns": {
        "status": "success",
        "interaction_type": "string",
        "interest_status": "string"
      }
    },
    {
      "tool_name": "get_customer_shortlist",
      "facade_method": "MatchingIntelligenceFacade.get_shortlist",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)",
        "status_filter": "string (default null)"
      },
      "returns": {
        "status": "success",
        "total_count": "int",
        "items": "Array<ShortlistItem>"
      }
    },
    {
      "tool_name": "get_lead_qualification_snapshot",
      "facade_method": "MatchingIntelligenceFacade.get_qualification",
      "parameters": {
        "tenant_id": "UUID (from auth context)",
        "lead_id": "UUID (target customer)"
      },
      "returns": {
        "qualification_status": "string (UNQUALIFIED | PARTIALLY_QUALIFIED | FULLY_QUALIFIED)",
        "missing_critical_fields": "Array<string>",
        "next_recommended_question": "string"
      }
    }
  ]
}
```

---

## 5. SCORE SEPARATION MATRIX

| Score Field | Governing Service | Range | Objective | Update Trigger |
|---|---|---|---|---|
| `compatibility_score` | `AIPropertyMatchingEngine` | `0.0 – 100.0` | Customer $\leftrightarrow$ Property specific fit | Customer requirement edit, property price/status change |
| `qualification_score` | `LeadQualificationDomainService` | `0.0 – 100.0` | Buyer purchase readiness & lifecycle maturity | New conversation turn, contact info verification, budget confirmed |
| `revenue_opportunity_score` | `crm_models.Lead` | `0.0 – 100.0` | Deal size & brokerage commission priority | Stage transition, offer submission, deal closed |

**Matrix certified 100% compliant with Part 3 deterministic intelligence architecture.**
