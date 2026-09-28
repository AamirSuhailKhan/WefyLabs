# WefyLabs Property Match Learning & Affinity Mining

## 1. Principles of Property Match Learning
Property recommendation must continuously adapt to buyer interactions while respecting two inviolable constraints:
1. **Correlation $\neq$ Causation**: Learning correlates property attributes (location, price band, layout, payment plan) with successful visits and bookings without claiming unverifiable causal proof.
2. **Authoritative Inventory Truth**: Low-confidence AI learning signals must never overwrite authoritative property records (pricing, unit availability, developer contracts).

## 2. Interaction Funnel for Property Units
For every recommended unit, the platform records granular outcome states:
- `PROPERTIES_SHOWN`: In brochure or catalog.
- `PROPERTIES_CLICKED`: Virtual walkthrough or spec sheet opened.
- `PROPERTIES_SHORTLISTED`: Added to lead's favorites.
- `PROPERTIES_REJECTED`: Client explicitly declines viewing.
- `PROPERTIES_REVISITED`: Client reopens link $> 3$ times within 48h.
- `PROPERTIES_DISCUSSED`: Mentioned in call or WhatsApp transcript.
- `PROPERTIES_VISITED`: Physical site visit walkthrough completed.
- `PROPERTIES_BOOKED`: Unit reserved via signed booking agreement.

## 3. Organizational Property Affinity Rules
Learned affinity rules are synthesized into `OrganizationLearningProfile`:
```json
{
  "property_affinity_rules": {
    "preferred_bedroom_count": [2, 3],
    "high_conversion_developers": ["Emaar", "Sobha", "Damac"],
    "critical_amenities": ["Metro Proximity", "Infinity Pool", "Private Balcony"],
    "payment_plan_elasticity": "High (>70% bookings favor post-handover payment plans)"
  }
}
```

## 4. Cold Start & Multi-Tenant Boundaries
New developments utilize content-based vector embeddings against verified project specifications. Customer-specific learning weights remain tenant-isolated; Tenant A's private sales affinity rules never adjust Tenant B's matching algorithms.
