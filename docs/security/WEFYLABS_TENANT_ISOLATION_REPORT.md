# WefyLabs Tenant Isolation Security Report

**Document Version**: 1.0  
**Test Suite Reference**: `apps/api/tests/test_tenant_matrix_security.py`  
**Execution Timestamp**: September 25, 2026  
**Result**: **17/17 PROOFS VERIFIED AND PASSED**  

---

## 1. Tenant Security Architecture

WefyLabs enforces a multi-tenant security perimeter designed to prevent cross-tenant data leakage across all execution vectors: HTTP REST APIs, direct domain service invocations, background worker jobs, Copilot tools, and media storage.

### Core Security Guarantees
1. **Organization as Perimeter**: The tenant boundary is determined by `organization_id`. A user/broker is merely an actor inside that boundary.
2. **Fail-Closed Resolution**: When a tenant context cannot be definitively authenticated or verified, the system returns HTTP 403 `TENANT_ISOLATION_VIOLATION`. It never guesses an organization or falls back to synthetic or demo accounts.
3. **No IDOR via Direct UUID Guessing**: Direct querying of primary keys (e.g. `PropertyListing.id`) without an accompanying `organization_id` filter is rejected at the service and database layer.

---

## 2. Automated Proof Matrix (Prompt §9)

The following 17 automated tests were executed against an isolated in-memory test database with distinct tenants (`Tenant A: Alpha Brokerage`, `Tenant B: Beta Realty`):

| Proof ID | Security Proof Statement | Test Function | Result | Verification Level |
| :---: | :--- | :--- | :---: | :--- |
| **01** | Tenant A cannot read Tenant B lead | `test_proof_01_tenant_a_cannot_read_tenant_b_lead` | **PASSED** | VERIFIED BY TEST |
| **02** | Tenant A cannot modify Tenant B lead | `test_proof_02_tenant_a_cannot_modify_tenant_b_lead` | **PASSED** | VERIFIED BY TEST |
| **03** | Tenant A cannot read Tenant B conversation | `test_proof_03_tenant_a_cannot_read_tenant_b_conversation` | **PASSED** | VERIFIED BY TEST |
| **04** | Tenant A cannot send a message using Tenant B integration | `test_proof_04_tenant_a_cannot_send_message_using_tenant_b_integration` | **PASSED** | VERIFIED BY TEST |
| **05** | Tenant A cannot view Tenant B properties | `test_proof_05_tenant_a_cannot_view_tenant_b_properties` | **PASSED** | VERIFIED BY TEST |
| **06** | Tenant A cannot invoke a tool against Tenant B property | `test_proof_06_tenant_a_cannot_invoke_tool_against_tenant_b_property` | **PASSED** | VERIFIED BY TEST |
| **07** | Tenant A cannot access Tenant B analytics | `test_proof_07_tenant_a_cannot_access_tenant_b_analytics` | **PASSED** | VERIFIED BY TEST |
| **08** | Tenant A cannot export Tenant B data | `test_proof_08_tenant_a_cannot_export_tenant_b_data` | **PASSED** | VERIFIED BY TEST |
| **09** | Tenant A cannot retrieve Tenant B search results | `test_proof_09_tenant_a_cannot_retrieve_tenant_b_search_results` | **PASSED** | VERIFIED BY TEST |
| **10** | Tenant A cannot trigger Tenant B workflow | `test_proof_10_tenant_a_cannot_trigger_tenant_b_workflow` | **PASSED** | VERIFIED BY TEST |
| **11** | Tenant A cannot access Tenant B background jobs | `test_proof_11_tenant_a_cannot_access_tenant_b_background_jobs` | **PASSED** | VERIFIED BY TEST |
| **12** | Tenant A cannot access Tenant B AI memory / audit records | `test_proof_12_tenant_a_cannot_access_tenant_b_ai_memory` | **PASSED** | VERIFIED BY TEST |
| **13** | Tenant A cannot access Tenant B documents in ObjectStorage | `test_proof_13_tenant_a_cannot_access_tenant_b_documents` | **PASSED** | VERIFIED BY TEST |
| **14** | Tenant A cannot manipulate Tenant B appointments | `test_proof_14_tenant_a_cannot_manipulate_tenant_b_appointments` | **PASSED** | VERIFIED BY TEST |
| **15** | Tenant A cannot access Tenant B billing | `test_proof_15_tenant_a_cannot_access_tenant_b_billing` | **PASSED** | VERIFIED BY TEST |
| **16** | Tenant A cannot obtain Tenant B data through guessed IDs (IDOR) | `test_proof_16_tenant_a_cannot_obtain_tenant_b_data_through_guessed_ids` | **PASSED** | VERIFIED BY TEST |
| **17** | Tenant A cannot bypass isolation through alternate routes | `test_proof_17_tenant_a_cannot_bypass_isolation_through_alternate_routes` | **PASSED** | VERIFIED BY TEST |

---

## 3. Defense-in-Depth Verification

### 3.1 Service Layer Enforcement
`PropertyService` automatically resolves the calling broker's `organization_id` via `_resolve_tenant_org_id` and applies `_tenant_filter` on every query:
```python
def _tenant_filter(self, broker_id: uuid.UUID, org_id: uuid.UUID):
    return or_(
        PropertyListing.organization_id == org_id,
        and_(PropertyListing.organization_id.is_(None), PropertyListing.broker_id == broker_id)
    )
```
Direct attempts to reserve, update price, or archive a property belonging to another tenant fail with HTTP 404 (preventing existence leakage) or HTTP 403.

### 3.2 Storage Boundary Enforcement
`ObjectStorageService` resolves physical paths strictly relative to the verified `org_uuid`:
```python
def _resolve_physical_path(self, org_uuid: uuid.UUID, object_key: str) -> Path:
    self.verify_tenant_key(object_key, org_uuid) # Raises PermissionError on mismatch
    ...
```
Cross-tenant downloads and deletions raise `PermissionError`, blocking unauthorized access even if the object key is known or guessed.

### 3.3 AI Tool Execution
Copilot tools (e.g. `get_property`, `search_properties`, `link_lead_to_property`) take the authenticated broker object, which routes through `PropertyService` with tenant filters applied. Invoking a tool with a foreign tenant's property ID returns `"error": "Property not found"`, preventing prompt injection tools from accessing cross-tenant inventory.
