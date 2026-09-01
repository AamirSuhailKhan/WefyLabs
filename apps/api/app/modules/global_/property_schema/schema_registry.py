"""
PropertySchemaRegistry — Market-Aware Property Schema Validation
===============================================================
Replaces the hardcoded property_type CheckConstraint in Lead and PropertyListing.
Property types and required fields are defined per market, not globally hardcoded.

India market: 1bhk, 2bhk, 3bhk, 4bhk_plus, villa, plot, commercial
UAE market: studio, 1_bed, 2_bed, 3_bed, luxury_villa, penthouse, commercial
UK market: flat, terraced, semi_detached, detached, bungalow
US market: single_family, condo, townhouse, multi_family, land, commercial
Singapore: hdb_flat, condo, landed_house, executive_condo
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import PropertySchema, PropertyField

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationError:
    field_key: str
    message: str


@dataclass
class SchemaValidationResult:
    is_valid: bool
    errors: List[SchemaValidationError]

    @property
    def error_messages(self) -> List[str]:
        return [f"{e.field_key}: {e.message}" for e in self.errors]


@dataclass
class UnitConversionResult:
    original_value: float
    original_unit: str
    canonical_value: float       # Always sqft internally
    canonical_unit: str = "sqft"


class UnitConversionService:
    """
    Converts between area measurement units.
    Canonical internal unit: sqft (for consistent arithmetic).
    Display unit: as-supplied (stored in area_unit column).
    """

    # Conversion factors to sqft
    _TO_SQFT: Dict[str, float] = {
        "sqft": 1.0,
        "sq_ft": 1.0,
        "sqm": 10.7639,        # 1 sqm = 10.7639 sqft
        "sq_m": 10.7639,
        "sqyd": 9.0,           # 1 sq yard = 9 sqft
        "sq_yd": 9.0,
        "marla": 272.25,       # 1 marla (Pakistan/India) = 272.25 sqft
        "kanal": 5445.0,       # 1 kanal = 20 marla = 5445 sqft
        "cent": 435.6,         # South India: 1 cent = 435.6 sqft
        "acre": 43560.0,
        "hectare": 107639.0,
    }

    @classmethod
    def to_sqft(cls, value: float, from_unit: str) -> UnitConversionResult:
        """Convert any area value to canonical sqft."""
        unit_lower = from_unit.lower().strip()
        factor = cls._TO_SQFT.get(unit_lower)
        if factor is None:
            logger.warning(f"[UnitConversion] Unknown area unit '{from_unit}'. Treating as sqft.")
            factor = 1.0
        return UnitConversionResult(
            original_value=value,
            original_unit=from_unit,
            canonical_value=round(value * factor, 2),
        )

    @classmethod
    def from_sqft(cls, sqft_value: float, to_unit: str) -> float:
        """Convert sqft to display unit."""
        unit_lower = to_unit.lower().strip()
        factor = cls._TO_SQFT.get(unit_lower, 1.0)
        return round(sqft_value / factor, 2)

    @classmethod
    def supported_units(cls) -> List[str]:
        return list(cls._TO_SQFT.keys())


class PropertySchemaRegistry:
    """
    Provides market-aware property schema lookup and validation.
    Replaces the hardcoded property_type enum in Lead and PropertyListing models.

    Resolution order (most to least specific):
      Organization+Market → Market → Country → Global fallback
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        # In-memory cache: market_id → PropertySchema
        self._schema_cache: Dict[str, PropertySchema] = {}

    async def get_schema(
        self,
        market_id: Optional[str] = None,
        country_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[PropertySchema]:
        """Load the most specific active schema for the given context."""
        cache_key = f"{organization_id}:{market_id}:{country_id}"
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]

        # Build scope priority order
        scope_queries = []
        if organization_id and market_id:
            scope_queries.append((PropertySchema.organization_id == organization_id,
                                   PropertySchema.market_id == market_id))
        if market_id:
            scope_queries.append((PropertySchema.organization_id == None,
                                   PropertySchema.market_id == market_id))
        if country_id:
            scope_queries.append((PropertySchema.organization_id == None,
                                   PropertySchema.market_id == None,
                                   PropertySchema.country_id == country_id))

        for conditions in scope_queries:
            stmt = (
                select(PropertySchema)
                .where(and_(PropertySchema.is_active == True, *conditions))
                .order_by(PropertySchema.version.desc())
                .limit(1)
            )
            result = await self._db.execute(stmt)
            schema = result.scalar_one_or_none()
            if schema:
                self._schema_cache[cache_key] = schema
                return schema

        return None

    async def get_allowed_property_types(
        self,
        market_id: Optional[str] = None,
        country_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[List[str]]:
        """
        Return the list of allowed property type codes for a given market.
        Returns None if no schema is configured (accepts any value).
        """
        schema = await self.get_schema(market_id, country_id, organization_id)
        if not schema:
            return None
        return schema.property_type_codes

    async def validate_property_type(
        self,
        property_type: str,
        market_id: Optional[str] = None,
        country_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Validate if a property type is valid for the given market.
        Returns True if no schema is configured (permissive) or if type is in allowed list.
        """
        allowed = await self.get_allowed_property_types(market_id, country_id, organization_id)
        if allowed is None:
            return True
        return property_type in allowed

    async def validate_extended_fields(
        self,
        extended_fields: Dict[str, Any],
        market_id: Optional[str] = None,
        country_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> SchemaValidationResult:
        """
        Validate extended_fields against the market's PropertyField definitions.
        Checks required fields and type constraints.
        """
        errors: List[SchemaValidationError] = []
        schema = await self.get_schema(market_id, country_id, organization_id)

        if not schema:
            return SchemaValidationResult(is_valid=True, errors=[])

        # Load fields
        stmt = select(PropertyField).where(PropertyField.schema_id == schema.id)
        result = await self._db.execute(stmt)
        fields = list(result.scalars().all())

        for pf in fields:
            value = extended_fields.get(pf.field_key)

            # Required check
            if pf.is_required and (value is None or value == ""):
                errors.append(SchemaValidationError(
                    field_key=pf.field_key,
                    message=f"'{pf.field_label}' is required."
                ))
                continue

            if value is None:
                continue

            # Type check
            if pf.field_type == "number":
                try:
                    float(value)
                except (TypeError, ValueError):
                    errors.append(SchemaValidationError(pf.field_key, f"'{pf.field_label}' must be a number."))
            elif pf.field_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(SchemaValidationError(pf.field_key, f"'{pf.field_label}' must be true or false."))
            elif pf.field_type == "select":
                if pf.select_options and value not in pf.select_options:
                    errors.append(SchemaValidationError(
                        pf.field_key,
                        f"'{pf.field_label}' must be one of: {', '.join(pf.select_options)}"
                    ))

        return SchemaValidationResult(is_valid=len(errors) == 0, errors=errors)

    def invalidate_cache(self, market_id: Optional[str] = None):
        """Invalidate schema cache — call after schema updates."""
        if market_id:
            self._schema_cache = {
                k: v for k, v in self._schema_cache.items()
                if market_id not in k
            }
        else:
            self._schema_cache.clear()
