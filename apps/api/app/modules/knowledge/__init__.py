"""
BeetleLabs Enterprise Knowledge Intelligence Platform
======================================================
Multi-tenant, production-grade knowledge engine powering:
  - AI Sales Agent
  - Property Recommendation Engine
  - AI Follow-up Engine
  - Customer-facing Chat (Website / WhatsApp / Telegram)
  - CRM Intelligence

Architecture principle:
  RAG = retrieval layer only. Never the source of truth.
  Live price/availability → always from transactional services.
  Only PUBLISHED knowledge serves customer-facing AI.
  Every fact carries full provenance and tenant isolation.
"""
