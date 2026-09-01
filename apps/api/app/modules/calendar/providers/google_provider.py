"""
Google Calendar API Provider Integration
========================================
Implements CalendarProvider for Google Workspace / Google Calendar API.
Supports FreeBusy queries, event creation with Google Meet, updates, and cancellations.
Zero simulated or mock fallbacks — all operations map to real Google Calendar REST endpoints.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx

from app.modules.calendar.providers.provider_interface import CalendarProvider
from app.modules.calendar.exceptions import (
    CalendarNotConnected,
    CalendarAuthorizationExpired,
    CalendarPermissionDenied,
    CalendarEventNotFound,
    CalendarRateLimited,
    CalendarProviderUnavailable,
    CalendarAPIError,
)

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(CalendarProvider):
    """
    Production Google Calendar API provider.
    Never fabricates event IDs or returns simulated success when tokens are absent.
    """

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://www.googleapis.com/calendar/v3"

    def _handle_http_error(self, resp: httpx.Response, action: str) -> None:
        """Maps Google API HTTP error status codes into domain exceptions."""
        if resp.status_code == 401:
            raise CalendarAuthorizationExpired(f"Google Calendar authorization expired during {action}.")
        elif resp.status_code == 403:
            raise CalendarPermissionDenied(f"Google Calendar permission denied during {action}: {resp.text[:200]}")
        elif resp.status_code == 404:
            raise CalendarEventNotFound(f"Google Calendar event not found during {action}.")
        elif resp.status_code == 429:
            raise CalendarRateLimited(f"Google Calendar rate limit exceeded during {action}.")
        elif resp.status_code >= 500:
            raise CalendarProviderUnavailable(f"Google Calendar service unavailable (HTTP {resp.status_code}).")
        else:
            raise CalendarAPIError(f"Google Calendar API returned HTTP {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

    async def get_availability(
        self,
        account_email: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> List[Dict[str, datetime]]:
        """
        Queries Google Calendar FreeBusy API for busy intervals.
        """
        if not access_token:
            raise CalendarNotConnected(f"No access token provided for account {account_email}.")

        url = f"{self.base_url}/freeBusy"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "timeMin": start_utc.isoformat(),
            "timeMax": end_utc.isoformat(),
            "items": [{"id": account_email}]
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.error(f"[GoogleCalendar] Network error querying FreeBusy: {e}")
            raise CalendarProviderUnavailable(f"Google Calendar FreeBusy request failed: {e}")

        if resp.status_code != 200:
            self._handle_http_error(resp, "FreeBusy query")

        data = resp.json()
        calendars = data.get("calendars", {}).get(account_email, {})
        busy_list = calendars.get("busy", [])
        return [
            {
                "start": datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                "end": datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            }
            for b in busy_list
        ]

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
        """
        Creates an event in Google Calendar with optional Google Meet link.
        """
        if not access_token:
            raise CalendarNotConnected(f"Cannot create calendar event: missing access token for {account_email}.")

        url = f"{self.base_url}/calendars/{account_email}/events"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        event_body: Dict[str, Any] = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {"dateTime": start_utc.isoformat()},
            "end": {"dateTime": end_utc.isoformat()},
            "attendees": [{"email": e} for e in (attendee_emails or [])]
        }

        if virtual_provider == "GOOGLE_MEET":
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"req_{uuid.uuid4().hex}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {"conferenceDataVersion": "1"} if virtual_provider == "GOOGLE_MEET" else {}
                resp = await client.post(url, json=event_body, headers=headers, params=params)
        except Exception as e:
            logger.error(f"[GoogleCalendar] Network error creating event: {e}")
            raise CalendarProviderUnavailable(f"Google Calendar create event request failed: {e}")

        if resp.status_code not in (200, 201):
            self._handle_http_error(resp, "event creation")

        data = resp.json()
        external_id = data.get("id")
        if not external_id:
            raise CalendarAPIError("Google Calendar response omitted event ID.")

        conf_data = data.get("conferenceData", {})
        entry_points = conf_data.get("entryPoints", [])
        video_entry = next((ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"), None)
        meeting_url = video_entry or data.get("hangoutLink")

        return {
            "external_event_id": external_id,
            "meeting_url": meeting_url,
            "status": data.get("status", "confirmed")
        }

    async def update_event(
        self,
        account_email: str,
        external_event_id: str,
        start_utc: datetime,
        end_utc: datetime,
        access_token: Optional[str] = None
    ) -> bool:
        """
        Updates start and end times of an existing Google Calendar event.
        """
        if not access_token:
            raise CalendarNotConnected(f"Cannot update event: missing access token for {account_email}.")

        url = f"{self.base_url}/calendars/{account_email}/events/{external_event_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        patch_body = {
            "start": {"dateTime": start_utc.isoformat()},
            "end": {"dateTime": end_utc.isoformat()}
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.patch(url, json=patch_body, headers=headers)
        except Exception as e:
            logger.error(f"[GoogleCalendar] Network error patching event: {e}")
            raise CalendarProviderUnavailable(f"Google Calendar update request failed: {e}")

        if resp.status_code != 200:
            self._handle_http_error(resp, "event update")

        return True

    async def cancel_event(
        self,
        account_email: str,
        external_event_id: str,
        access_token: Optional[str] = None
    ) -> bool:
        """
        Deletes/cancels an event from Google Calendar.
        """
        if not access_token:
            raise CalendarNotConnected(f"Cannot cancel event: missing access token for {account_email}.")

        url = f"{self.base_url}/calendars/{account_email}/events/{external_event_id}"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(url, headers=headers)
        except Exception as e:
            logger.error(f"[GoogleCalendar] Network error deleting event: {e}")
            raise CalendarProviderUnavailable(f"Google Calendar cancel request failed: {e}")

        if resp.status_code in (200, 204):
            return True
        elif resp.status_code == 404:
            # Event already deleted
            return True
        else:
            self._handle_http_error(resp, "event cancellation")
            return False
