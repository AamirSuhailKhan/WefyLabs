# BEETLELABS — PART 21.4.4 IMPLEMENTATION PLAN
## AI Qualification Conversation Engine

### 1. Existing Architecture Discovered
- **Part 21.4.1 (Foundation)**: `QualificationFact`, `QualificationConflict`, `QualificationRequirementPolicy`, `QualificationAuditEvent`, `QualificationSnapshotRecord`, enums (`QualificationState`, `QualificationIntent`, `QualificationBuyerType`, `QualificationTimeline`, `QualificationFinancing`, `FactValueCategory`, `EvidenceSourceType`, `FactStatus`, `ConflictStatus`, `QualificationAuditActorType`, `QualificationAuditEventType`).
- **Part 21.4.2 (Extraction Engine)**: `QualificationFactExtractor` with prompt injection sanitization, decimal-safe currency normalizers, bedroom and location normalizers, calibrated confidence bands (HIGH, MEDIUM, LOW, UNKNOWN), multi-source priority (Human > Customer > CRM > AI), and provenance tracking.
- **Part 21.4.3 (Policy Engine)**: `DeterministicQualificationPolicyEngine` with `evaluate_detailed()` and `get_missing_info()`, `QUESTION_TEMPLATES`, separated completeness and confidence scoring, conflict escalations to `NEEDS_HUMAN_REVIEW`, and audit log persistence.
- **Part 21.3 (Property Recommendation)**: `PropertyRecommendationService` with candidate retrieval, hard constraint filtering, compatibility scoring, and real inventory grounding.
- **Communication & Conversation Models**: `Conversation` in `app/models/conversation.py`, `UnifiedMessage` and `ChannelMessage` in `app/models/communication_models.py`.

### 2. Existing Reusable Components
- `LeadQualificationDomainService` and `QualificationFactRepository`.
- `DeterministicQualificationPolicyEngine` and `QUESTION_TEMPLATES`.
- `QualificationFactExtractor` and `QualificationFactNormalizer`.
- `PropertyRecommendationService` (for inventory inquiries).
- `validate_prompt_injection` in `app.infrastructure.security.prompt_guard`.
- `GoogleAdapter` / `OpenAIAdapter` via LLM Router.

### 3. Missing Capabilities To Implement in Part 21.4.4
- `QualificationConversationState` domain representation.
- Next Question Selector prioritizing missing required/recommended fields with deduplication and fatigue controls.
- Natural Language Question Generation via LLM with strict output schema validation and deterministic fallback.
- Multi-turn conversation processing loop (customer message -> fact extraction -> fact persistence -> policy re-evaluation -> question selection or terminal state).
- Human Handoff triggers and structured reasons.
- Non-hallucinating property inquiry routing via Part 21.3.
- REST endpoints and frontend integration in `api-client.ts` and `LeadDrawer.tsx` / `ExtractedDataCard.tsx`.
- Complete test suite in `tests/test_part21_4_4_qualification_conversation.py`.

### 4. Database Impact
- **Zero Schema Migrations**: Reuses existing `qualification_facts`, `qualification_snapshots`, `qualification_audit_events`, and `conversations` tables. Alembic head remains at `merge_002_and_9999_heads`.

### 5. API Impact
- New endpoints added under `/api/v1/leads/{lead_id}/qualification/conversation/`:
  - `POST /start`
  - `POST /message`
  - `GET /state`

### 6. Frontend Impact
- Enhanced `api-client.ts` with conversation methods and TypeScript types.
- UI elements in `ExtractedDataCard.tsx` / `LeadDrawer.tsx` displaying live conversational qualification status, verified vs unknown facts, next best question, and human handoff indicators.

### 7. Test Strategy
- Dedicated suite `tests/test_part21_4_4_qualification_conversation.py` covering all 39 test scenarios.
- Regression testing across Parts 21.4.1, 21.4.2, 21.4.3, 21.3, and full backend regression suite.
- Production Next.js build verification and FastAPI route verification.
