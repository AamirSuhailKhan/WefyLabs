from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class IntegrationEvent(BaseModel):
    provider_name: str
    event_type: str
    payload: Dict[str, Any]

class BaseProvider(ABC):
    """Abstract Base Class for all BeetleLabs Integration Providers."""
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider key (e.g. google_calendar, twilio, docusign, property_finder)."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Category (e.g. calendar, messaging, payment, e_signature, portal_syndication)."""
        pass


class CalendarProvider(BaseProvider):
    @abstractmethod
    async def create_event(self, title: str, start_time: str, end_time: str, attendees: List[str]) -> Dict[str, Any]:
        pass

class MessagingProvider(BaseProvider):
    @abstractmethod
    async def send_message(self, recipient: str, text_content: str) -> Dict[str, Any]:
        pass

class PaymentProvider(BaseProvider):
    @abstractmethod
    async def create_payment_link(self, amount: float, currency: str, description: str) -> Dict[str, Any]:
        pass

class SignatureProvider(BaseProvider):
    @abstractmethod
    async def create_signature_request(self, document_name: str, signer_email: str) -> Dict[str, Any]:
        pass

class PortalSyndicationProvider(BaseProvider):
    @abstractmethod
    async def publish_listing(self, property_id: str, title: str, price: float, location: str) -> Dict[str, Any]:
        pass


# --- Implementation Providers ---

class GoogleCalendarProvider(CalendarProvider):
    @property
    def provider_id(self) -> str: return "google_calendar"
    @property
    def category(self) -> str: return "calendar"

    async def create_event(self, title: str, start_time: str, end_time: str, attendees: List[str]) -> Dict[str, Any]:
        return {"status": "success", "provider": self.provider_id, "event_id": f"gcal_{title.replace(' ', '_')}"}

class OutlookCalendarProvider(CalendarProvider):
    @property
    def provider_id(self) -> str: return "microsoft_outlook"
    @property
    def category(self) -> str: return "calendar"

    async def create_event(self, title: str, start_time: str, end_time: str, attendees: List[str]) -> Dict[str, Any]:
        return {"status": "success", "provider": self.provider_id, "event_id": f"outlook_{title.replace(' ', '_')}"}

class WhatsAppProvider(MessagingProvider):
    @property
    def provider_id(self) -> str: return "whatsapp_direct"
    @property
    def category(self) -> str: return "messaging"

    async def send_message(self, recipient: str, text_content: str) -> Dict[str, Any]:
        return {"status": "sent", "provider": self.provider_id, "recipient": recipient}

class TwilioSMSProvider(MessagingProvider):
    @property
    def provider_id(self) -> str: return "twilio_sms"
    @property
    def category(self) -> str: return "messaging"

    async def send_message(self, recipient: str, text_content: str) -> Dict[str, Any]:
        return {"status": "sent", "provider": self.provider_id, "recipient": recipient}

class StripePaymentProvider(PaymentProvider):
    @property
    def provider_id(self) -> str: return "stripe"
    @property
    def category(self) -> str: return "payment"

    async def create_payment_link(self, amount: float, currency: str, description: str) -> Dict[str, Any]:
        return {"status": "created", "provider": self.provider_id, "url": f"https://checkout.stripe.com/pay/{description[:10]}"}

class RazorpayPaymentProvider(PaymentProvider):
    @property
    def provider_id(self) -> str: return "razorpay"
    @property
    def category(self) -> str: return "payment"

    async def create_payment_link(self, amount: float, currency: str, description: str) -> Dict[str, Any]:
        return {"status": "created", "provider": self.provider_id, "url": f"https://rzp.io/i/{description[:10]}"}

class DocuSignProvider(SignatureProvider):
    @property
    def provider_id(self) -> str: return "docusign"
    @property
    def category(self) -> str: return "e_signature"

    async def create_signature_request(self, document_name: str, signer_email: str) -> Dict[str, Any]:
        return {"status": "sent", "provider": self.provider_id, "envelope_id": f"ds_{document_name.replace(' ', '_')}"}

class PropertyFinderSyndicationProvider(PortalSyndicationProvider):
    @property
    def provider_id(self) -> str: return "property_finder"
    @property
    def category(self) -> str: return "portal_syndication"

    async def publish_listing(self, property_id: str, title: str, price: float, location: str) -> Dict[str, Any]:
        return {"status": "published", "provider": self.provider_id, "portal_ref": f"pf_{property_id}"}


class IntegrationRegistry:
    """Central Integration Provider Registry decoupling business logic from third-party vendor APIs."""
    
    _PROVIDERS: Dict[str, BaseProvider] = {
        "google_calendar": GoogleCalendarProvider(),
        "microsoft_outlook": OutlookCalendarProvider(),
        "whatsapp_direct": WhatsAppProvider(),
        "twilio_sms": TwilioSMSProvider(),
        "stripe": StripePaymentProvider(),
        "razorpay": RazorpayPaymentProvider(),
        "docusign": DocuSignProvider(),
        "property_finder": PropertyFinderSyndicationProvider()
    }

    @classmethod
    def get_provider(cls, provider_id: str) -> BaseProvider:
        provider = cls._PROVIDERS.get(provider_id.lower())
        if not provider:
            raise KeyError(f"Integration provider '{provider_id}' is not registered.")
        return provider

    @classmethod
    def list_active_providers(cls) -> List[Dict[str, str]]:
        return [
            {"provider_id": p.provider_id, "category": p.category}
            for p in cls._PROVIDERS.values()
        ]
