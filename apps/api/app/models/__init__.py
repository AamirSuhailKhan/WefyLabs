from app.database import Base
from app.models.broker import Broker
from app.models.user import User
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.models.follow_up import FollowUp
from app.models.subscription import Subscription
from app.models.crm_models import (
    PipelineStage, LeadNote, LeadTag, LeadTagAssignment,
    Task, Meeting, Contact, Activity,
    Notification, ApiKey, CustomField
)
from app.models.developer_models import DeveloperApiKey, WebhookSubscription
from app.models.organization import (
    Organization, OrganizationMember,
    Workspace, Department,
    RoleModel, PermissionModel, RolePermission
)
from app.models.invitation_models import PasswordResetToken, OrganizationInvitation
from app.models.audit_log import AuditLog
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin, TenantMixin, AuditMixin
from app.models.communication_models import (
    UnifiedConversation, UnifiedMessage, CallDetailRecord,
    # Part 6 — Enterprise Omnichannel Communication Engine
    OmnichannelConversation, ConversationChannelLink, ConversationControl,
    ChannelMessage, MessageAttachment, DeliveryStatusRecord,
    MessageTemplate, TemplateVariable, ProviderCredential,
    OutboundQueue, InboundQueue, TypingEvent, PresenceRecord,
)
from app.models.property_models import PropertyListing, PropertyMedia, PropertyPriceHistory, LeadPropertyInterest
from app.models.command_center_models import CommandCenterDismissal
from app.models.onboarding_models import OnboardingState, TenantActivation, DemoSession
from app.models.transaction_models import DealTransaction, DealMilestone, DealPaymentSchedule

from app.models.ingestion_models import ConnectorConfig, LeadImportBatch, LeadImportItem, OriginalPayload, IngestionLog
from app.models.enrichment_models import LeadEnrichment, ConfidenceScore, EnrichmentHistory, EnrichmentSource, EnrichmentProvider
from app.models.identity_models import (
    Identity, IdentityLink, IdentityAlias, IdentityHistory, IdentityConflict,
    DuplicateCandidate, MergeOperation, MergeHistory, SimilarityScore, ManualReview
)
from app.models.lead_intelligence_models import (
    LeadIntelligenceProfile, LeadPrediction, LeadRecommendation,
    PredictionHistory, ScoringRule, MLModelVersion,
    FeatureVector, PredictionExplanation, RevenueForecast
)
from app.models.agent_models import (
    AgentSession, ConversationState, QualificationProfile, AgentMemory,
    ConversationSummary, ToolExecution, PromptVersion, DecisionRecord,
    Escalation, LLMUsage, AgentConfiguration
)

from app.models.recommendation_models import (
    BuyerProfile, BuyerPreference, BuyerConstraint, BuyerPreferenceEvidence,
    PropertyFeatureVector, Recommendation, RecommendationItem, RecommendationScore,
    RecommendationExplanation, RecommendationFeedback, RecommendationExperiment,
    RecommendationModelVersion, RecommendationFeature, RecommendationSimulation,
    RecommendationComparison, RecommendationHistory, RecommendationConfiguration,
    RecommendationBusinessRule
)

# ─── Knowledge Intelligence Platform ─────────────────────────────────────────
from app.models.knowledge_models import (
    KnowledgeSource, KnowledgeDocument, KnowledgeDocumentVersion,
    KnowledgeChunk, KnowledgeEmbedding, KnowledgeFact,
    KnowledgeConflict, KnowledgeVerification, KnowledgePermission,
    KnowledgeCollection, KnowledgeCollectionDocument, KnowledgeIndex,
    KnowledgeQuery, KnowledgeRetrieval, KnowledgeCitation,
    KnowledgeFeedback, KnowledgeEvaluation, KnowledgeProvider,
    KnowledgeProcessingJob, KnowledgeDeletionJob, KnowledgeFreshnessPolicy,
)

# ─── Part 8 — AI Follow-Up & Autonomous Lead Nurturing Engine ─────────────────
from app.models.follow_up_models import (
    FollowUpPolicy, FollowUpSequence, FollowUpSequenceStep, FollowUpEnrollment,
    FollowUpExecution, FollowUpDecision, CommunicationConsent, ContactFatigue,
    NextBestAction, FollowUpAttribution, FollowUpRule, FollowUpAutomationEvent
)

# ─── Part 9 — Calendar, Meeting & Scheduling Intelligence Engine ──────────────
from app.models.calendar_models import (
    CalendarAccount, CalendarConnection, AvailabilityRule, MeetingHold,
    Meeting as SchedulingMeeting, Viewing, MeetingPreparationBrief,
    MeetingOutcome, NoShowPrediction, MeetingReminder, CalendarEvent,
    CalendarConflict
)

# ─── Part 10 — CRM Intelligence & Autonomous Sales Operations Engine ──────────
from app.models.crm_intelligence_models import (
    LeadHealthSnapshot, LeadRisk, SlaPolicy, SlaInstance, SlaBreach,
    PipelineHealthSnapshot, OpportunityHealthSnapshot, AgentWorkloadSnapshot,
    AnomalyEvent, SalesInsight, InsightDismissal,
    OperationalNextBestAction, ActionExecution,
    ManagerDailyBrief, AgentDailyBrief
)

# ─── Part 11 — Predictive Analytics, Conversion Forecasting & MLOps Engine ────
from app.models.predictive_models import (
    PredictionModelEntity, PredictionModelVersionEntity,
    PredictionFeatureDefinition, PredictionTrainingDataset,
    PredictionInferenceRecord, PredictionOutcomeRecord,
    PredictionCalibrationRecord, PredictionDriftRecord,
    ForecastSnapshotRecord, ForecastScenarioRecord,
    DemandPredictionSnapshot, SalesCyclePredictionSnapshot
)

# ─── Part 12 — Workflow Automation & Autonomous Revenue Operations Engine ─────
from app.models.workflow_models import (
    WorkflowDefinition, WorkflowVersion, WorkflowInstance,
    WorkflowNodeExecution, WorkflowApproval, WorkflowWaitState,
    WorkflowTemplate, WorkflowExecutionLock
)

# ─── Part 14 — Global Multi-Country Infrastructure & Localization Engine ────────
from app.models.global_models import (
    Country, Market, MarketConfiguration, CountryConfigurationVersion,
    Currency, ExchangeRate, ExchangeRateSnapshot,
    HolidayCalendar, Holiday,
    Translation,
    PropertySchema, PropertyField,
    ProviderConfiguration, ProviderHealth,
    CompliancePolicy, ConsentRecord,
    DataResidencyPolicy,
    RegionalPipeline, RegionalPipelineStage,
    MarketFeatureFlag, MarketRollout,
)

# ─── Part 21.1 — Real-Estate Lead Acquisition Foundation ────────────────────
from app.models.acquisition_models import (
    LeadSource, LeadCampaign, CampaignPropertyLink,
    LeadAcquisitionEvent, LeadProspect, SourceAttribution,
    AcquisitionChannel, LeadIntent, TransactionType,
    ConsentStatus, ProspectStatus, DuplicateMatchStatus,
)

# ─── Part 21.2 — Real-Estate Lead Discovery Engine ──────────────────────────
from app.models.discovery_models import (
    DiscoverySource, DiscoveryCampaign, DiscoveryRun,
    DiscoveryCandidate, DiscoveryEvidence, DiscoverySignal,
    DiscoverySourceType, ProviderStatus, DiscoveryCampaignStatus,
    DiscoveryRunStatus, CandidateStatus, ComplianceStatus, SignalType,
)

# ─── Part 21.2A — AI Prospect Intelligence Engine ───────────────────────────
from app.models.prospect_intelligence_models import (
    ProspectIntelligence, ProspectIntelligenceHistory,
    ProspectType, TransactionIntent, TimelineCategory,
    FinancingType, PurposeCategory, UrgencyLevel,
    SalesReadiness, IntelligenceStatus, NextBestActionType,
)

# ─── Part 13 — AI Memory & Customer Intelligence Engine ───────────────────────
from app.models.memory_models import (
    MemoryRecord, MemoryVersion, MemoryEvidence,
    MemoryObjection, MemoryPropertyFeedback, MemoryAuditLog,
    MemoryRetentionPolicy, MemoryDeletionRequest
)

# ─── Part 21.4.1 — AI Lead Qualification Domain Foundation ───────────────────
from app.models.qualification_models import (
    QualificationFact, QualificationConflict, QualificationRequirementPolicy,
    QualificationAuditEvent, QualificationSnapshotRecord,
    QualificationState, QualificationIntent, QualificationBuyerType,
    QualificationTimeline, QualificationFinancing, FactValueCategory,
    EvidenceSourceType, FactStatus, ConflictStatus,
    QualificationAuditActorType, QualificationAuditEventType,
)

__all__ = [
    # Core
    "Base",
    "Broker",
    "User",
    "Lead",
    "Conversation",
    "Score",
    "FollowUp",
    "Subscription",
    # Ingestion & Enrichment
    "ConnectorConfig",
    "LeadImportBatch",
    "LeadImportItem",
    "OriginalPayload",
    "IngestionLog",
    "LeadEnrichment",
    "ConfidenceScore",
    "EnrichmentHistory",
    "EnrichmentSource",
    "EnrichmentProvider",
    # Identity Resolution
    "Identity",
    "IdentityLink",
    "IdentityAlias",
    "IdentityHistory",
    "IdentityConflict",
    "DuplicateCandidate",
    "MergeOperation",
    "MergeHistory",
    "SimilarityScore",
    "ManualReview",
    # Lead Intelligence & Revenue
    "LeadIntelligenceProfile",
    "LeadPrediction",
    "LeadRecommendation",
    "PredictionHistory",
    "ScoringRule",
    "MLModelVersion",
    "FeatureVector",
    "PredictionExplanation",
    "RevenueForecast",
    # Autonomous AI Agent
    "AgentSession",
    "ConversationState",
    "QualificationProfile",
    "AgentMemory",
    "ConversationSummary",
    "ToolExecution",
    "PromptVersion",
    "DecisionRecord",
    "Escalation",
    "LLMUsage",
    "AgentConfiguration",
    # CRM Entities
    "PipelineStage",
    "LeadNote",
    "LeadTag",
    "LeadTagAssignment",
    "Task",
    "Meeting",
    "Contact",
    "Activity",
    "Notification",
    "ApiKey",
    "CustomField",
    "WebhookSubscription",
    "DeveloperApiKey",
    # Organization & RBAC
    "Organization",
    "OrganizationMember",
    "OrganizationInvitation",
    "PasswordResetToken",
    "Workspace",
    "Department",
    "RoleModel",
    "PermissionModel",
    "RolePermission",
    # Onboarding, Activation & Demo (Part 31)
    "OnboardingState",
    "TenantActivation",
    "DemoSession",
    "CommandCenterDismissal",
    # Audit & Infrastructure
    "AuditLog",
    "TimestampMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "AuditMixin",
    # Communication (Legacy)
    "UnifiedConversation",
    "UnifiedMessage",
    "CallDetailRecord",
    # Communication (Part 6 — Enterprise Omnichannel)
    "OmnichannelConversation",
    "ConversationChannelLink",
    "ConversationControl",
    "ChannelMessage",
    "MessageAttachment",
    "DeliveryStatusRecord",
    "MessageTemplate",
    "TemplateVariable",
    "ProviderCredential",
    "OutboundQueue",
    "InboundQueue",
    "TypingEvent",
    "PresenceRecord",
    # Property & Deals
    "PropertyListing",
    "PropertyMedia",
    "PropertyPriceHistory",
    "DealTransaction",
    "DealMilestone",
    "DealPaymentSchedule",
    # Workflows
    "WorkflowDefinition",
    "WorkflowExecution",
    # Part 8 — AI Follow-Up & Autonomous Lead Nurturing Engine
    "FollowUpPolicy",
    "FollowUpSequence",
    "FollowUpSequenceStep",
    "FollowUpEnrollment",
    "FollowUpExecution",
    "FollowUpDecision",
    "CommunicationConsent",
    "ContactFatigue",
    "NextBestAction",
    "FollowUpAttribution",
    "FollowUpRule",
    "FollowUpAutomationEvent",
    # Part 9 — Calendar, Meeting & Scheduling Intelligence Engine
    "CalendarAccount",
    "CalendarConnection",
    "AvailabilityRule",
    "MeetingHold",
    "SchedulingMeeting",
    "Viewing",
    "MeetingPreparationBrief",
    "MeetingOutcome",
    "NoShowPrediction",
    "MeetingReminder",
    "CalendarEvent",
    "CalendarConflict",
    # Part 10 — CRM Intelligence & Autonomous Sales Operations Engine
    "LeadHealthSnapshot",
    "LeadRisk",
    "SlaPolicy",
    "SlaInstance",
    "SlaBreach",
    "PipelineHealthSnapshot",
    "OpportunityHealthSnapshot",
    "AgentWorkloadSnapshot",
    "AnomalyEvent",
    "SalesInsight",
    "InsightDismissal",
    "OperationalNextBestAction",
    "ActionExecution",
    "ManagerDailyBrief",
    "AgentDailyBrief",
    # Part 11 — Predictive Analytics, Conversion Forecasting & MLOps Engine
    "PredictionModelEntity",
    "PredictionModelVersionEntity",
    "PredictionFeatureDefinition",
    "PredictionTrainingDataset",
    "PredictionInferenceRecord",
    "PredictionOutcomeRecord",
    "PredictionCalibrationRecord",
    "PredictionDriftRecord",
    "ForecastSnapshotRecord",
    "ForecastScenarioRecord",
    "DemandPredictionSnapshot",
    "SalesCyclePredictionSnapshot",
    # Part 12 — Workflow Automation & Autonomous Revenue Operations Engine
    "WorkflowDefinition",
    "WorkflowVersion",
    "WorkflowInstance",
    "WorkflowNodeExecution",
    "WorkflowApproval",
    "WorkflowWaitState",
    "WorkflowTemplate",
    "WorkflowExecutionLock",
    # Part 13 — AI Memory & Customer Intelligence Engine
    "MemoryRecord",
    "MemoryVersion",
    "MemoryEvidence",
    "MemoryObjection",
    "MemoryPropertyFeedback",
    "MemoryAuditLog",
    "MemoryRetentionPolicy",
    "MemoryDeletionRequest",
    # Part 14 — Global Multi-Country Infrastructure & Localization Engine
    "Country",
    "Market",
    "MarketConfiguration",
    "CountryConfigurationVersion",
    "Currency",
    "ExchangeRate",
    "ExchangeRateSnapshot",
    "HolidayCalendar",
    "Holiday",
    "Translation",
    "PropertySchema",
    "PropertyField",
    "ProviderConfiguration",
    "ProviderHealth",
    "CompliancePolicy",
    "ConsentRecord",
    "DataResidencyPolicy",
    "RegionalPipeline",
    "RegionalPipelineStage",
    "MarketFeatureFlag",
    "MarketRollout",
    # Part 21.1 — Real-Estate Lead Acquisition Foundation
    "LeadSource",
    "LeadCampaign",
    "CampaignPropertyLink",
    "LeadAcquisitionEvent",
    "LeadProspect",
    "SourceAttribution",
    # Part 21.2 — Real-Estate Lead Discovery Engine
    "DiscoverySource",
    "DiscoveryCampaign",
    "DiscoveryRun",
    "DiscoveryCandidate",
    "DiscoveryEvidence",
    "DiscoverySignal",
    # Part 21.2A — AI Prospect Intelligence Engine
    "ProspectIntelligence",
    "ProspectIntelligenceHistory",
    "ProspectType",
    "TransactionIntent",
    "TimelineCategory",
    "FinancingType",
    "PurposeCategory",
    "UrgencyLevel",
    "SalesReadiness",
    "IntelligenceStatus",
    "NextBestActionType",
    # Part 21.4.1 — AI Lead Qualification Domain Foundation
    "QualificationFact",
    "QualificationConflict",
    "QualificationRequirementPolicy",
    "QualificationAuditEvent",
    "QualificationSnapshotRecord",
    "QualificationState",
    "QualificationIntent",
    "QualificationBuyerType",
    "QualificationTimeline",
    "QualificationFinancing",
    "FactValueCategory",
    "EvidenceSourceType",
    "FactStatus",
    "ConflictStatus",
    "QualificationAuditActorType",
    "QualificationAuditEventType",
    # Part 21.8 — AI Autonomous Sales Loop & Event-Driven Orchestration Engine
    "SalesLoopEvent",
    "SalesLoopAuditEntry",
    "SalesLoopDeadLetter",
    "LeadAutomationState",
    # Part 23.4 — Production-Grade Razorpay Payments & Billing
    "PaymentOrder",
    "PaymentTransaction",
    "PaymentRefund",
    "PaymentWebhookEvent",
    "PaymentAuditLog",
    "PaymentStatus",
    "RefundStatus",
    "WebhookEventStatus",
]

# ─── Part 21.8 — AI Autonomous Sales Loop & Event-Driven Orchestration Engine ─
from app.modules.autonomous_loop.models import (
    SalesLoopEvent,
    SalesLoopAuditEntry,
    SalesLoopDeadLetter,
    LeadAutomationState,
)

# ─── Part 23.4 — Production-Grade Razorpay Payments & Billing ─────────────────
from app.models.payment_models import (
    PaymentOrder,
    PaymentTransaction,
    PaymentRefund,
    PaymentWebhookEvent,
    PaymentAuditLog,
    PaymentStatus,
    RefundStatus,
    WebhookEventStatus,
)

# ─── Part 25 — Enterprise AI Copilot Operating System ─────────────────────────
from app.models.copilot_models import (
    CopilotConversation,
    CopilotMessage,
)

# ─── Part 35 — AI Real Estate Revenue Autopilot ───────────────────────────────
from app.models.revenue_autopilot_models import (
    RevenueOpportunity,
    RevenueFeedbackLog,
)

__all__ = __all__ + [
    "CopilotConversation",
    "CopilotMessage",
    "RevenueOpportunity",
    "RevenueFeedbackLog",
]

# ─── Part 11 — Revenue Intelligence Layer ──────────────────────────────────────
from app.models.revenue_intelligence_models import (
    RevenueFunnelSnapshot,
    RevenueLeakageEvent,
)

__all__ = __all__ + [
    "RevenueFunnelSnapshot",
    "RevenueLeakageEvent",
]

# ─── Part 17 — Enterprise Production Runtime (Transactional Outbox) ─────────
from app.models.outbox_models import (
    OutboxEvent,
    OutboxStatus,
)

__all__ = __all__ + [
    "OutboxEvent",
    "OutboxStatus",
]


# ─── Part 18 — Real Estate Deal, Booking & Transaction OS ────────────────────
from app.models.deal_models import (
    DealStage,
    Deal,
    DealStageHistory,
    DealOffer,
    DealReservation,
    DealBooking,
    DealCommission,
    DealClosing,
    DealPostSale,
    DealDocument,
    DealApprovalRequest,
    DealCommercialAuditLog,
)

__all__ = __all__ + [
    "DealStage",
    "Deal",
    "DealStageHistory",
    "DealOffer",
    "DealReservation",
    "DealBooking",
    "DealCommission",
    "DealClosing",
    "DealPostSale",
    "DealDocument",
    "DealApprovalRequest",
    "DealCommercialAuditLog",
]

# ─── Part 19 — Real Estate Supply, Project, Unit Inventory & Channel Partner Network OS ─
from app.models.inventory_models import (
    # Status enums
    DeveloperStatus,
    ProjectStatus,
    UnitInventoryStatus,
    ChannelPartnerStatus,
    ChannelPartnerTier,
    PriceBookStatus,
    # Domain entities
    RealEstateDeveloper,
    RealEstateProject,
    ProjectPhase,
    ProjectBuilding,
    ProjectFloor,
    ProjectUnit,
    ProjectUnitStatusLog,
    ProjectPriceBook,
    PriceBookEntry,
    ProjectMedia,
    ChannelPartner,
    ChannelPartnerProjectAgreement,
    ChannelPartnerCommission,
    InventoryAvailabilitySnapshot,
)

__all__ = __all__ + [
    # Enums
    "DeveloperStatus",
    "ProjectStatus",
    "UnitInventoryStatus",
    "ChannelPartnerStatus",
    "ChannelPartnerTier",
    "PriceBookStatus",
    # Entities
    "RealEstateDeveloper",
    "RealEstateProject",
    "ProjectPhase",
    "ProjectBuilding",
    "ProjectFloor",
    "ProjectUnit",
    "ProjectUnitStatusLog",
    "ProjectPriceBook",
    "PriceBookEntry",
    "ProjectMedia",
    "ChannelPartner",
    "ChannelPartnerProjectAgreement",
    "ChannelPartnerCommission",
    "InventoryAvailabilitySnapshot",
]

# ─── Part 20 — Real Estate Marketing, Listing Distribution & Demand Generation OS ─
from app.models.marketing_models import (
    # Status constants
    CampaignObjective,
    CampaignStatus,
    ListingPublicationStatus,
    AssetStatus,
    AssetType,
    DistributionChannel,
    ApprovalDecision,
    LaunchStatus,
    # Domain entities
    MarketingCampaign,
    CampaignApproval,
    CampaignAuditLog,
    MarketingAsset,
    PropertyListingPublication,
    ListingDistribution,
    LandingPage,
    TrackingLink,
    CampaignEvent,
    ProjectLaunch,
    CampaignListingLink,
)

__all__ = __all__ + [
    "CampaignObjective",
    "CampaignStatus",
    "ListingPublicationStatus",
    "AssetStatus",
    "AssetType",
    "DistributionChannel",
    "ApprovalDecision",
    "LaunchStatus",
    "MarketingCampaign",
    "CampaignApproval",
    "CampaignAuditLog",
    "MarketingAsset",
    "PropertyListingPublication",
    "ListingDistribution",
    "LandingPage",
    "TrackingLink",
    "CampaignEvent",
    "ProjectLaunch",
    "CampaignListingLink",
]
