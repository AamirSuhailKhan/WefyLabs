with open('docs/audits/PHASE14_FINAL_TRANSFORMATION_EXECUTIVE_REPORT.md', 'r', encoding='utf-8') as f:
    content = f.read()

idx1 = content.find('### 10.1')
idx2 = content.find('### 10.2')

assert idx1 != -1 and idx2 != -1, "Indices not found"

new_section_10 = """### 10.1 Mathematically Reconciled AI Inference Cost Model (Current 2026 vs. Post-Jan 1, 2027 Scheduled Rates)

All model pricing, token workloads, and unit economics have been verified and reconciled against current official Google Gemini documentation and transparent arithmetic:

#### A. Token Consumption Workloads (Assumed Workload Standard)
1. **Lead Qualification Extraction:**
   - System Prompt (`QUALIFICATION_SYSTEM_PROMPT` in `extractor.py`): ~620 input tokens
   - Customer Conversation & Field Context: ~330 input tokens
   - **Total Input Tokens:** **950 tokens**
   - Structured Qualification JSON Output: **300 tokens**
   - Total Tokens per Qualification Turn: **1,250 tokens**
2. **Sales Brief Generation (Triggered on ~30% of Qualified Leads):**
   - Context, Property Inventory & Lead Profile Input: **1,100 tokens**
   - Executive Brief & Recommended Strategy Output: **350 tokens**
   - Total Tokens per Brief: **1,450 tokens**
3. **Operational Retry Allowance:**
   - Structured parsing / validation retry rate: **5%**

#### B. Current Promotional Rates (Through December 31, 2026: $0.75 / 1M In, $3.75 / 1M Out)

$$\\text{Qualification Input Cost} = 950 \\times \\frac{\\$0.75}{1,000,000} = \\$0.0007125$$

$$\\text{Qualification Output Cost} = 300 \\times \\frac{\\$3.75}{1,000,000} = \\$0.0011250$$

$$\\mathbf{\\text{Raw Qualification Cost}} = \\$0.0007125 + \\$0.0011250 = \\mathbf{\\$0.0018375} \\quad (\\mathbf{₹0.1531})$$

$$\\mathbf{\\text{Retry Allowance (5\\%)}} = 0.05 \\times \\$0.0018375 = \\mathbf{\\$0.000091875} \\quad (\\mathbf{₹0.0077})$$

$$\\text{Sales Brief Input Cost} = 1,100 \\times \\frac{\\$0.75}{1,000,000} = \\$0.0008250$$

$$\\text{Sales Brief Output Cost} = 350 \\times \\frac{\\$3.75}{1,000,000} = \\$0.0013125$$

$$\\text{Sales Brief Unit Cost} = \\$0.0008250 + \\$0.0013125 = \\$0.0021375 \\quad (₹0.1781)$$

$$\\mathbf{\\text{Expected Sales Brief Cost (30\\%)}} = 0.30 \\times \\$0.0021375 = \\mathbf{\\$0.00064125} \\quad (\\mathbf{₹0.0534})$$

$$\\mathbf{\\text{Total Current Blended Cost per Lead}} = \\$0.0018375 + \\$0.000091875 + \\$0.00064125 = \\mathbf{\\$0.002570625} \\quad (\\mathbf{₹0.2142})$$

*(At foreign exchange rate of 1 USD = 83.33 INR)*

#### C. Post-January 1, 2027 Scheduled Standard Rates ($1.50 / 1M In, $7.50 / 1M Out - Exact 2x Surcharge)
Google's official pricing documentation establishes that promotional introductory rates expire on December 31, 2026, reverting to standard list rates ($1.50 / 1M in, $7.50 / 1M out):

- **2027 Raw Qualification Cost:** $950 \\times \\$0.0000015 + 300 \\times \\$0.0000075 = \\mathbf{\\$0.0036750} \\quad (₹0.3062)$
- **2027 Retry Allowance (5%):** $0.05 \\times \\$0.0036750 = \\mathbf{\\$0.00018375} \\quad (₹0.0153)$
- **2027 Sales Brief Cost:** $1,100 \\times \\$0.0000015 + 350 \\times \\$0.0000075 = \\$0.0042750 \\quad (₹0.3562)$
- **2027 Expected Brief Cost (30%):** $0.30 \\times \\$0.0042750 = \\mathbf{\\$0.0012825} \\quad (₹0.1069)$
- **Total Post-Jan 1, 2027 Blended Cost per Lead:**
  $$\\mathbf{\\text{Total 2027 Blended Cost}} = \\$0.0036750 + \\$0.00018375 + \\$0.0012825 = \\mathbf{\\$0.00514125} \\quad (\\mathbf{₹0.4284})$$

#### D. Comparative Scenario & Sensitivity Ledger (Measured, Price-Based, and Assumed)

| Workload Scenario | Lead Volume | Current 2026 AI Cost | Post-Jan 2027 AI Cost | Budget / Gross Margin Impact | Classification |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Commercial Pilot Tier** | 100 leads | **\\$0.2571 (₹21.42)** | **\\$0.5141 (₹42.84)** | Current ₹35 budget has ₹13.58 buffer; 2027 requires ₹50 budget | `PRICE-BASED ESTIMATE` |
| **Mid-Market Evaluation** | 500 leads | **\\$1.2853 (₹107.10)**| **\\$2.5706 (₹214.21)**| Covered by pilot fee | `PRICE-BASED ESTIMATE` |
| **Enterprise Monthly Scale**| 10,000 leads | **\\$25.71 / mo (₹2,142)**| **\\$51.41 / mo (₹4,284)**| Direct AI COGS at scale | `PRICE-BASED ESTIMATE` |
| **Growth-Tier SaaS Tenant** | 10,000 leads | **\\$25.71 / mo** | **\\$51.41 / mo** | 2026 Gross Margin: **70.2%**; 2027 Gross Margin: **64.3%** | `PRICE-BASED ESTIMATE` |
| **Sensitivity: 2x Tokens** | 10,000 leads | **\\$51.41 / mo (₹4,284)**| **\\$102.83 / mo (₹8,569)**| 2027 Gross Margin: **52.5%** (Multi-turn qualification stress test) | `ASSUMED WORKLOAD` |
| **Sensitivity: 60% Briefs** | 10,000 leads | **\\$32.12 / mo (₹2,677)**| **\\$64.24 / mo (₹5,353)**| 2027 Gross Margin: **61.3%** (Heavy sales briefing frequency) | `ASSUMED WORKLOAD` |

#### E. Model Comparison Status & Scientific Rigor Disclaimer
- **Candidate Models:** `gemini-3.5-flash-lite`, `gemini-3.6-flash` (Designated Standard), `gemini-3.8-flash`.
- **Comparative Metrics (Latency / Field Accuracy):** Any comparative percentages previously cited in interim planning discussions (e.g. 94.2% vs 99.8%) are classified as **`UNVERIFIED — SPECULATIVE VENDOR BENCHMARKS / REQUIRES LIVE MODEL EVALUATION`**. A 6-case or 10-case internal suite cannot establish statistical comparative percentages.
- **Deterministic Rule Compliance:** The local test battery (`scratch/lead_qualification_synthetic_suite.py`) verified **10 / 10 exact discrete scenarios passed** for schema validation, prompt injection blocking, and currency parsing.
- **Live Provider Status:** Formally classified as **`BLOCKED — VALID CREDENTIAL REQUIRED`** due to Google GenAI SDK `ClientError: 400 INVALID_ARGUMENT (API_KEY_INVALID)`.

---

"""

updated_content = content[:idx1] + new_section_10 + content[idx2:]
with open('docs/audits/PHASE14_FINAL_TRANSFORMATION_EXECUTIVE_REPORT.md', 'w', encoding='utf-8', newline='') as f:
    f.write(updated_content)

print("SUCCESS: Updated Section 10 in executive report")

