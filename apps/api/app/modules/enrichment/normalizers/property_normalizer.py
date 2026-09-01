"""
Volume 2 PART 2 — Property Normalizer
"""
import re
from typing import Dict, Any, Optional

PROPERTY_TYPES = {
    "1bhk": ["1bhk", "1 bed", "1 bedroom", "one bedroom", "1-bedroom"],
    "2bhk": ["2bhk", "2 bed", "2 bedroom", "two bedroom", "2-bedroom"],
    "3bhk": ["3bhk", "3 bed", "3 bedroom", "three bedroom", "3-bedroom"],
    "villa": ["villa", "townhouse", "mansion", "duplex"],
    "plot": ["plot", "land", "commercial plot"],
    "studio": ["studio", "0bhk"],
    "penthouse": ["penthouse", "sky villa"]
}


class PropertyNormalizer:
    @classmethod
    def normalize(cls, property_type_raw: Optional[str], bedrooms_raw: Optional[Any] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        text = f"{property_type_raw or ''} {bedrooms_raw or ''} {notes or ''}".lower()
        
        detected_type = None
        bedrooms = None
        bathrooms = None

        # Detect property type
        for ptype, keywords in PROPERTY_TYPES.items():
            if any(kw in text for kw in keywords):
                detected_type = ptype
                break

        # Detect bedroom count if not found
        if not bedrooms and detected_type in ["1bhk", "2bhk", "3bhk"]:
            bedrooms = int(detected_type[0])
        elif not bedrooms:
            bed_match = re.search(r"(\d+)\s*(?:bed|bedroom|bhk)", text)
            if bed_match:
                bedrooms = int(bed_match.group(1))

        # Detect bathroom count
        bath_match = re.search(r"(\d+)\s*(?:bath|bathroom)", text)
        if bath_match:
            bathrooms = int(bath_match.group(1))

        # Map to canonical property_type enum: ('1bhk', '2bhk', '3bhk', 'villa', 'plot')
        canonical_type = detected_type
        if canonical_type in ["studio"]:
            canonical_type = "1bhk"
        elif canonical_type in ["penthouse"]:
            canonical_type = "villa"
        elif canonical_type not in ["1bhk", "2bhk", "3bhk", "villa", "plot"]:
            canonical_type = None

        return {
            "property_type": canonical_type or property_type_raw,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "confidence": 0.85 if canonical_type else 0.3
        }
