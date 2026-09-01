"""
Volume 2 PART 2 — Location Normalizer
"""
from typing import Dict, Any, Optional

CITY_LOCATION_MAP = {
    "dubai": {"city": "Dubai", "state": "Dubai", "country": "United Arab Emirates", "iso2": "AE", "timezone": "Asia/Dubai"},
    "abu dhabi": {"city": "Abu Dhabi", "state": "Abu Dhabi", "country": "United Arab Emirates", "iso2": "AE", "timezone": "Asia/Dubai"},
    "sharjah": {"city": "Sharjah", "state": "Sharjah", "country": "United Arab Emirates", "iso2": "AE", "timezone": "Asia/Dubai"},
    "ajman": {"city": "Ajman", "state": "Ajman", "country": "United Arab Emirates", "iso2": "AE", "timezone": "Asia/Dubai"},
    "ras al khaimah": {"city": "Ras Al Khaimah", "state": "RAK", "country": "United Arab Emirates", "iso2": "AE", "timezone": "Asia/Dubai"},
    "london": {"city": "London", "state": "England", "country": "United Kingdom", "iso2": "GB", "timezone": "Europe/London"},
    "mumbai": {"city": "Mumbai", "state": "Maharashtra", "country": "India", "iso2": "IN", "timezone": "Asia/Kolkata"},
    "delhi": {"city": "Delhi", "state": "Delhi", "country": "India", "iso2": "IN", "timezone": "Asia/Kolkata"},
    "riyadh": {"city": "Riyadh", "state": "Riyadh", "country": "Saudi Arabia", "iso2": "SA", "timezone": "Asia/Riyadh"},
    "doha": {"city": "Doha", "state": "Doha", "country": "Qatar", "iso2": "QA", "timezone": "Asia/Qatar"},
    "cairo": {"city": "Cairo", "state": "Cairo", "country": "Egypt", "iso2": "EG", "timezone": "Africa/Cairo"},
    "new york": {"city": "New York", "state": "NY", "country": "United States", "iso2": "US", "timezone": "America/New_York"},
}

POPULAR_DUBAI_AREAS = [
    "dubai marina", "downtown", "downtown dubai", "palm jumeirah", "business bay",
    "jbr", "jumeirah beach residence", "jlt", "jumeirah lake towers", "dubai hills",
    "dubai hills estate", "arabian ranches", "creek harbour", "dubai creek harbour",
    "meydan", "damac hills", "soha hartland", "mBR city", "town square", "furjan"
]


class LocationNormalizer:
    @classmethod
    def normalize(cls, city: Optional[str] = None, country: Optional[str] = None, raw_location: Optional[str] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "city": city,
            "state": None,
            "country": country,
            "iso2": None,
            "timezone": None,
            "preferred_areas": [],
            "confidence": 0.0
        }

        search_str = f"{raw_location or ''} {city or ''} {country or ''}".lower()

        # Check for Dubai sub-areas
        found_areas = []
        for area in POPULAR_DUBAI_AREAS:
            if area in search_str:
                found_areas.append(area.title())
        result["preferred_areas"] = found_areas

        # Match city map
        matched = None
        for key, loc in CITY_LOCATION_MAP.items():
            if key in search_str:
                matched = loc
                break

        if matched:
            result["city"] = matched["city"]
            result["state"] = matched["state"]
            result["country"] = matched["country"]
            result["iso2"] = matched["iso2"]
            result["timezone"] = matched["timezone"]
            result["confidence"] = 0.9
        elif country:
            result["country"] = country.title()
            result["confidence"] = 0.6

        return result
