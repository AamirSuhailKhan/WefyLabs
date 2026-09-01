import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

@pytest.mark.asyncio
async def test_internationalization_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. List supported country packs
        res_list = await ac.get("/api/v1/i18n/countries")
        assert res_list.status_code == 200
        countries = res_list.json()
        assert len(countries) >= 7
        codes = [c["country_code"] for c in countries]
        assert "IN" in codes
        assert "AE" in codes
        assert "US" in codes

        # 2. Get specific country pack (AE - UAE)
        res_ae = await ac.get("/api/v1/i18n/countries/AE")
        assert res_ae.status_code == 200
        ae_pack = res_ae.json()
        assert ae_pack["currency"]["code"] == "AED"
        assert "Property Finder" in ae_pack["major_portals"]

        # 3. Format Currency (IN - Lakhs/Crores vs US - Millions)
        res_format_in = await ac.post("/api/v1/i18n/format-currency", json={"amount": 15000000, "country_code": "IN"})
        assert res_format_in.status_code == 200
        assert "1.50 Cr" in res_format_in.json()["formatted_string"]

        res_format_us = await ac.post("/api/v1/i18n/format-currency", json={"amount": 1500000, "country_code": "US"})
        assert res_format_us.status_code == 200
        assert "1.50M" in res_format_us.json()["formatted_string"]

        # 4. Calculate Tax (GST IN vs VAT UAE)
        res_tax_in = await ac.post("/api/v1/i18n/calculate-tax", json={"amount": 10000, "country_code": "IN"})
        assert res_tax_in.status_code == 200
        assert res_tax_in.json()["tax_name"] == "GST"
        assert res_tax_in.json()["tax_amount"] == 1800.0
