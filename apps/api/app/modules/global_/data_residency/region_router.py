"""
RegionRouter & TenantRegionResolver — Data Residency Routing Engine
====================================================================
Routes data operations to the configured storage region for a tenant.

Architecture:
  - NEVER hardcode: if country == "AE": use_middle_east_db()
  - Configuration-driven: TenantRegionResolver reads from DataResidencyPolicy
  - RegionRouter selects the appropriate data store connection

Supported regions:
  INDIA          — ap-south-1 (Mumbai)
  MIDDLE_EAST    — me-central-1 (UAE) / me-south-1 (Bahrain)
  EUROPE         — eu-west-1 (Ireland) / eu-central-1 (Frankfurt)
  NORTH_AMERICA  — us-east-1 (Virginia) / ca-central-1 (Canada)
  APAC           — ap-southeast-1 (Singapore) / ap-southeast-2 (Sydney)
  GLOBAL         — Multi-region (no residency restriction)

IMPORTANT: Declaring regional storage does NOT automatically satisfy
data residency legal requirements. Compliance teams must verify.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


# Region → available infrastructure config
REGION_METADATA: Dict[str, Dict] = {
    "INDIA": {
        "aws_region": "ap-south-1",
        "display_name": "India (Mumbai)",
        "countries": ["IN"],
        "pii_encryption_required": True,
        "gdpr_applicable": False,
        "pdp_applicable": True,      # India PDPB
    },
    "MIDDLE_EAST": {
        "aws_region": "me-central-1",
        "display_name": "UAE / Middle East",
        "countries": ["AE", "SA", "QA", "OM", "BH", "KW"],
        "pii_encryption_required": True,
        "gdpr_applicable": False,
        "pdp_applicable": False,
    },
    "EUROPE": {
        "aws_region": "eu-west-1",
        "display_name": "Europe (Ireland)",
        "countries": ["GB", "DE", "FR", "NL", "SE", "NO"],
        "pii_encryption_required": True,
        "gdpr_applicable": True,
        "pdp_applicable": False,
    },
    "NORTH_AMERICA": {
        "aws_region": "us-east-1",
        "display_name": "US East (Virginia)",
        "countries": ["US", "CA"],
        "pii_encryption_required": True,
        "gdpr_applicable": False,
        "pdp_applicable": False,
        "ccpa_applicable": True,    # US California
        "pipeda_applicable": True,  # Canada
    },
    "APAC": {
        "aws_region": "ap-southeast-1",
        "display_name": "Singapore",
        "countries": ["SG", "AU"],
        "pii_encryption_required": True,
        "gdpr_applicable": False,
        "pdp_applicable": False,
        "pdpa_applicable": True,    # Singapore PDPA
    },
    "GLOBAL": {
        "aws_region": "us-east-1",
        "display_name": "Global (Multi-Region)",
        "countries": [],
        "pii_encryption_required": True,
        "gdpr_applicable": False,
        "pdp_applicable": False,
    },
}


@dataclass
class RegionResolution:
    """Result of region resolution for a tenant/operation."""
    organization_id: str
    primary_region: str
    backup_region: Optional[str]
    allowed_processing_regions: List[str]
    pii_encryption_required: bool
    resolved_from: str    # "policy" | "country_default" | "system_default"
    policy_id: Optional[str] = None


class TenantRegionResolver:
    """
    Resolves the storage/processing region for a tenant.

    Resolution order:
      1. DataResidencyPolicy for organization
      2. DataResidencyPolicy for country
      3. Country metadata default region
      4. GLOBAL fallback
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._cache: Dict[str, RegionResolution] = {}

    async def resolve(
        self,
        organization_id: str,
        country_code: Optional[str] = None,
    ) -> RegionResolution:
        """
        Resolve the primary data region for an organization.
        Returns RegionResolution with provenance.
        """
        cache_key = f"{organization_id}:{country_code}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        from app.models.global_models import DataResidencyPolicy

        # 1. Check org-level policy
        stmt = select(DataResidencyPolicy).where(and_(
            DataResidencyPolicy.organization_id == organization_id,
            DataResidencyPolicy.is_active == True,
        )).limit(1)
        result = await self._db.execute(stmt)
        policy = result.scalar_one_or_none()

        if policy:
            resolution = RegionResolution(
                organization_id=organization_id,
                primary_region=policy.storage_region,
                backup_region=None,
                allowed_processing_regions=policy.allowed_transfer_regions or [policy.storage_region],
                pii_encryption_required=policy.requires_encryption,
                resolved_from="policy",
                policy_id=str(policy.id),
            )
            self._cache[cache_key] = resolution
            return resolution

        # 2. Check country-level policy
        if country_code:
            stmt2 = select(DataResidencyPolicy).where(and_(
                DataResidencyPolicy.organization_id.is_(None),
                DataResidencyPolicy.is_active == True,
            )).limit(1)
            result2 = await self._db.execute(stmt2)
            country_policy = result2.scalar_one_or_none()

            if country_policy:
                resolution = RegionResolution(
                    organization_id=organization_id,
                    primary_region=country_policy.storage_region,
                    backup_region=None,
                    allowed_processing_regions=country_policy.allowed_transfer_regions or [country_policy.storage_region],
                    pii_encryption_required=country_policy.requires_encryption,
                    resolved_from="country_default",
                    policy_id=str(country_policy.id),
                )
                self._cache[cache_key] = resolution
                return resolution

        # 3. Infer from country code
        if country_code:
            default_region = self._country_to_region(country_code)
            metadata = REGION_METADATA.get(default_region, REGION_METADATA["GLOBAL"])
            resolution = RegionResolution(
                organization_id=organization_id,
                primary_region=default_region,
                backup_region=None,
                allowed_processing_regions=[default_region, "GLOBAL"],
                pii_encryption_required=metadata.get("pii_encryption_required", True),
                resolved_from="country_default",
            )
            self._cache[cache_key] = resolution
            return resolution

        # 4. Global fallback
        resolution = RegionResolution(
            organization_id=organization_id,
            primary_region="GLOBAL",
            backup_region=None,
            allowed_processing_regions=["GLOBAL"],
            pii_encryption_required=True,
            resolved_from="system_default",
        )
        self._cache[cache_key] = resolution
        return resolution

    @staticmethod
    def _country_to_region(country_code: str) -> str:
        """Map ISO Alpha-2 to storage region."""
        for region, meta in REGION_METADATA.items():
            if country_code in meta.get("countries", []):
                return region
        return "GLOBAL"

    def is_transfer_allowed(
        self,
        source_region: str,
        target_region: str,
        resolution: RegionResolution,
    ) -> bool:
        """
        Check if data transfer from source to target region is allowed
        per the tenant's data residency policy.
        """
        if source_region == target_region:
            return True
        return target_region in resolution.allowed_processing_regions


class RegionRouter:
    """
    Routes data store operations to the configured region.

    In a multi-region deployment, this selects the correct
    database connection/endpoint. In a single-region deployment,
    returns the default connection.

    Note: Full multi-region DB routing requires infrastructure
    configuration outside this service. This class provides the
    interface that infrastructure integrates with.
    """

    def __init__(self, resolver: TenantRegionResolver):
        self._resolver = resolver

    async def get_region(self, organization_id: str, country_code: Optional[str] = None) -> str:
        """Return the primary region identifier for routing."""
        resolution = await self._resolver.resolve(organization_id, country_code)
        return resolution.primary_region

    async def validate_operation(
        self,
        organization_id: str,
        operation_region: str,
        country_code: Optional[str] = None,
    ) -> bool:
        """
        Validate that an operation in a given region is permitted
        by the tenant's data residency policy.
        Returns True if allowed, False if blocked.
        """
        resolution = await self._resolver.resolve(organization_id, country_code)
        if operation_region == resolution.primary_region:
            return True
        if operation_region in resolution.allowed_processing_regions:
            return True

        logger.warning(
            f"[RegionRouter] DATA RESIDENCY VIOLATION: org={organization_id} "
            f"attempted operation in region={operation_region} "
            f"but policy requires {resolution.primary_region}"
        )
        return False

    @staticmethod
    def get_region_metadata(region: str) -> Dict:
        """Return metadata for a region."""
        return REGION_METADATA.get(region, {})
