"""
Lead Acquisition Connectors package.
Exports official connectors for Meta, Google, IndiaMART, and 99acres.
"""
from app.modules.lead_acquisition.connectors.meta_connector import MetaLeadAdsConnector
from app.modules.lead_acquisition.connectors.google_connector import GoogleLeadFormConnector
from app.modules.lead_acquisition.connectors.indiamart_connector import IndiaMartConnector
from app.modules.lead_acquisition.connectors.ninety_nine_acres_connector import NinetyNineAcresConnector

__all__ = [
    "MetaLeadAdsConnector",
    "GoogleLeadFormConnector",
    "IndiaMartConnector",
    "NinetyNineAcresConnector",
]
