"""One AI Gateway for business-critical model calls.

Business modules must not import provider SDKs. Invalid or missing credentials
return a truthful FAILED / CONFIGURATION_REQUIRED result — never synthetic success.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.tenancy.scope import as_organization_uuid, require_organization_id
from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter
from app.modules.ai_agent.llm_router.base_adapter import LLMResponse
from app.modules.ai_agent.llm_router.router import LLMRouter

logger = logging.getLogger("wefylabs.ai_gateway")


class OperationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEGRADED = "DEGRADED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


@dataclass
class AIGatewayResult:
    status: OperationStatus
    content: str = ""
    structured: Optional[Dict[str, Any]] = None
    provider: str = ""
    model: str = ""
    request_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == OperationStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "content": self.content,
            "structured": self.structured,
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "ai_generated": self.success,
        }


class ModelRouter:
    """Policy-driven model selector.

    Routing Policy:
    - LIGHT tasks (extraction, classification, intent): use the fast flash model.
      Optimizes cost and latency for high-frequency inference.
    - HEAVY tasks (generation, planning, tool orchestration): use the full model.
      Prioritizes reasoning quality for customer-facing output.
    - Structured output: always use a model known to support JSON mode.
    - Tool calling: always escalate to full model (requires function-calling support).

    The concrete model names are resolved from settings so they can be changed
    at runtime via environment variables without code changes.
    """

    # Task types that benefit from a lighter, faster model
    _LIGHT_TASKS: frozenset = frozenset({
        "extraction",
        "classification",
        "intent_detection",
        "entity_recognition",
        "qualification",  # extraction phase — fact parsing
        "summarization",
    })

    def select(self, task_type: str, *, structured: bool = False, tool_calling: bool = False) -> str:
        from app.config import settings
        full_model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"

        # Tool calling always requires the full model
        if tool_calling:
            return full_model

        # Light tasks use the flash model when available
        light_model = getattr(settings, "GEMINI_LIGHT_MODEL", None) or full_model
        if task_type in self._LIGHT_TASKS and not tool_calling:
            return light_model

        return full_model


class AIGateway:
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.model_router = ModelRouter()

    def _build_router(self, model: str) -> Optional[LLMRouter]:
        from app.config import settings
        api_key = (getattr(settings, "GEMINI_API_KEY", None) or "").strip()
        if not api_key or api_key.startswith("placeholder") or api_key == "mock-gemini-key":
            return None
        primary = GoogleAdapter(api_key=api_key, model=model)
        return LLMRouter(primary=primary)

    async def complete(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        feature: str,
        messages: List[Dict[str, str]],
        actor_id: Optional[str] = None,
        task_type: str = "completion",
        tools: Optional[List[Dict[str, Any]]] = None,
        expect_json: bool = False,
        prompt_version: str = "v1",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> AIGatewayResult:
        request_id = str(uuid.uuid4())
        try:
            org_uuid = require_organization_id(organization_id)
        except Exception as exc:
            return AIGatewayResult(
                status=OperationStatus.UNAUTHORIZED,
                request_id=request_id,
                error_code="ORGANIZATION_CONTEXT_REQUIRED",
                error_message=str(exc),
            )

        model = self.model_router.select(task_type, structured=expect_json, tool_calling=bool(tools))
        router = self._build_router(model)
        if router is None:
            result = AIGatewayResult(
                status=OperationStatus.CONFIGURATION_REQUIRED,
                request_id=request_id,
                provider="google",
                model=model,
                error_code="CONFIGURATION_REQUIRED",
                error_message="GEMINI_API_KEY is not configured for production AI calls.",
            )
            await self._persist(org_uuid, actor_id, feature, task_type, result, prompt_version)
            return result

        llm: LLMResponse = await router.route(
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not llm.success:
            status = OperationStatus.PROVIDER_UNAVAILABLE
            if llm.error and "not configured" in llm.error.lower():
                status = OperationStatus.CONFIGURATION_REQUIRED
            result = AIGatewayResult(
                status=status,
                request_id=request_id,
                provider=llm.provider,
                model=llm.model,
                input_tokens=llm.prompt_tokens,
                output_tokens=llm.completion_tokens,
                latency_ms=llm.latency_ms,
                cost=llm.cost_usd,
                error_code=status.value,
                error_message=llm.error,
            )
            await self._persist(org_uuid, actor_id, feature, task_type, result, prompt_version)
            return result

        structured = None
        content = llm.content or ""
        if expect_json:
            structured = self._parse_json(content)
            if structured is None:
                result = AIGatewayResult(
                    status=OperationStatus.VALIDATION_ERROR,
                    content=content,
                    request_id=request_id,
                    provider=llm.provider,
                    model=llm.model,
                    input_tokens=llm.prompt_tokens,
                    output_tokens=llm.completion_tokens,
                    latency_ms=llm.latency_ms,
                    cost=llm.cost_usd,
                    error_code="INVALID_STRUCTURED_OUTPUT",
                    error_message="Model output was not valid JSON and cannot execute business actions.",
                    tool_calls=llm.tool_calls,
                )
                await self._persist(org_uuid, actor_id, feature, task_type, result, prompt_version)
                return result

        result = AIGatewayResult(
            status=OperationStatus.SUCCESS,
            content=content,
            structured=structured,
            provider=llm.provider,
            model=llm.model,
            request_id=request_id,
            input_tokens=llm.prompt_tokens,
            output_tokens=llm.completion_tokens,
            latency_ms=llm.latency_ms,
            cost=llm.cost_usd,
            tool_calls=llm.tool_calls,
        )
        await self._persist(org_uuid, actor_id, feature, task_type, result, prompt_version)
        return result

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def _persist(
        self,
        organization_id: uuid.UUID,
        actor_id: Optional[str],
        feature: str,
        task_type: str,
        result: AIGatewayResult,
        prompt_version: str,
    ) -> None:
        if self.db is None:
            return
        try:
            from app.models.ai_foundation_models import AIRequestRecord

            record = AIRequestRecord(
                organization_id=organization_id,
                actor_id=actor_id,
                feature=feature,
                task_type=task_type,
                model=result.model,
                provider=result.provider,
                prompt_version=prompt_version,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                cost=result.cost,
                status=result.status.value,
                error_code=result.error_code,
                tool_count=len(result.tool_calls),
                request_id=result.request_id,
            )
            self.db.add(record)
            await self.db.flush()
        except Exception as exc:
            logger.warning("[AIGateway] failed to persist AIRequestRecord: %s", exc)
