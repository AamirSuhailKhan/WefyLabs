# WEFYLABS — PROPERTY INTELLIGENCE CURRENT STATE AUDIT
**Master Build 03: Authoritative Property & Inventory Truth Architecture**
**Audit Date:** 2026-09-25  
**Auditor:** Principal Engineer & Real Estate Data Architect  
**Repository State:** `update-os` branch, Master Build 01 & 02 Verified

---

## 1. Executive Summary

This audit establishes the baseline of all property, project, building, floor, unit, and inventory capabilities across WefyLabs. In accordance with Master Build 03 rules, **no parallel property systems are built and no fake/synthetic data is tolerated**. Instead, existing supply-side entities (`ProjectUnit`, `RealEstateProject`, `ProjectBuilding`, `ProjectFloor`, `RealEstateDeveloper`) and demand-side commercial entities (`PropertyListing`, `PropertyMedia`, `PropertyPriceHistory`, `LeadPropertyInterest`) are audited, converged, and hardened into a single unified source of truth.

---

## 2. Audit Matrix of Existing Components

| Component / Subsystem | Path / Location | Classification | Current State & Gaps | Target Action in Build 03 |
| :--- | :--- | :--- | :--- | :--- |
| **Physical Supply Hierarchy** | `apps/api/app/models/inventory_models.py` | `production-ready` | Complete hierarchy: Developer → Project → Phase → Building → Floor → Unit. Uses strict types (MoneyType, PctType). | Maintain as canonical physical hierarchy. |
| **Unit Inventory State Machine** | `apps/api/app/models/inventory_models.py` | `production-ready` | `UnitInventoryStatus` defines `AVAILABLE`, `RESERVED`, `BOOKED`, `SOLD`, `BLOCKED`, `UNDER_OFFER`, `RETURNED` with explicit `can_transition()` graph. | Keep as canonical physical state machine. |
| **Physical Unit Audit Log** | `apps/api/app/models/inventory_models.py` | `production-ready` | `ProjectUnitStatusLog` append-only audit trail with `previous_status`, `new_status`, `reason`, `changed_by_id`, `deal_id`. | Preserve and link to outbox events. |
| **Commercial Property Listing** | `apps/api/app/models/property_models.py` | `production-ready` | `PropertyListing` represents commercial/marketing projection. Supports `organization_id` and `broker_id`. | Link seamlessly to `ProjectUnit` (`property_listing_id`). |
| **Price Audit History** | `apps/api/app/models/property_models.py` | `production-ready` | `PropertyPriceHistory` records `old_price`, `new_price`, `changed_by_id`, `reason`, `changed_at`. | Keep and enforce for all price mutations. |
| **Lead ↔ Property Relationship** | `apps/api/app/models/property_models.py` | `production-ready` | `LeadPropertyInterest` tracks matching score, deterministic score, reasons, mismatches, score breakdown, visits. | Converge with Master Build 02 lead intelligence. |
| **Supply-Side Service** | `apps/api/app/modules/inventory/service.py` | `partial` | UnitService enforces state transitions, locks, and logs. **Gap:** Did not propagate unit status changes to linked `PropertyListing`. | Add automatic synchronization to linked `PropertyListing` and transactional outbox. |
| **Property Intelligence Service** | `apps/api/app/modules/property_intelligence/service.py` | `partial` | 7-stage deterministic search and grounded truth fact pack. **Gap:** Search query checked `broker_id == t_uuid` but did not include `organization_id == t_uuid`. | Update search filter to `or_(organization_id == t_uuid, broker_id == t_uuid)`. |
| **AI Property Tools** | `apps/api/app/modules/property_intelligence/` | `partial` | Fact pack and search exist. **Gap:** Missing structured AI tools for `compare_properties`, `get_project`, `get_unit`, `check_availability` with prompt injection defense. | Implement AI Property Tools layer with inert delimiter wrapping. |
| **CSV Batch Importer** | `apps/api/app/modules/properties/service.py` | `partial` | Validates with `FileSecurityScanner`, detects duplicates. **Gap:** Lacks dry-run/preview mode and project/unit hierarchy mapping. | Enhance import pipeline with dry-run and idempotency. |
| **Property Recommendation / Matcher** | `apps/api/app/modules/property_recommendation/` | `production-ready` | 16-file deterministic matching engine with hard filters, compatibility scoring, and explainable breakdowns. | Verify tenant isolation and non-hallucinated scoring. |
| **Public Share Endpoint** | `apps/api/app/presentation/api/v1/properties.py` | `production-ready` | Redacts internal fields (`owner_name`, `owner_phone`, `commission_amount`, `internal_notes`). | Maintain strict privacy invariant. |
| **Distributed Reservation Lock** | `apps/api/app/common/redis/distributed_lock.py` | `production-ready` | Redis-backed distributed lock with safe in-process fallback. | Tested under concurrent reservation races. |

---

## 3. Identification of Duplicates & Convergence Decisions

### A. Dual Property Representation
- **Existing Issue:** The repository contains two conceptual representations:
  1. `ProjectUnit` (`inventory_models.py`): The physical unit in a building/floor/project with atomic inventory lifecycle.
  2. `PropertyListing` (`property_models.py`): The marketing/commercial listing entity exposed to channels, leads, and public sharing.
- **Decision (Convergence, NOT Rewrite):**
  - Treat `ProjectUnit` as the **Physical Inventory Identity**.
  - Treat `PropertyListing` as the **Market / Channel Listing**.
  - Maintain the existing `ProjectUnit.property_listing_id` foreign key.
  - When `ProjectUnit.transition_status()` is invoked (e.g., unit reserved or sold), automatically synchronize the linked `PropertyListing.status`.
  - When `PropertyListing` price is updated, sync `ProjectUnit.total_price` if linked.

### B. Search Pipeline Unification
- **Existing Issue:** `PropertyService.search_and_filter` in `modules/properties/service.py` and `PropertyIntelligenceService.search_property_inventory` in `modules/property_intelligence/service.py` provide overlapping query capabilities.
- **Decision:**
  - `PropertyIntelligenceService` serves as the authoritative, deterministic 7-stage search and grounded truth provider for AI agents and system-to-system queries.
  - `PropertyService.search_and_filter` delegates to or aligns with the 7-stage filter semantics and cache invalidation tags.

---

## 4. Architectural Invariants for Build 03

1. **Physical Identity Stability:** A unit's identity is defined by `(organization_id, project_id, building_id, unit_number)`. Price or status modifications never create a new unit or alter identity.
2. **Deterministic State Machine:** Unit status transitions must strictly follow `UnitInventoryStatus.can_transition()`. Direct arbitrary status mutations by LLMs or untrusted callers are rejected with HTTP 409 Conflict.
3. **Strict Multi-Tenant Scoping:** Every property query, unit lookup, reservation, and search must filter by `organization_id` / `broker_id`. Cross-tenant data leakage is prevented at the database level.
4. **Zero AI Hallucination:** Prices, availability states, and configurations must originate from authoritative database records. If a field is missing, it is explicitly returned as `NOT_PROVIDED` or `NOT_AVAILABLE`.
5. **Prompt-Injection Defense:** Untrusted property descriptions and notes must be wrapped in inert delimiters (`<data>...</data>`) and never interpreted as agent instructions.
6. **Transactional Outbox:** Every state transition must record a domain event (`inventory.unit.reserved`, `inventory.unit.sold`, `property.price_changed`) in the outbox atomically with the database commit.
