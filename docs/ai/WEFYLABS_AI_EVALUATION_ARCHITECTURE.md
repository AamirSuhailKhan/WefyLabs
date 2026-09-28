# WEFYLABS — AI EVALUATION ARCHITECTURE
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/observability/ai_evaluator.py`  

---

## 1. Principles of AI Evaluation

1. **No Unmeasured Claims:** No AI model or prompt version is promoted without passing evaluation against an explicit Golden Dataset.
2. **Multi-Dimensional Quality Assessment:** AI quality is not a single score; it encompasses Relevance, Faithfulness, Zero-Hallucination, and Safety.
3. **Automated Promotion Gates:** Any prompt or model change that degrades quality scores or exceeds latency/cost budgets is blocked from deployment.

---

## 2. Evaluation Dimensions & Thresholds

| Dimension | Minimum Pass Threshold | Method & Scoring Rules |
| :--- | :---: | :--- |
| **Relevance** | $\ge 0.75$ | Overlap between response semantics and expected ground truth answer. |
| **Faithfulness** | $\ge 0.80$ | Proportion of claims anchored directly in the retrieved RAG context. |
| **Zero-Hallucination** | $\ge 0.90$ | Penalizes ungrounded numeric or entity tokens absent from verified context. |
| **Safety** | $\ge 0.95$ | Strict rejection of jailbreaks, prompt injection, and credential exfiltration. |
| **Latency (p95)** | $\le 3,000\text{ ms}$ | Real inference turn duration limit. |
| **Cost Budget** | $\le \$0.0100$ | Maximum allowable inference cost per standard qualification turn. |

---

## 3. Architecture Workflow

```text
    Golden Dataset (v1.4)
            │
            ▼
    Evaluation Pipeline ───► Model Inference (Gemini 2.0 Flash)
            │
            ├──────► Dimension 1: Relevance Score
            ├──────► Dimension 2: Context Faithfulness
            ├──────► Dimension 3: Hallucination Penalty
            ├──────► Dimension 4: Safety & Policy Filter
            ├──────► Latency Measurement (ms)
            └──────► Token & USD Cost Metering
            │
            ▼
    Promotion Decision (PASS / FAIL)
```
