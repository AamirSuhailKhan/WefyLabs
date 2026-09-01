"""
Knowledge Domain Events
========================
All 13 event types for the Knowledge Intelligence Platform.
Published via the existing DomainEventBus singleton.

Consumers:
  - Audit service (wildcard subscriber — all events auto-logged)
  - Observability metrics
  - Cache invalidation
  - Email/notification triggers (admin notifications)
"""


class KnowledgeEvents:
    UPLOADED = "KnowledgeUploaded"
    PARSED = "KnowledgeParsed"
    EXTRACTED = "KnowledgeExtracted"
    INDEXED = "KnowledgeIndexed"
    PUBLISHED = "KnowledgePublished"
    EXPIRED = "KnowledgeExpired"
    UPDATED = "KnowledgeUpdated"
    DELETED = "KnowledgeDeleted"
    CONFLICT_DETECTED = "KnowledgeConflictDetected"
    VERIFIED = "KnowledgeVerified"
    REJECTED = "KnowledgeRejected"
    REINDEXED = "KnowledgeReindexed"
    FEEDBACK_RECEIVED = "KnowledgeFeedbackReceived"
