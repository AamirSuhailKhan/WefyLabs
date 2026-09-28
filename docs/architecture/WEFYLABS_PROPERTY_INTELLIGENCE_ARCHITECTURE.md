# WEFYLABS PROPERTY INTELLIGENCE OS — ARCHITECTURE SPECIFICATION

**Build:** Master Build 04  
**Status:** Approved & Verified in Code  
**Layer:** Subsystem Core Architecture  

---

## 1. Architectural Principles

WefyLabs Property Intelligence OS operates under strict foundational principles:

```text
                  PROPERTY INTELLIGENCE OS

                         PROJECT
                            ↓
                       BUILDING
                            ↓
                          FLOOR
                            ↓
                          UNIT
                            ↓
                     INVENTORY TRUTH
                    /        |        \
                PRICE   AVAILABILITY   SOURCE
                   \         |         /
                    \        |        /
                     PROVENANCE + FRESHNESS
                              ↓
                         SEARCH INDEX
                              ↓
                      MATCHING ENGINE
                              ↓
                          AI TOOLS
                              ↓
                  CONVERSATION / SALES
                              ↓
                           REVENUE
```

1. **Database as Canonical Truth:** PostgreSQL holds authoritative inventory, pricing, availability, and audit logs.
2. **Search Index as Asynchronous Projection:** Search indexing (PostgreSQL tsvector / Meilisearch / pgvector) is downstream from the transactional database. Failure of a search index update does not roll back the domain transaction; the outbox ensures eventual consistency.
3. **AI as Reasoning Layer Only:** LLMs reason over retrieved, authenticated property facts. They never synthesize, guess, or extrapolate prices, units, or availability.
4. **Physical Unit vs Marketing Listing:** Distinct physical units (`ProjectUnit`) represent structural inventory; commercial listings (`PropertyListing`) represent channel-facing syndications.

---

## 2. 7-Stage Deterministic Search Pipeline

The search engine in `apps/api/app/modules/property_intelligence/service.py` executes a structured 7-stage deterministic filter pipeline:

```text
Incoming Query
    │
    ▼
Stage 1: Multi-Tenant Filter (organization_id mandatory)
    │
    ▼
Stage 2: Geography Filter (city, locality, sub-locality)
    │
    ▼
Stage 3: Configuration & Area Filter (bhk, bedrooms, min/max sqft)
    │
    ▼
Stage 4: Financial Boundaries (min_price, max_price, price_type)
    │
    ▼
Stage 5: Inventory Availability Filter (status == 'available')
    │
    ▼
Stage 6: Geospatial Great-Circle Haversine Filter (radius_km from lat/lng)
    │
    ▼
Stage 7: Normalized Amenity Intersect & Sorting (price_asc, distance_asc, area_desc)
    │
    ▼
Structured Provenance Response DTO
```

### 2.1 Great-Circle Haversine Distance
Geospatial radius filtering computes the exact spherical surface distance:
$$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
where $R = 6371.0\text{ km}$. Properties outside the designated radius are excluded, and results sorted by `distance_asc` are returned with deterministic distance metrics.

---

## 3. Freshness Policy & Staleness Engine

Data provenance and freshness are evaluated per attribute rather than as an arbitrary global timestamp:

| Dimension | Maximum Time-to-Live (TTL) | Failure Mode if Expired |
| :--- | :--- | :--- |
| **Availability Status** | 2 Hours | Marked `STALE`; recommendation requires human confirmation |
| **Price / Charges** | 24 Hours | Marked `EXPIRED`; cannot be quoted as firm list price |
| **Possession Timelines** | 720 Hours (30 Days) | Marked `UNVERIFIED`; flagged for construction update |
| **Amenities & Specifications** | 2160 Hours (90 Days) | Baseline specs retained with re-audit flag |

Every search item and property detail response includes a `freshness` breakdown indicating exact field ages, source provenance, and staleness status.

---

## 4. Conflict Resolution Workbench & Source Precedence

When multiple integrations (developer API, portal webhook, CSV upload, manual CRM) report conflicting data for the same physical unit, WefyLabs enforces a **Source Precedence Hierarchy**:

1. **Developer Authoritative Feed** (Trust Tier 1)
2. **Verified Internal Inventory Audit** (Trust Tier 2)
3. **Authorized Broker Feed** (Trust Tier 3)
4. **Portal Ingestion Feed (99acres / Housing)** (Trust Tier 4)
5. **CSV Batch Import** (Trust Tier 5)
6. **Manual Unverified Entry** (Trust Tier 6)

### Conflict Workbench Lifecycle
If a lower-trust source or conflicting observation arrives:
1. The authoritative database value is **not** silently overwritten.
2. A `PropertyDataConflict` record is created with:
   - `field_name` (e.g. `price`, `availability`)
   - `current_value` vs `competing_value`
   - `current_source` vs `competing_source`
   - `observed_at` timestamps
3. Operators inspect the conflict in the internal Conflict Workbench and choose `ACCEPT_COMPETING`, `KEEP_CURRENT`, or `MANUAL_OVERRIDE` with audit reason logging.

---

## 5. AI Property Tools & Security Architecture

The AI Gateway connects to the Property Intelligence OS via strict read-only tool wrappers:
- `search_properties(tenant_id, criteria)`
- `get_property(tenant_id, property_id)`
- `get_price(tenant_id, property_id)`
- `get_amenities(tenant_id, property_id)`
- `get_possession(tenant_id, property_id)`
- `get_location(tenant_id, property_id)`

### Prompt Injection Defense
All property descriptions, marketing remarks, and imported brochures are treated as untrusted user inputs.
Before feeding context to LLM reasoning prompts:
1. Text is scrubbed of directive injection phrases (`ignore previous instructions`, `reveal system prompt`, `disregard instructions`).
2. Filtered matches are replaced with `[FILTERED_INSTRUCTION]`.
3. Content is encapsulated within `<untrusted_property_data>` boundary tags, instructing the model to treat the content solely as factual attributes and never as executable instructions.
