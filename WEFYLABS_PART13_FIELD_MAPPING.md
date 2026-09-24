# WEFYLABS PART 13: REAL ESTATE LEAD FIELD MAPPING SPECIFICATION

## 1. Overview
This document specifies the exact deterministic mapping and normalization rules for transforming external lead data from **Meta Lead Ads** and **Google Ads Lead Forms** into the canonical `CanonicalLeadPayload` and `Lead` models in WefyLabs.

Under no circumstances are LLMs permitted to silently hallucinate or alter raw contact information during normalization. All transformations are deterministic, repeatable, and preserve original raw values in `LeadAcquisitionEvent.raw_payload`.

---

## 2. Meta Lead Ads Field Mappings

### 2.1 Standard Contact Fields
| External Field | Canonical Field | Normalization Rule | Required/Optional | Fallback | Provenance | Version |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `full_name` | `contact_name` | Trim whitespace, title case | Optional | `first_name` + `last_name` | Provider payload | v19.0 |
| `first_name`, `last_name` | `contact_name` | Combine if `full_name` missing | Optional | `"Unknown Lead"` | Provider payload | v19.0 |
| `email` | `email` | Trim, convert to lowercase, RFC 5322 validate | Optional | `None` | Provider payload | v19.0 |
| `phone_number` | `phone` | Strip non-digits, format to E.164 (`+91...`) | Optional | Raw digits if unparseable | Provider payload | v19.0 |

### 2.2 Real Estate Specific Fields
| External Field Label / Key | Canonical Field | Normalization Rule | Required/Optional | Fallback | Examples |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `budget`, `price_range` | `budget` | Extract numeric tokens; convert "Lakh"/"Cr" to integer INR | Optional | `None` | `"75 Lakh"` -> `7500000`, `"1.5 Cr"` -> `15000000` |
| `bhk`, `bedrooms`, `room_type` | `bhk` | Extract numeric prefix or string representation | Optional | `None` | `"3 BHK"` -> `"3 BHK"`, `"2"` -> `"2 BHK"` |
| `preferred_location`, `location`, `city` | `preferred_location` | Trim string, title case | Optional | `None` | `"Gurgaon, Sector 54"` -> `"Gurgaon, Sector 54"` |
| `timeline`, `buying_time` | `timeline` | Standardize to `"IMMEDIATE"`, `"1-3_MONTHS"`, `"3-6_MONTHS"`, `">6_MONTHS"` | Optional | Raw string | `"Within 30 days"` -> `"IMMEDIATE"` |
| `purpose`, `investment_or_self_use` | `custom_fields["purpose"]` | Map to `"INVESTMENT"` or `"SELF_USE"` | Optional | Raw string | `"For Self Use"` -> `"SELF_USE"` |
| Custom unmapped questions | `custom_fields[question_key]` | Preserve question text as key and answer as value | Optional | `None` | `{"preferred_bank": "HDFC"}` |

### 2.3 Meta Tracking & Attribution Fields
| External Field | Canonical Attribution Field | Description |
| :--- | :--- | :--- |
| `id` (leadgen_id) | `external_lead_id` | Unique Meta lead submission identifier |
| `form_id` | `form_id` | Meta Instant Form ID |
| `page_id` | `page_id` | Facebook Page ID hosting the form |
| `ad_id` | `ad_id` | Meta Ad creative ID |
| `adset_id` | `ad_set_id` | Meta Ad Set ID |
| `campaign_id` | `campaign_id` | Meta Campaign ID |
| `created_time` | `external_created_at` | ISO 8601 provider submission timestamp |

---

## 3. Google Ads Lead Form Field Mappings

### 3.1 Standard Column IDs
| External Column ID | Canonical Field | Normalization Rule | Required/Optional | Fallback |
| :--- | :--- | :--- | :--- | :--- |
| `FULL_NAME` | `contact_name` | Trim whitespace, title case | Optional | `FIRST_NAME` + `LAST_NAME` |
| `FIRST_NAME`, `LAST_NAME` | `contact_name` | Combine if `FULL_NAME` missing | Optional | `"Unknown Lead"` |
| `EMAIL` | `email` | Trim, convert to lowercase | Optional | `None` |
| `PHONE_NUMBER` | `phone` | Strip non-digits, format to E.164 | Optional | Raw digits |
| `CITY` | `preferred_location` | Trim string, title case | Optional | `None` |
| `POSTAL_CODE` | `custom_fields["postal_code"]`| Strip spaces, validate 6-digit PIN code | Optional | `None` |

### 3.2 Real Estate Specific Questions
| External Column / Question | Canonical Field | Normalization Rule | Required/Optional | Examples |
| :--- | :--- | :--- | :--- | :--- |
| Question matching `budget` | `budget` | Extract numeric tokens; parse Lakh / Crore | Optional | `"50-75L"` -> `7500000` |
| Question matching `bedroom`/`bhk` | `bhk` | Standardize BHK formatting | Optional | `"2 BHK"` -> `"2 BHK"` |
| Question matching `timeline` | `timeline` | Standardize to purchase horizon | Optional | `"0-3 months"` -> `"1-3_MONTHS"` |
| Question matching `property_type` | `custom_fields["property_type"]` | Map to `"APARTMENT"`, `"VILLA"`, `"PLOT"` | Optional | `"Luxury Apartment"` |

### 3.3 Google Tracking & Attribution Fields
| External Field | Canonical Attribution Field | Description |
| :--- | :--- | :--- |
| `lead_id` | `external_lead_id` | Google lead submission ID |
| `form_id` | `form_id` | Google Lead Form Asset ID |
| `campaign_id` | `campaign_id` | Google Ads Campaign ID |
| `gclid` | `custom_fields["gclid"]` | Google Click Identifier for offline conversion tracking |
| `ad_group_id` | `ad_set_id` | Google Ads Ad Group ID |
| `creative_id` | `ad_id` | Google Ads Creative / Ad ID |
| `lead_submitted_timestamp` | `external_created_at` | Epoch integer or ISO timestamp |

---

## 4. Normalization Rules & Edge Cases

### 4.1 Phone Number Normalization
1. Raw value: `"+91 98765 43210"` -> Cleaned: `"+919876543210"`
2. Raw value: `"9876543210"` (10-digit Indian national number) -> Prepend default country code: `"+919876543210"`
3. Raw value: `"09876543210"` (Leading zero) -> Strip zero, format to E.164: `"+919876543210"`
4. Invalid phone strings (e.g. `"N/A"`, `"0000000000"`) -> Recorded as `None` or quarantined; original stored in raw metadata.

### 4.2 Email Normalization
1. Raw value: `"  User.Name@Example.COM  "` -> Cleaned: `"user.name@example.com"`
2. Syntax validation: Verified against standard email regex; unparseable emails do not trigger fatal pipeline failures but set `data_quality_flags["invalid_email"] = True`.

### 4.3 Indian Real Estate Budget Parsing
- `"85 Lakh"` / `"85 L"` / `"85,00,000"` -> `8500000`
- `"1.25 Cr"` / `"1.25 Crore"` -> `12500000`
- `"50L - 75L"` -> Extracted upper limit: `7500000`
- Raw text preserved in `custom_fields["raw_budget"]`.

---

## 5. Provenance & Versioning
Every normalized lead record records:
- `normalization_version`: `"1.0.0"`
- `raw_metadata_reference`: Reference to `LeadAcquisitionEvent.id` containing the verbatim provider submission payload.
- `source`: `"META"` or `"GOOGLE_ADS"`
- `channel`: `"PAID_SOCIAL"` (Meta) or `"PAID_SEARCH"` (Google Ads).
