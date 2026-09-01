from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel

from app.core.internationalization import InternationalFrameworkRegistry, CountryPack, CurrencyPack

router = APIRouter(prefix="/i18n", tags=["International Framework"])

class CurrencyFormatRequest(BaseModel):
    amount: float
    country_code: str = "IN"

class CurrencyFormatResponse(BaseModel):
    amount: float
    country_code: str
    currency_code: str
    currency_symbol: str
    formatted_string: str

class TaxCalculationRequest(BaseModel):
    amount: float
    country_code: str = "IN"

class TaxCalculationResponse(BaseModel):
    base_amount: float
    tax_name: str
    tax_rate_pct: float
    tax_amount: float
    total_amount: float

@router.get("/countries", response_model=List[CountryPack])
async def list_supported_countries():
    """Returns configuration packs for all globally supported countries."""
    return InternationalFrameworkRegistry.list_all_country_packs()

@router.get("/countries/{country_code}", response_model=CountryPack)
async def get_country_pack(country_code: str):
    """Retrieves country pack configuration by ISO 2-letter country code."""
    return InternationalFrameworkRegistry.get_country_pack(country_code)

@router.post("/format-currency", response_model=CurrencyFormatResponse)
async def format_currency_endpoint(req: CurrencyFormatRequest):
    """Formats numeric amounts according to regional currency conventions (e.g. Lakhs/Crores for IN vs. Millions for US/AE)."""
    pack = InternationalFrameworkRegistry.get_country_pack(req.country_code)
    curr = pack.currency

    if curr.display_unit == "lakhs_crores":
        if req.amount >= 10000000:
            formatted = f"{curr.symbol}{req.amount / 10000000:.2f} Cr"
        elif req.amount >= 100000:
            formatted = f"{curr.symbol}{req.amount / 100000:.2f} L"
        else:
            formatted = f"{curr.symbol}{req.amount:,.0f}"
    else:
        if req.amount >= 1000000:
            formatted = f"{curr.symbol}{req.amount / 1000000:.2f}M"
        elif req.amount >= 1000:
            formatted = f"{curr.symbol}{req.amount / 1000:.1f}K"
        else:
            formatted = f"{curr.symbol}{req.amount:,.0f}"

    return CurrencyFormatResponse(
        amount=req.amount,
        country_code=pack.country_code,
        currency_code=curr.code,
        currency_symbol=curr.symbol,
        formatted_string=formatted
    )

@router.post("/calculate-tax", response_model=TaxCalculationResponse)
async def calculate_regional_tax_endpoint(req: TaxCalculationRequest):
    """Calculates country-specific real estate tax rates (GST, VAT, RETT)."""
    pack = InternationalFrameworkRegistry.get_country_pack(req.country_code)
    tax_amt = round(req.amount * (pack.default_tax_rate_pct / 100.0), 2)
    total_amt = round(req.amount + tax_amt, 2)

    return TaxCalculationResponse(
        base_amount=req.amount,
        tax_name=pack.tax_name,
        tax_rate_pct=pack.default_tax_rate_pct,
        tax_amount=tax_amt,
        total_amount=total_amt
    )
