"""
Calendar Provider Interface & Mock Provider
===========================================
Defines the universal calendar integration contract for Google Calendar, Microsoft Graph,
and Apple CalDAV without vendor lock-in.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional

class CalendarProvider(ABC):
    """
    Universal calendar provider abstraction.
    """

    @abstractmethod
    async def get_availability(
        self,
        account_email: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> List[Dict[str, datetime]]:
        """Returns a list of busy intervals {'start': dt, 'end': dt}."""
        pass

    @abstractmethod
    async def create_event(
        self,
        account_email: str,
        title: str,
        start_utc: datetime,
        end_utc: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendee_emails: Optional[List[str]] = None,
        virtual_provider: str = "NONE",
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates an external event and optional virtual meeting link."""
        pass

    @abstractmethod
    async def update_event(
        self,
        account_email: str,
        external_event_id: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> bool:
        """Updates event time on the external provider."""
        pass

    @abstractmethod
    async def cancel_event(
        self,
        account_email: str,
        external_event_id: str,
        access_token: Optional[str] = None
    ) -> bool:
        """Cancels/deletes the event on the external provider."""
        pass


class MockCalendarProvider(CalendarProvider):
    """
    In-memory calendar provider for testing and deterministic offline execution.
    """

    def __init__(self):
        self.events: Dict[str, Dict[str, Any]] = {}

    async def get_availability(
        self,
        account_email: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> List[Dict[str, datetime]]:
        busy_blocks = []
        for evt_id, evt in self.events.items():
            if evt.get("account_email") == account_email:
                e_start = evt["start_utc"]
                e_end = evt["end_utc"]
                if not (e_end <= start_utc or e_start >= end_utc):
                    busy_blocks.append({"start": e_start, "end": e_end})
        return busy_blocks

    async def create_event(
        self,
        account_email: str,
        title: str,
        start_utc: datetime,
        end_utc: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendee_emails: Optional[List[str]] = None,
        virtual_provider: str = "NONE",
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        ext_id = f"ext_evt_{len(self.events) + 1}"
        meeting_url = None
        if virtual_provider == "GOOGLE_MEET":
            meeting_url = f"https://meet.google.com/beetle-{ext_id}"
        elif virtual_provider == "MICROSOFT_TEAMS":
            meeting_url = f"https://teams.microsoft.com/l/meetup-join/beetle-{ext_id}"
        elif virtual_provider == "ZOOM":
            meeting_url = f"https://zoom.us/j/9876543210?pwd=beetle_{ext_id}"

        self.events[ext_id] = {
            "account_email": account_email,
            "title": title,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "description": description,
            "location": location,
            "meeting_url": meeting_url
        }
        return {
            "external_event_id": ext_id,
            "meeting_url": meeting_url,
            "status": "confirmed"
        }

    async def update_event(
        self,
        account_email: str,
        external_event_id: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> bool:
        if external_event_id in self.events:
            self.events[external_event_id]["start_utc"] = start_utc
            self.events[external_event_id]["end_utc"] = end_utc
            return True
        return False

    async def cancel_event(
        self,
        account_email: str,
        external_event_id: str,
        access_token: Optional[str] = None
    ) -> bool:
        if external_event_id in self.events:
            del self.events[external_event_id]
            return True
        return True
