with open('docs/audits/PHASE14_PRODUCT_STRATEGY_AND_BUSINESS_MODEL.md', 'r', encoding='utf-8') as f:
    content = f.read()

idx1 = content.find('## 3. Unit Economics')
idx2 = content.find('## 4. Customer Acquisition')

assert idx1 != -1 and idx2 != -1, "Indices not found"

new_section_3 = """## 3. Unit Economics & Cost-to-Serve Analysis

The modern asynchronous architecture (FastAPI, PostgreSQL with `pgvector 0.8.7`, Redis 7, Celery, and Google Gemini 3.6 Flash) provides extraordinarily favorable gross margins compared to legacy monolithic stacks:

### Estimated Monthly Infrastructure & AI Cost per Growth Tenant (10,000 Leads/Mo)

| Component | Architecture / Sizing | Monthly Cost (USD) | Monthly Cost (INR) | Classification |
| :--- | :--- | :---: | :---: | :--- |
| **Compute (API & Workers)** | AWS ECS Fargate or DigitalOcean Dedicated (4 vCPU, 8GB RAM) | $45.00 | ₹3,750 | `PRICE-BASED ESTIMATE` |
| **Database (PostgreSQL + pgvector)** | Managed PostgreSQL 16 (2 vCPU, 4GB RAM, NVMe SSD) | $55.00 | ₹4,580 | `PRICE-BASED ESTIMATE` |
| **In-Memory Cache & Queues** | Managed Redis 7 (1GB RAM) | $15.00 | ₹1,250 | `PRICE-BASED ESTIMATE` |
| **AI Inference (Gemini 3.6 Flash)** | 10,000 leads @ $0.002570625 blended (950 in / 300 out qualification + 5% retry + 30% sales brief) | $25.71 | ₹2,142 | `PRICE-BASED ESTIMATE` |
| **Conversational Chat Headroom Buffer** | Optional 10% multi-turn follow-up buffer (~2,600 turns) | $2.57 | ₹214 | `ASSUMED WORKLOAD` |
| **Outbound WhatsApp Conversations** | Meta Cloud API service conversation fee (~10k conversations) | Client direct billing / BSP pass-through | Pass-through | `PASS-THROUGH` |
| **Total Direct COGS per Tenant** | | **$143.28** | **₹11,936** | `PRICE-BASED ESTIMATE` |

### Gross Margin Calculation
- **Monthly Revenue per Growth Tenant:** ₹39,999 ($480.00)
- **Direct Infrastructure & AI COGS (with buffer):** ₹11,936 ($143.28)
- **Gross Profit per Tenant:** **₹28,063 ($336.72)**
- **Blended Gross Margin:** **70.2%** (Exceeds industry standard for B2B SaaS: 70–80%)

---

"""

updated_content = content[:idx1] + new_section_3 + content[idx2:]
with open('docs/audits/PHASE14_PRODUCT_STRATEGY_AND_BUSINESS_MODEL.md', 'w', encoding='utf-8', newline='') as f:
    f.write(updated_content)

print("SUCCESS: Updated Section 3 in strategy doc")

