"""
AddressService — Production-Grade Multi-Country Address Engine
==============================================================
Spec §33 — Country-Specific Address Structures & Formatting.

Never forces every country into a rigid US/India "Street, City, State, ZIP" model.
Different countries have vastly different authoritative address schemas:
  - UAE: Building/Tower, Area / Sub-community, Emirate, PO Box, Makani Number
  - India: House/Flat, Street/Locality, Landmark, City/District, State, PIN Code
  - UK: Flat/Building, Street, Town/City, County, Postal Code (e.g. SW1A 1AA)
  - Saudi Arabia: Building No, Street, District, City, Postal Code, Additional No (National Address)
  - US/Canada: Street Address, Apt/Suite, City, State/Province, ZIP/Postal Code
  - Singapore: Block/House No, Building Name, Street, Postal Code (6-digit building-specific)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StructuredAddress:
    """Canonical multi-country address representation."""
    country_code: str                          # ISO Alpha-2 (AE, IN, GB, SA, US, SG, etc.)
    formatted_address: str                     # Multi-line or single-line standard formatted address
    components: Dict[str, Any] = field(default_factory=dict)
    postal_code: Optional[str] = None
    city_or_locality: Optional[str] = None
    state_or_emirate: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country_code": self.country_code,
            "formatted_address": self.formatted_address,
            "components": self.components,
            "postal_code": self.postal_code,
            "city_or_locality": self.city_or_locality,
            "state_or_emirate": self.state_or_emirate,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


class AddressService:
    """
    Validates, structures, and formats country-specific physical addresses.
    """

    @classmethod
    def format_address(cls, country_code: str, components: Dict[str, Any]) -> StructuredAddress:
        """
        Formats raw components into an authoritative national address structure.
        """
        cc = (country_code or "GLOBAL").upper()
        handler = getattr(cls, f"_format_{cc.lower()}", cls._format_generic)
        return handler(cc, components)

    # ─── Country Specific Formatters ──────────────────────────────────────────

    @classmethod
    def _format_ae(cls, country_code: str, comp: Dict[str, Any]) -> StructuredAddress:
        """
        UAE Address Structure:
        Building/Tower, Area/District, Emirate, PO Box, Makani Number
        """
        errors = []
        building = comp.get("building") or comp.get("tower") or comp.get("premise") or ""
        area = comp.get("area") or comp.get("locality") or comp.get("sub_community") or ""
        emirate = comp.get("emirate") or comp.get("city") or "Dubai"
        po_box = comp.get("po_box") or ""
        makani = comp.get("makani") or ""

        if not area and not building:
            errors.append("UAE address requires at least a building or area name.")

        parts = []
        if building:
            parts.append(building)
        if area:
            parts.append(area)
        if emirate:
            parts.append(emirate)
        if po_box:
            parts.append(f"P.O. Box {po_box}")
        parts.append("United Arab Emirates")
        if makani:
            parts.append(f"(Makani: {makani})")

        formatted = ", ".join(parts)
        return StructuredAddress(
            country_code="AE",
            formatted_address=formatted,
            components=comp,
            postal_code=po_box or None,
            city_or_locality=area or emirate,
            state_or_emirate=emirate,
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )

    @classmethod
    def _format_in(cls, country_code: str, comp: Dict[str, Any]) -> StructuredAddress:
        """
        India Address Structure:
        Flat/Plot, Street/Locality, Landmark, City/District, State, PIN Code
        """
        errors = []
        line1 = comp.get("line1") or comp.get("flat_or_plot") or comp.get("building") or ""
        locality = comp.get("locality") or comp.get("street") or ""
        landmark = comp.get("landmark") or ""
        city = comp.get("city") or comp.get("district") or ""
        state = comp.get("state") or ""
        pincode = str(comp.get("pincode") or comp.get("postal_code") or "").strip()

        if pincode and (len(pincode) != 6 or not pincode.isdigit()):
            errors.append(f"Invalid Indian PIN code: '{pincode}'. Must be 6 digits.")

        parts = []
        if line1:
            parts.append(line1)
        if locality:
            parts.append(locality)
        if landmark:
            parts.append(f"Near {landmark}")
        if city:
            parts.append(city)
        if state:
            parts.append(f"{state} - {pincode}" if pincode else state)
        elif pincode:
            parts.append(pincode)
        parts.append("India")

        formatted = ", ".join(parts)
        return StructuredAddress(
            country_code="IN",
            formatted_address=formatted,
            components=comp,
            postal_code=pincode or None,
            city_or_locality=city or locality,
            state_or_emirate=state,
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )

    @classmethod
    def _format_gb(cls, country_code: str, comp: Dict[str, Any]) -> StructuredAddress:
        """
        UK Address Structure:
        Flat/Building, Street, Town/City, County, Postcode
        """
        errors = []
        premise = comp.get("premise") or comp.get("building") or comp.get("flat") or ""
        street = comp.get("street") or comp.get("thoroughfare") or ""
        city = comp.get("city") or comp.get("town") or ""
        county = comp.get("county") or ""
        postcode = comp.get("postcode") or comp.get("postal_code") or ""

        parts = []
        if premise and street:
            parts.append(f"{premise} {street}")
        elif premise or street:
            parts.append(premise or street)
        if city:
            parts.append(city)
        if county:
            parts.append(county)
        if postcode:
            parts.append(postcode.upper())
        parts.append("United Kingdom")

        formatted = ", ".join(parts)
        return StructuredAddress(
            country_code="GB",
            formatted_address=formatted,
            components=comp,
            postal_code=postcode or None,
            city_or_locality=city,
            state_or_emirate=county,
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )

    @classmethod
    def _format_sa(cls, country_code: str, comp: Dict[str, Any]) -> StructuredAddress:
        """
        Saudi Arabia National Address Structure:
        Building No, Street, District, City, Postal Code, Additional No
        """
        errors = []
        building_no = comp.get("building_no") or comp.get("building") or ""
        street = comp.get("street") or ""
        district = comp.get("district") or comp.get("locality") or ""
        city = comp.get("city") or ""
        postal_code = comp.get("postal_code") or comp.get("zip") or ""
        additional_no = comp.get("additional_no") or ""

        parts = []
        if building_no and street:
            parts.append(f"{building_no} {street}")
        elif building_no or street:
            parts.append(building_no or street)
        if district:
            parts.append(f"{district} District")
        if city:
            parts.append(city)
        if postal_code and additional_no:
            parts.append(f"{postal_code}-{additional_no}")
        elif postal_code:
            parts.append(str(postal_code))
        parts.append("Saudi Arabia")

        formatted = ", ".join(parts)
        return StructuredAddress(
            country_code="SA",
            formatted_address=formatted,
            components=comp,
            postal_code=str(postal_code) if postal_code else None,
            city_or_locality=city or district,
            state_or_emirate=city,
            is_valid=len(errors) == 0,
            validation_errors=errors,
        )

    @classmethod
    def _format_generic(cls, country_code: str, comp: Dict[str, Any]) -> StructuredAddress:
        """Fallback generic address formatter."""
        line1 = comp.get("line1") or comp.get("street") or comp.get("address") or ""
        line2 = comp.get("line2") or comp.get("apt_suite") or ""
        city = comp.get("city") or comp.get("locality") or ""
        state = comp.get("state") or comp.get("province") or comp.get("region") or ""
        postal_code = comp.get("postal_code") or comp.get("zip") or comp.get("pincode") or ""

        parts = [p for p in [line1, line2, city, state, postal_code, country_code] if p]
        return StructuredAddress(
            country_code=country_code,
            formatted_address=", ".join(parts) if parts else "[No Address Provided]",
            components=comp,
            postal_code=str(postal_code) if postal_code else None,
            city_or_locality=city or None,
            state_or_emirate=state or None,
            is_valid=True,
            validation_errors=[],
        )
