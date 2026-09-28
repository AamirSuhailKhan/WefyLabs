# WEFYLABS — REAL-TIME IDENTITY GRAPH ARCHITECTURE

## 1. Conceptual Domain Hierarchy
WefyLabs models customer identity through a strict hierarchical graph:

```text
Organization (Tenant Boundary: organization_id)
    ↓
Person / Identity (Canonical Customer Node)
    ↓
Lead (Channel Inflow / Operational CRM Record)
    ↓
Conversation (Omnichannel Communication Stream)
    ↓
Activity (Timeline Event / Audit Log)
    ↓
Opportunity (Revenue Deal / Booking)
```

---

## 2. Identity Graph Schema & Links

### 2.1 Identity Node (`identities` table)
- `id`: Canonical UUID string for the person
- `organization_id`: Tenant foreign key (strictly isolated)
- `primary_phone_e164`: Primary verified contact number
- `primary_email`: Primary verified email address
- `primary_name`: Canonical name
- `first_source`: First touch channel (`META`, `GOOGLE`, `WEBSITE`, etc.)
- `lead_count`: Total lead instances linked to this identity node

### 2.2 Identity Link (`identity_links` table)
- `id`: UUID string
- `identity_id`: Foreign key to `identities.id`
- `lead_id`: Foreign key to `leads.id`
- `organization_id`: Tenant foreign key
- `link_confidence`: `1.0` (exact phone/email match) or lower
- `link_method`: `intake_ingestion`, `phone_match`, `email_match`
- `matched_fields`: List of matching fields (e.g. `["phone", "email"]`)
- `is_primary`: Boolean indicating canonical lead representation

---

## 3. Matching Hierarchy & Resolution Rules

### Tier 1: Exact Trusted Identifiers
1. **Verified E.164 Phone**: Primary deterministic identifier within the tenant.
2. **Normalized Email**: Secondary deterministic identifier.
3. **Provider Identity ID / WhatsApp JID**: Direct 1-to-1 match.

### Tier 2: Strong Combinations
- Normalized phone + customer name match
- Normalized email + customer name match

### Tier 3: Reviewable Candidates
- Weak matches or conflicting attributes are recorded as candidate links for operator review rather than destructive automatic merging.

---

## 4. Cross-Channel Consolidation Invariants
1. **Never Destroy Evidence**: When a repeat inquiry arrives (e.g. from Google after Meta), the first-touch attribution (`SourceAttribution`) is preserved, `last_touch_at` is updated, and the new inquiry is linked as a re-engagement activity.
2. **Tenant Scoping**: An identical phone number in Tenant A and Tenant B creates two distinct, non-overlapping `Identity` nodes in each respective tenant. Zero cross-tenant leakage.
3. **Owner Preservation**: Subsequent inquiries do not silently reassign lead ownership away from the active assigned broker.
