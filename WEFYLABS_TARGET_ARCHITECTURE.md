# WEFYLABS TARGET ARCHITECTURE

```text
Channels (web form / one verified messaging channel)
  → Ingestion + idempotency
  → Identity & Deduplication [tenant scoped]
  → Canonical Lead + Conversation timeline
  → Property authority + deterministic matching
  → AI Gateway (context, retrieval, policy, tools, audit)
  → Human approval / execution adapter
  → CRM, Calendar, Messaging
  → Transactional Outbox → Celery consumers
  → Revenue funnel + evaluation
```

## Single Sources of Truth

| Domain | Authority |
|---|---|
| Identity | canonical contact/lead identity service with auditable merge |
| Lead state | one canonical lead lifecycle/pipeline |
| Property facts, price, availability | verified property listing/inventory owner; never LLM output |
| Conversation | unified conversation/message envelope with channel links |
| Appointment | scheduling meeting + external provider event reconciliation |
| Permissions | authenticated principal + organization membership + policy |
| Billing | verified payment-provider webhook state |
| Audit | append-only audit/event records |

## Shared AI Brain

Centralize context construction, retrieval with citations, tenant scoping, tool permissions, policy, structured validation, prompt versions, LLM usage, evaluation and audit logging. Preserve deterministic qualification/matching as the fallback; the LLM proposes language or structured candidates but never authoritatively mutates transactional facts.

## Dependency Graph

```text
Principal + Organization
  → Identity + canonical timeline
  → Property authority
  → deterministic qualification/matching
  → governed AI + handoff
  → appointment/outreach execution
  → evented revenue funnel
  → outcomes/evaluation
```
