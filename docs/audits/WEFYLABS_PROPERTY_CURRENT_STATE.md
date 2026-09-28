# WEFYLABS PROPERTY SUBSYSTEM — PHASE 0 AUDIT & CURRENT STATE

**Build:** Master Build 04 — Property Intelligence OS, Authoritative Inventory Truth, Property Graph & Real-Time Matching  
**Author:** Principal Engineer + CTO + Real Estate Data Architect + Inventory Systems Architect  
**Classification System:** Production Truth / Zero Fake Data  
**Audit Date:** 2026-09-26  

---

## 1. Executive Summary

A comprehensive architectural audit of the WefyLabs property, inventory, and matching codebase was conducted across models, schemas, repositories, services, routers, Celery tasks, search indexes, and AI platform integrations.

The audit revealed three distinct historical implementations of property and inventory data:
1. **Supply-Side Developer/Project/Unit Hierarchy (`apps/api/app/models/inventory_models.py`):** Authoritative physical real estate hierarchy (`RealEstateDeveloper` → `RealEstateProject` → `ProjectBuilding` → `ProjectFloor` → `ProjectUnit`). Features distributed Redis locking, append-only status transitions (`ProjectUnitStatusLog`), and transactional outbox emission.
2. **Commercial / Broker Listing Layer (`apps/api/app/models/property_models.py`):** Marketing and commercial exposure layer (`PropertyListing`, `PropertyMedia`, `PropertyDocument`, `PropertyPriceHistory`, `LeadPropertyInterest`).
3. **AI Recommendation & Search Projections (`apps/api/app/modules/property_intelligence/`, `apps/api/app/modules/property_recommendation/`):** 7-stage deterministic filter/scorer, Great-Circle Haversine geosearch, taxonomy normalization, and grounded LLM reasoning tools.

Master Build 04 formally establishes:
- **Database as Authoritative Source of Truth:** Neither LLM context, Meilisearch indexes, Redis caches, nor frontend states may invent or alter property/inventory truth.
- **Physical Unit vs Marketing Listing separation:** Physical `ProjectUnit` represents actual brick-and-mortar assets, while `PropertyListing` represents multi-channel marketing views linked via `property_listing_id`.
- **Fail-Closed Tenancy:** Strict `organization_id` scoping enforced across all database queries, geosearch filters, conflict logs, and AI tools.

---

## 2. Inventory & Property Component Classification

Each major component across the codebase was analyzed and classified using the 13 canonical operational ratings:

| Component / Subsystem | Location | Current Classification | Convergence & Hardening Strategy |
| :--- | :--- | :--- | :--- |
| **Physical Unit Hierarchy** | `app/models/inventory_models.py` | `PRODUCTION-READY` | Retained as master physical truth (`Developer` → `Project` → `Building` → `Floor` → `Unit`). Added extended states (`HOLD`, `UNDER_NEGOTIATION`, `ALLOCATED`, `UNAVAILABLE`, `UNKNOWN`). |
| **Unit Status State Machine** | `app/modules/inventory/service.py` | `PRODUCTION-READY` | Guarded by `can_transition`, Redis distributed locking, append-only audit trail (`ProjectUnitStatusLog`), and transactional Outbox. |
| **Marketing Listing Model** | `app/models/property_models.py` | `PRODUCTION-READY` | Synchronized with physical units via `property_listing_id`. Maintains price, status, amenities, and location data. |
| **Price History & Provenance** | `app/models/property_models.py` | `IMPLEMENTED` | Hardened with `currency`, `price_type`, `unit_id`, `source`, `effective_from`, `effective_to`, and `observed_at`. |
| **Data Conflict Engine** | `app/models/property_models.py` | `IMPLEMENTED` | Created `PropertyDataConflict` model and Workbench APIs for multi-source conflict resolution. |
| **Property Search Service** | `app/modules/property_intelligence/service.py` | `PRODUCTION-READY` | 7-stage deterministic filtering with Great-Circle Haversine geosearch, canonical taxonomy, and freshness policy. |
| **Amenity Taxonomy** | `app/modules/property_intelligence/service.py` | `PRODUCTION-READY` | Normalized canonical mapping (`AMENITY_CANONICAL_MAP`) preserving source strings while matching standard tokens. |
| **Freshness Engine** | `app/modules/property_intelligence/service.py` | `PRODUCTION-READY` | Distinct TTL policy: availability (2h), price (24h), possession (720h), amenities (2160h). Stale data flagged explicitly. |
| **Property Matching Engine** | `app/modules/property_recommendation/` | `PRODUCTION-READY` | 8-dimensional scoring with hard-constraint filtering (budget, location, status). Safe against recommending `SOLD` or `BLOCKED` units. |
| **AI Property Tools** | `app/modules/property_intelligence/service.py` | `PRODUCTION-READY` | Strict read-only structured tools (`get_price`, `get_amenities`, `get_possession`, `get_location`) with prompt-injection filtering. |
| **CSV Import Pipeline** | `app/modules/properties/service.py` | `PRODUCTION-READY` | Full dry-run validation, deterministic deduplication on title/locality, and idempotent upserts. |
| **Transactional Outbox** | `app/infrastructure/outbox/outbox_service.py` | `PRODUCTION-READY` | Atomically commits domain mutations with outbox events (`inventory.unit.<status>`) for async search indexing. |
| **Portal Feeds (99acres/Housing)** | External integrations | `PARTIAL` / `NOT VERIFIED` | Webhook endpoints exist for ingestion; live provider network traffic is not verified in local dev. Treated as untrusted source. |
| **Floor Plan & Media Vault** | `app/models/property_models.py` | `IMPLEMENTED` | Object-storage backed media and floor-plan attachments with tenant scoping. |

---

## 3. Detailed Model Audits

### 3.1 Developer & Project Hierarchy
- **`RealEstateDeveloper`**: Root entity scoped to `organization_id`. Tracks `developer_name`, `developer_code`, `status`, and `headquarters`.
- **`RealEstateProject`**: Scoped to developer and tenant. Contains project geography (`city`, `locality`, `latitude`, `longitude`), RERA registration (`rera_number`), possession timelines (`launch_date`, `possession_date`), and unit aggregates.
- **`ProjectBuilding` (Tower)**: Represents physical towers (e.g., Tower A, Tower B) with `total_floors` and `construction_status`.
- **`ProjectFloor`**: Supports both numeric and alphanumeric floor identifiers (Podium, Ground, Mezzanine, Penthouse).
- **`ProjectUnit`**: Canonical physical asset identity (`unit_code`, `unit_number`, `carpet_area`, `built_up_area`, `base_price`, `total_price`, `inventory_status`, `facing`, `bedrooms`, `bathrooms`).

### 3.2 Inventory State Machine Lifecycle
The inventory lifecycle supports the following states:
```text
AVAILABLE ───► HOLD ───► RESERVED ───► BOOKED ───► SOLD
    │            │           │
    ▼            ▼           ▼
BLOCKED   UNDER_OFFER  ALLOCATED / UNDER_NEGOTIATION
    ▲
    └──────── UNAVAILABLE / UNKNOWN / RETURNED
```
Every transition is guarded by `UnitInventoryStatus.can_transition()`, creates an append-only log in `project_unit_status_logs`, and records an `OutboxEvent`.

---

## 4. Architectural Invariants Enforced in Build 04
1. **Zero Hallucination / Zero Fake Data:** The AI Platform may never invent property prices, unit numbers, or availability. Facts must originate from verified database records.
2. **Search Index as Secondary Projection:** PostgreSQL is the source of truth; search indexes (Meilisearch, pgvector) are retryable projections updated via outbox events.
3. **Fail-Closed Multi-Tenancy:** Cross-tenant leakage is strictly blocked by mandatory `organization_id` predicates on all SELECT, UPDATE, and DELETE operations.
4. **Prompt Injection Defense:** All user and external portal content is wrapped in `<untrusted_property_data>` tags and stripped of instruction override patterns before reaching AI reasoning engines.
