"""
Pydantic v2 Data Transfer Objects for AI Follow-Up and Autonomous Lead Nurturing Engine
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class FollowUpPolicyDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    organization_id: str
    autonomy_level: str = "LEVEL_3"
    allowed_channels: List[str] = ["WHATSAPP", "EMAIL"]
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "08:00"
    working_days: List[int] = [1, 2, 3, 4, 5, 6]
    max_messages_per_day: int = 2
    max_messages_per_week: int = 5
    max_consecutive_no_reply: int = 3
    min_hours_between_msgs: int = 18
    require_approval_high_value: bool = True
    high_value_threshold_aed: float = 5000000.0


class UpdatePolicyDTO(BaseModel):
    autonomy_level: Optional[str] = None
    allowed_channels: Optional[List[str]] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    max_messages_per_day: Optional[int] = None
    max_messages_per_week: Optional[int] = None
    max_consecutive_no_reply: Optional[int] = None
    min_hours_between_msgs: Optional[int] = None
    require_approval_high_value: Optional[bool] = None
    high_value_threshold_aed: Optional[float] = None


class SequenceStepDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_number: int
    delay_hours: int = 24
    preferred_channel: str = "WHATSAPP"
    reason_type: str = "UNANSWERED_INQUIRY"
    message_goal: str
    template_key: Optional[str] = None
    custom_prompt: Optional[str] = None
    require_human_approval: bool = False


class SequenceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    target_lifecycle_state: str
    is_active: bool = True
    steps: List[SequenceStepDTO] = []


class CreateSequenceDTO(BaseModel):
    name: str
    description: Optional[str] = None
    target_lifecycle_state: str
    steps: List[SequenceStepDTO] = []


class UpdateSequenceDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_lifecycle_state: Optional[str] = None
    is_active: Optional[bool] = None
    steps: Optional[List[SequenceStepDTO]] = None


class NextBestActionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommended_action: str
    action_reason: str
    priority_score: float
    confidence: float
    expected_outcome: Optional[str] = None
    target_property_id: Optional[str] = None


class FollowUpExecutionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    organization_id: str
    broker_id: str
    channel: str
    reason_type: str
    status: str
    scheduled_for_utc: datetime
    executed_at: Optional[datetime] = None
    recipient_identifier: str
    message_subject: Optional[str] = None
    message_body: str
    grounded_facts: List[Dict[str, Any]] = []
    suppression_reason: Optional[str] = None
    response_detected: bool = False


class FollowUpEvaluationResponseDTO(BaseModel):
    lead_id: str
    lifecycle_state: str
    is_eligible: bool
    is_suppressed: bool
    suppression_reason: Optional[str] = None
    selected_channel: Optional[str] = None
    optimal_time_utc: Optional[datetime] = None
    next_best_action: NextBestActionDTO
    draft_message: Optional[FollowUpExecutionDTO] = None


class LeadFollowUpStatusDTO(BaseModel):
    lead_id: str
    lifecycle_state: str
    is_suppressed: bool
    fatigue_score: float
    consecutive_no_replies: int
    next_best_action: NextBestActionDTO
    scheduled_executions: List[FollowUpExecutionDTO] = []
    active_sequence_enrollment: Optional[Dict[str, Any]] = None


class FollowUpAnalyticsDTO(BaseModel):
    organization_id: str
    total_evaluations: int
    total_dispatched: int
    total_suppressed: int
    delivery_rate_pct: float
    response_rate_pct: float
    average_fatigue_score: float
    channel_distribution: Dict[str, int]
    top_suppression_reasons: Dict[str, int]


class FollowUpRuleDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    enabled: bool = True
    trigger: str
    delay_minutes: int = 0
    action: str
    action_config: Dict[str, Any] = {}
    conditions: Dict[str, Any] = {}
    priority: str = "normal"
    max_runs: int = 1
    cooldown_hours: int = 24
    created_at: Optional[datetime] = None


class CreateFollowUpRuleDTO(BaseModel):
    name: str
    trigger: str
    action: str
    delay_minutes: int = 0
    action_config: Dict[str, Any] = {}
    conditions: Dict[str, Any] = {}
    priority: str = "normal"
    max_runs: int = 1
    cooldown_hours: int = 24


class UpdateFollowUpRuleDTO(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    trigger: Optional[str] = None
    action: Optional[str] = None
    delay_minutes: Optional[int] = None
    action_config: Optional[Dict[str, Any]] = None
    conditions: Optional[Dict[str, Any]] = None
    priority: Optional[str] = None
    max_runs: Optional[int] = None
    cooldown_hours: Optional[int] = None


class SnoozeTaskDTO(BaseModel):
    snooze_until: datetime
    reason: Optional[str] = "Snoozed by Broker"


class RescheduleTaskDTO(BaseModel):
    new_due_at: datetime
    reason: Optional[str] = "Rescheduled by Broker"


class DailyBriefingDTO(BaseModel):
    due_today_count: int
    overdue_count: int
    hot_uncontacted_count: int
    meetings_today_count: int
    top_priority_lead: Optional[Dict[str, Any]] = None
    summary_text: str
    generated_at: str
