with open('docs/audits/PHASE14_PRODUCT_STRATEGY_AND_BUSINESS_MODEL.md', 'r', encoding='utf-8') as f:
    content = f.read()

idx1 = content.find('## 3. Unit Economics')
idx2 = content.find('## 4. Customer Acquisition')

assert idx1 != -1 and idx2 != -1, "Indices not found"

new_section_3 = """## 3. Unit Economics & Cost-to-Serve Analysis

The modern asynchronous architecture (FastAPI, PostgreSQL with `pgvector 0.8.7`, Redis 7, Celery, and Google Gemini 3.6 Flash) provides extraordinarily favorable gross margins compared to legacy monolithic stacks:

### Estimated Monthly Infrastructure & AI Cost per Growth Tenant (10,000 Leads/Mo)

| Component | Architecture / Sizing | 2026 Monthly Cost (USD) | 2026 Monthly Cost (INR) | Post-Jan 2027 Cost (USD) | Classification |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Compute (API & Workers)** | AWS ECS Fargate or DigitalOcean Dedicated (4 vCPU, 8GB RAM) | $45.00 | ₹3,750 | $45.00 | `PRICE-BASED ESTIMATE` |
| **Database (PostgreSQL + pgvector)** | Managed PostgreSQL 16 (2 vCPU, 4GB RAM, NVMe SSD) | $55.00 | ₹4,580 | $55.00 | `PRICE-BASED ESTIMATE` |
| **In-Memory Cache & Queues** | Managed Redis 7 (1GB RAM) | $15.00 | ₹1,250 | $15.00 | `PRICE-BASED ESTIMATE` |
| **AI Inference (Gemini 3.6 Flash)** | 10,000 leads blended (950 in / 300 out + 5% retry + 30% sales brief) | $25.71 | ₹2,142 | $51.41 | `PRICE-BASED ESTIMATE` |
| **Conversational Chat Headroom Buffer** | Optional 10% multi-turn follow-up buffer (~2,600 turns) | $2.57 | ₹214 | $5.14 | `ASSUMED WORKLOAD` |
| **Outbound WhatsApp Conversations** | Meta Cloud API service conversation fee (~10k conversations) | Client direct billing / BSP pass-through | Pass-through | Pass-through | `PASS-THROUGH` |
| **Total Direct COGS per Tenant** | | **$143.28** | **₹11,936** | **$171.55 (₹14,295)** | `PRICE-BASED ESTIMATE` |

### Gross Margin Scenarios (Monthly Revenue per Growth Tenant: ₹39,999 / $480.00)
- **Current 2026 Baseline (Promotional List Pricing):**
  - Direct COGS: $143.28 (₹11,936).
  - Gross Profit: **$336.72 (₹28,063)**.
  - **Gross Margin:** **70.2%**.
- **Post-January 1, 2027 Standard List Pricing (Scheduled 2x Token Rate):**
  - Direct COGS: $171.55 (₹14,295).
  - Gross Profit: **$308.45 (₹25,704)**.
  - **Gross Margin:** **64.3%**.
- **Post-2027 Sensitivity Stress Test 1 (Token Workload Doubles to 1,900 in / 600 out):**
  - Total COGS: $228.11 (₹19,008).
  - Gross Profit: **$251.89 (₹20,991)**.
  - **Gross Margin:** **52.5%**.
- **Post-2027 Sensitivity Stress Test 2 (Brief Generation Increases to 60% of Leads):**
  - Total COGS: $185.67 (₹15,472).
  - Gross Profit: **$294.33 (₹24,527)**.
  - **Gross Margin:** **61.3%**.

---

"""

updated_content = content[:idx1] + new_section_3 + content[idx2:]
with open('docs/audits/PHASE14_PRODUCT_STRATEGY_AND_BUSINESS_MODEL.md', 'w', encoding='utf-8', newline='') as f:
    f.write(updated_content)

print("SUCCESS: Updated Section 3 in strategy doc")

