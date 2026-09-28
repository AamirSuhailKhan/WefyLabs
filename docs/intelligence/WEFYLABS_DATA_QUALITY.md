# WefyLabs Data Quality & Anomaly Detection Engine

## 1. Data Quality Dimensions
High-fidelity intelligence requires trustworthy operational foundations. WefyLabs audits data health across five standardized dimensions:
1. **Completeness**: Percentage of required fields populated (source attribution, phone, budget).
2. **Uniqueness**: Absence of duplicate leads across phone, email, and social handles.
3. **Validity**: Conformance to schema constraints, valid phone formats, real currency values.
4. **Consistency**: Monotonic funnel stage transitions without contradictory event jumps.
5. **Timeliness**: Low event ingestion latency and absence of orphan background tasks.

## 2. Automated Issue Detection Matrix
| Issue Type | Dimension | Detection Method | Severity |
| :--- | :--- | :--- | :--- |
| `DUPLICATE_LEAD` | Uniqueness | Identity resolution matching on normalized E.164 phone | HIGH |
| `MISSING_SOURCE_ATTRIBUTION`| Completeness | Daily background ingestion audit | MEDIUM |
| `ORPHAN_EVENT` | Consistency | Foreign key reconciliation scan | MEDIUM |
| `INVALID_STAGE_TRANSITION` | Consistency | State machine invariant validation | HIGH |
| `STALE_INVENTORY` | Timeliness | Developer availability sync timestamp check | CRITICAL |

## 3. Data Quality Score Formulation
$$\text{Quality Score} = 0.30 \cdot C + 0.25 \cdot U + 0.20 \cdot V + 0.15 \cdot S + 0.10 \cdot T$$
where $C$ is Completeness, $U$ is Uniqueness, $V$ is Validity, $S$ is Consistency, and $T$ is Timeliness.
The composite score is transparently surfaced with underlying issue counts to avoid false certainty.
