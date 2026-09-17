"""
PART 31 — Customer Onboarding, Tenant Activation & Demo Mode
============================================================
Exports:
- onboarding_router: FastAPI REST router mounted at /api/v1/onboarding
- OnboardingService: Progressive multi-step state machine & checklist
- TenantActivationService: Deterministic 0-100 activation score & milestone evaluator
- DemoModeService: Isolated synthetic Indian real estate playground
- OnboardingCsvImportService: Formula-sanitized lead & property importer
"""
from app.modules.onboarding.router import router as onboarding_router
from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.activation_service import TenantActivationService
from app.modules.onboarding.demo_service import DemoModeService
from app.modules.onboarding.csv_import_service import OnboardingCsvImportService

__all__ = [
    "onboarding_router",
    "OnboardingService",
    "TenantActivationService",
    "DemoModeService",
    "OnboardingCsvImportService",
]
