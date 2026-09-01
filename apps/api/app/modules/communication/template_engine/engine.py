"""
Template Engine — Versioned Message Template Rendering
========================================================
Renders MessageTemplate records with variable injection.
Supports: WhatsApp Business templates, Email templates, SMS templates.

Features:
- Variable injection ({{customer_name}}, {{property_name}}, etc.)
- Localization (language-aware template selection)
- Version management (fetch active version)
- A/B test group selection
- Usage tracking
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import MessageTemplate, TemplateVariable

logger = logging.getLogger(__name__)

# Regex for {{variable_name}} or {{1}} style placeholders
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class TemplateEngine:
    """
    Renders versioned templates with variable substitution.
    """

    async def render(
        self,
        template_name: str,
        organization_id: str,
        channel: str,
        variables: Dict[str, str],
        db: AsyncSession,
        language: str = "en",
        version: Optional[int] = None,
    ) -> Optional[str]:
        """
        Find template, inject variables, return rendered body.
        Returns None if template not found.
        """
        template = await self._find_template(
            db, organization_id, template_name, channel, language, version
        )
        if not template:
            logger.warning(
                f"[TemplateEngine] Template not found name={template_name} "
                f"channel={channel} org={organization_id}"
            )
            return None

        rendered = self._inject_variables(template.body, variables)

        # Track usage
        template.usage_count = (template.usage_count or 0) + 1
        await db.flush()

        logger.info(
            f"[TemplateEngine] Rendered template={template_name} "
            f"channel={channel} org={organization_id}"
        )
        return rendered

    async def render_with_header_footer(
        self,
        template_name: str,
        organization_id: str,
        channel: str,
        variables: Dict[str, str],
        db: AsyncSession,
        language: str = "en",
    ) -> Dict[str, Optional[str]]:
        """Render body, header, and footer separately (for WhatsApp templates)."""
        template = await self._find_template(
            db, organization_id, template_name, channel, language
        )
        if not template:
            return {"body": None, "header": None, "footer": None}

        return {
            "body": self._inject_variables(template.body, variables),
            "header": self._inject_variables(template.header or "", variables) or None,
            "footer": self._inject_variables(template.footer or "", variables) or None,
            "buttons": template.buttons,
        }

    async def get_variable_schema(
        self,
        template_name: str,
        organization_id: str,
        channel: str,
        db: AsyncSession,
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Return the variable schema for a template (for UI form generation)."""
        template = await self._find_template(
            db, organization_id, template_name, channel, language
        )
        if not template:
            return []

        stmt = select(TemplateVariable).where(
            TemplateVariable.template_id == template.id
        ).order_by(TemplateVariable.position)
        result = await db.execute(stmt)
        variables = result.scalars().all()

        return [
            {
                "position": v.position,
                "name": v.variable_name,
                "source": v.source,
                "source_field": v.source_field,
                "default": v.default_value,
                "required": v.is_required,
            }
            for v in variables
        ]

    async def create_template(
        self,
        organization_id: str,
        name: str,
        display_name: str,
        channel: str,
        body: str,
        db: AsyncSession,
        language: str = "en",
        category: str = "MARKETING",
        header: Optional[str] = None,
        footer: Optional[str] = None,
        buttons: Optional[Dict] = None,
        description: Optional[str] = None,
    ) -> MessageTemplate:
        """Create a new template (version 1)."""
        # Auto-detect variables in body
        placeholders = _PLACEHOLDER_RE.findall(body)

        template = MessageTemplate(
            organization_id=organization_id,
            name=name,
            display_name=display_name,
            channel=channel,
            body=body,
            header=header,
            footer=footer,
            buttons=buttons,
            language=language,
            category=category,
            description=description,
            version=1,
            is_active=True,
            approval_status="draft",
        )
        db.add(template)
        await db.flush()

        # Create variable definitions from auto-detected placeholders
        for idx, placeholder in enumerate(placeholders):
            var = TemplateVariable(
                template_id=template.id,
                position=idx + 1,
                variable_name=placeholder,
                source="lead",
                is_required=True,
            )
            db.add(var)

        await db.flush()
        return template

    # ─── Helpers ─────────────────────────────────────────────────────────────

    async def _find_template(
        self, db: AsyncSession, organization_id: str, name: str,
        channel: str, language: str = "en", version: Optional[int] = None
    ) -> Optional[MessageTemplate]:
        """Find the active template matching criteria."""
        stmt = select(MessageTemplate).where(
            MessageTemplate.organization_id == organization_id,
            MessageTemplate.name == name,
            MessageTemplate.channel == channel,
            MessageTemplate.language == language,
            MessageTemplate.is_active == True,
            MessageTemplate.approval_status.in_(["approved", "draft"]),
        )
        if version is not None:
            stmt = stmt.where(MessageTemplate.version == version)
        else:
            stmt = stmt.order_by(MessageTemplate.version.desc())

        result = await db.execute(stmt)
        return result.scalars().first()

    def _inject_variables(self, template_body: str, variables: Dict[str, str]) -> str:
        """Replace {{variable_name}} placeholders with values."""
        if not template_body:
            return ""

        def replacer(match):
            key = match.group(1)
            return variables.get(key, match.group(0))  # Keep original if missing

        return _PLACEHOLDER_RE.sub(replacer, template_body)
