"""
Indexing Document Adapters
===========================
Each adapter serializes a CRM entity into a standardized SearchDocument.
These live in the indexing layer — services never know the document schema.
"""
import hashlib
import json
from typing import Optional, Any, Dict
from app.modules.search.interfaces.provider_interface import SearchDocument


def _hash(doc: Dict[str, Any]) -> str:
    """Stable SHA-256 hash of a document for staleness detection."""
    raw = json.dumps(doc, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class LeadIndexAdapter:
    """Converts a Lead ORM row or dict into a SearchDocument."""

    @staticmethod
    def _val(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @classmethod
    def to_document(cls, lead: Any, organization_id: str) -> SearchDocument:
        lead_id = str(cls._val(lead, "id", ""))
        name = cls._val(lead, "name")
        phone = cls._val(lead, "phone", "")
        status = cls._val(lead, "status", "")
        pipeline_stage = cls._val(lead, "pipeline_stage", "")
        updated_at = str(cls._val(lead, "updated_at", ""))

        doc = SearchDocument({
            "id": lead_id,
            "entity_type": "lead",
            "entity_id": lead_id,
            "organization_id": organization_id,
            "display_title": name or phone or "Lead",
            "display_subtitle": f"{status} · {pipeline_stage}",
            "searchable_text": " ".join(filter(None, [name, phone, status, pipeline_stage])),
            "status": status,
            "score": cls._val(lead, "score"),
            "pipeline_stage": pipeline_stage,
            "phone": phone,
            "updated_at": updated_at,
        })
        doc["document_hash"] = _hash(doc)
        return doc


class PropertyIndexAdapter:
    """Converts a PropertyListing ORM row into a SearchDocument."""

    @staticmethod
    def to_document(prop: Any, organization_id: str) -> SearchDocument:
        doc = SearchDocument({
            "id": str(getattr(prop, "id", "")),
            "entity_type": "property",
            "entity_id": str(getattr(prop, "id", "")),
            "organization_id": organization_id,
            "display_title": getattr(prop, "title", ""),
            "display_subtitle": f"{getattr(prop, 'city', '')} · {getattr(prop, 'property_type', '')}",
            "searchable_text": " ".join(filter(None, [
                getattr(prop, "title", ""),
                getattr(prop, "city", ""),
                getattr(prop, "locality", ""),
                getattr(prop, "project_name", None) or "",
                getattr(prop, "property_type", ""),
            ])),
            "city": getattr(prop, "city", None),
            "locality": getattr(prop, "locality", None),
            "property_type": getattr(prop, "property_type", None),
            "price": float(getattr(prop, "price", 0)),
            "bedrooms": getattr(prop, "bedrooms", None),
            "status": getattr(prop, "status", None),
            "updated_at": str(getattr(prop, "updated_at", "")),
        })
        doc["document_hash"] = _hash(doc)
        return doc


class ContactIndexAdapter:
    """Converts a Contact ORM row into a SearchDocument."""

    @staticmethod
    def to_document(contact: Any, organization_id: str) -> SearchDocument:
        doc = SearchDocument({
            "id": str(getattr(contact, "id", "")),
            "entity_type": "contact",
            "entity_id": str(getattr(contact, "id", "")),
            "organization_id": organization_id,
            "display_title": getattr(contact, "name", ""),
            "display_subtitle": f"{getattr(contact, 'email', '') or ''} · {getattr(contact, 'contact_type', '')}",
            "searchable_text": " ".join(filter(None, [
                getattr(contact, "name", ""),
                getattr(contact, "email", None) or "",
                getattr(contact, "phone", None) or "",
                getattr(contact, "company", None) or "",
                getattr(contact, "contact_type", ""),
            ])),
            "email": getattr(contact, "email", None),
            "phone": getattr(contact, "phone", None),
            "contact_type": getattr(contact, "contact_type", None),
            "updated_at": str(getattr(contact, "updated_at", "")),
        })
        doc["document_hash"] = _hash(doc)
        return doc


class TaskIndexAdapter:
    @staticmethod
    def to_document(task: Any, organization_id: str) -> SearchDocument:
        doc = SearchDocument({
            "id": str(getattr(task, "id", "")),
            "entity_type": "task",
            "entity_id": str(getattr(task, "id", "")),
            "organization_id": organization_id,
            "display_title": getattr(task, "title", ""),
            "display_subtitle": f"{getattr(task, 'status', '')} · {getattr(task, 'priority', '')}",
            "searchable_text": " ".join(filter(None, [
                getattr(task, "title", ""),
                getattr(task, "description", None) or "",
                getattr(task, "status", ""),
            ])),
            "status": getattr(task, "status", None),
            "priority": getattr(task, "priority", None),
            "updated_at": str(getattr(task, "updated_at", "")),
        })
        doc["document_hash"] = _hash(doc)
        return doc


class MeetingIndexAdapter:
    @staticmethod
    def to_document(meeting: Any, organization_id: str) -> SearchDocument:
        doc = SearchDocument({
            "id": str(getattr(meeting, "id", "")),
            "entity_type": "meeting",
            "entity_id": str(getattr(meeting, "id", "")),
            "organization_id": organization_id,
            "display_title": getattr(meeting, "title", ""),
            "display_subtitle": f"{getattr(meeting, 'meeting_type', '')} · {getattr(meeting, 'status', '')}",
            "searchable_text": " ".join(filter(None, [
                getattr(meeting, "title", ""),
                getattr(meeting, "location", None) or "",
                getattr(meeting, "status", ""),
            ])),
            "meeting_type": getattr(meeting, "meeting_type", None),
            "status": getattr(meeting, "status", None),
            "updated_at": str(getattr(meeting, "updated_at", "")),
        })
        doc["document_hash"] = _hash(doc)
        return doc


# Registry — used by IndexingService to resolve adapter by entity type
ADAPTER_REGISTRY = {
    "lead": LeadIndexAdapter,
    "property": PropertyIndexAdapter,
    "contact": ContactIndexAdapter,
    "task": TaskIndexAdapter,
    "meeting": MeetingIndexAdapter,
}


def get_adapter(entity_type: str):
    return ADAPTER_REGISTRY.get(entity_type)
