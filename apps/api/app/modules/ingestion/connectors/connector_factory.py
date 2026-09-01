from typing import Dict, Type
from app.modules.ingestion.connectors.base_connector import ILeadConnector
from app.modules.ingestion.connectors.website_connector import WebsiteFormConnector
from app.modules.ingestion.connectors.messaging_connector import MessagingConnector
from app.modules.ingestion.connectors.connectors import (
    EmailParserConnector, FileImportConnector, RestWebhookConnector
)

CONNECTOR_REGISTRY: Dict[str, Type[ILeadConnector]] = {
    "website": WebsiteFormConnector,
    "whatsapp": MessagingConnector,
    "telegram": MessagingConnector,
    "messaging": MessagingConnector,
    "email": EmailParserConnector,
    "csv_import": FileImportConnector,
    "file_import": FileImportConnector,
    "webhook": RestWebhookConnector,
    "meta_lead_ads": RestWebhookConnector,
    "google_lead_forms": RestWebhookConnector,
}


def get_connector(source: str) -> ILeadConnector:
    """Factory function resolving connector instance by source name."""
    connector_cls = CONNECTOR_REGISTRY.get(source.lower(), RestWebhookConnector)
    return connector_cls()
