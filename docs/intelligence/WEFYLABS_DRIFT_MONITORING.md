# WefyLabs Drift Monitoring & Statistical Surveillance

## 1. Types of Drift Monitored
1. **Feature Drift**: Inbound lead attribute distribution changes (e.g. abrupt shift in median budget or inquiry channels).
2. **Concept Drift**: Degradation in the statistical relationship between qualification scores and actual booking conversion.
3. **Model Quality Drift**: Increase in hallucination rate, latency spikes, or drop in recommendation acceptance.
4. **Cost Drift**: Unplanned surges in token consumption or provider API overhead per qualified lead.

## 2. Statistical Methodology (Population Stability Index - PSI)
Feature distribution stability is measured via the Population Stability Index:
$$\text{PSI} = \sum_{i=1}^{k} (A_i - E_i) \times \ln\left(\frac{A_i}{E_i}\right)$$
where $A_i$ is the actual recent distribution and $E_i$ is the baseline expectation across bucket $i$.

| PSI Value | Interpretation | System Response |
| :--- | :--- | :--- |
| $\text{PSI} < 0.10$ | Stable Distribution | Continue normal operations |
| $0.10 \le \text{PSI} < 0.20$ | Moderate Shift | Flag for telemetry monitoring |
| $\text{PSI} \ge 0.20$ | Significant Drift | Emit `DriftAlertRecord` & trigger review |

## 3. Drift Alert Record Schema
```python
class DriftAlertRecord(Base):
    __tablename__ = "drift_alert_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    drift_type: Mapped[str] = mapped_column(String(40), nullable=False)
    feature_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    drift_magnitude: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="NEW", nullable=False)
```
