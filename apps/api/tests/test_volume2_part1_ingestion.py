"""
Volume 2 PART 1 — Universal Lead Ingestion Engine Tests
======================================================
Comprehensive tests for:
  - Canonical Lead DTO & Field Validation
  - Connector Adapters (Website, WhatsApp, Email, CSV, Webhook)
  - Connector Factory Resolution
  - Ingestion Engine Models
"""
import pytest
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO
from app.modules.ingestion.connectors.connector_factory import get_connector
from app.modules.ingestion.connectors.website_connector import WebsiteFormConnector
from app.modules.ingestion.connectors.messaging_connector import MessagingConnector
from app.modules.ingestion.connectors.connectors import EmailParserConnector, FileImportConnector, RestWebhookConnector
from app.models.ingestion_models import ConnectorConfig, LeadImportBatch, LeadImportItem, OriginalPayload, IngestionLog


# ─── Canonical Lead DTO Tests ──────────────────────────────────────────────────

def test_canonical_lead_dto_validation():
    dto = CanonicalLeadDTO(
        name="  Jane Doe  ",
        phone="+971 (50) 987-6543",
        email="JANE.DOE@EXAMPLE.COM ",
        source="website",
    )
    assert dto.name == "  Jane Doe  "
    assert dto.phone == "+971509876543"
    assert dto.email == "jane.doe@example.com"
    assert dto.country_code == "AE"


def test_canonical_lead_dto_invalid_phone():
    with pytest.raises(ValueError, match="at least 7 digits"):
        CanonicalLeadDTO(name="Test", phone="123", source="test")


def test_canonical_lead_dto_invalid_email():
    with pytest.raises(ValueError, match="Invalid email format"):
        CanonicalLeadDTO(name="Test", phone="+971501234567", email="invalid_email_str", source="test")


# ─── Connector Factory & Adapters Tests ────────────────────────────────────────

def test_connector_factory_resolution():
    assert isinstance(get_connector("website"), WebsiteFormConnector)
    assert isinstance(get_connector("whatsapp"), MessagingConnector)
    assert isinstance(get_connector("email"), EmailParserConnector)
    assert isinstance(get_connector("csv_import"), FileImportConnector)
    assert isinstance(get_connector("meta_lead_ads"), RestWebhookConnector)


def test_website_connector_parse():
    connector = WebsiteFormConnector()
    raw = {
        "full_name": "Alice Smith",
        "mobile": "+971501112233",
        "email": "alice@example.com",
        "message": "Interested in 2BHK Villa in Dubai",
        "utm_campaign": "google_search_q3",
    }
    assert connector.validate_raw(raw) is True
    canonical = connector.parse_to_canonical(raw)
    assert canonical.name == "Alice Smith"
    assert canonical.phone == "+971501112233"
    assert canonical.email == "alice@example.com"
    assert canonical.source == "website_contact_form"
    assert canonical.notes[0] == "Interested in 2BHK Villa in Dubai"


def test_messaging_connector_parse():
    connector = MessagingConnector()
    raw = {
        "from": "+971509998877",
        "profile_name": "Bob Marley",
        "text": "Hi, please send brochure for Marina Bay Project",
    }
    assert connector.validate_raw(raw) is True
    canonical = connector.parse_to_canonical(raw)
    assert canonical.name == "Bob Marley"
    assert canonical.phone == "+971509998877"
    assert canonical.whatsapp_number == "+971509998877"
    assert canonical.source == "whatsapp_business"


def test_email_parser_connector_parse():
    connector = EmailParserConnector()
    raw = {
        "from_email": "investor@venture.com",
        "from_name": "Charlie Munger",
        "subject": "Inquiry about Downtown Commercial Plots",
        "body_plain": "I want to purchase 3 commercial plots.",
    }
    assert connector.validate_raw(raw) is True
    canonical = connector.parse_to_canonical(raw)
    assert canonical.name == "Charlie Munger"
    assert canonical.email == "investor@venture.com"
    assert canonical.source == "email_parser"


def test_file_import_connector_parse():
    connector = FileImportConnector()
    raw_row = {
        "Full Name": "David Beckham",
        "Mobile": "+971504445556",
        "Email Address": "david@beckham.com",
        "City": "Dubai",
        "Type": "Villa",
    }
    assert connector.validate_raw(raw_row) is True
    canonical = connector.parse_to_canonical(raw_row)
    assert canonical.name == "David Beckham"
    assert canonical.phone == "+971504445556"
    assert canonical.email == "david@beckham.com"
    assert canonical.city == "Dubai"


# ─── Ingestion Database Models Tests ──────────────────────────────────────────

def test_ingestion_models_instantiation():
    cfg = ConnectorConfig(
        organization_id="org-101",
        connector_type="whatsapp",
        name="Official WhatsApp Connector",
    )
    assert cfg.connector_type == "whatsapp"

    batch = LeadImportBatch(
        organization_id="org-101",
        user_id="user-1",
        filename="leads_q3.csv",
        total_records=5000,
    )
    assert batch.total_records == 5000

    item = LeadImportItem(
        batch_id="batch-1",
        organization_id="org-101",
        row_index=1,
        raw_data={"Name": "Test"},
        status="pending",
    )
    assert item.row_index == 1

    payload = OriginalPayload(
        ingestion_id="ing-123",
        organization_id="org-101",
        source="website",
        raw_payload_json={"name": "Test"},
    )
    assert payload.ingestion_id == "ing-123"

    log = IngestionLog(
        ingestion_id="ing-123",
        organization_id="org-101",
        source="website",
        status="success",
        latency_ms=12.5,
    )
    assert log.status == "success"
