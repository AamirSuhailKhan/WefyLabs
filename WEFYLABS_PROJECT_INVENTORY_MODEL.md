# WEFYLABS PROJECT & INVENTORY DOMAIN MODEL
## Canonical Data Specifications for Institutional Real Estate Supply

---

## 1. Domain Entities & Database Schema

### 1.1 Developer Entity (`real_estate_developers`)
```sql
CREATE TABLE real_estate_developers (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    broker_id UUID NOT NULL,
    developer_code VARCHAR(32) UNIQUE NOT NULL,
    legal_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    logo_url VARCHAR(1024),
    rera_number VARCHAR(128),
    gst_number VARCHAR(64),
    pan_number VARCHAR(32),
    cin_number VARCHAR(64),
    primary_email VARCHAR(255),
    primary_phone VARCHAR(64),
    website_url VARCHAR(512),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country_code VARCHAR(8) DEFAULT 'IN',
    years_in_business INTEGER,
    status VARCHAR(32) DEFAULT 'active',
    rating NUMERIC(3, 2),
    total_projects INTEGER DEFAULT 0,
    completed_projects INTEGER DEFAULT 0,
    ongoing_projects INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 1.2 Project Entity (`real_estate_projects`)
```sql
CREATE TABLE real_estate_projects (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    broker_id UUID NOT NULL,
    developer_id UUID REFERENCES real_estate_developers(id),
    project_code VARCHAR(32) UNIQUE NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    tagline VARCHAR(255),
    description TEXT,
    project_type VARCHAR(64) DEFAULT 'residential',
    transaction_type VARCHAR(32) DEFAULT 'sale',
    status VARCHAR(32) DEFAULT 'announced',
    address TEXT,
    locality VARCHAR(128),
    city VARCHAR(100),
    state VARCHAR(100),
    country_code VARCHAR(8) DEFAULT 'IN',
    pincode VARCHAR(20),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    rera_number VARCHAR(128),
    total_towers INTEGER DEFAULT 1,
    total_floors INTEGER DEFAULT 1,
    total_units INTEGER DEFAULT 0,
    available_units INTEGER DEFAULT 0,
    reserved_units INTEGER DEFAULT 0,
    booked_units INTEGER DEFAULT 0,
    sold_units INTEGER DEFAULT 0,
    price_min NUMERIC(20, 4),
    price_max NUMERIC(20, 4),
    currency VARCHAR(8) DEFAULT 'INR',
    amenities JSONB DEFAULT '[]',
    unit_configs JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 1.3 Authoritative Unit Entity (`project_units`)
```sql
CREATE TABLE project_units (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    broker_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES real_estate_projects(id),
    phase_id UUID,
    building_id UUID,
    floor_id UUID,
    property_listing_id UUID,
    unit_code VARCHAR(32) UNIQUE NOT NULL,
    unit_number VARCHAR(64) NOT NULL,
    unit_type VARCHAR(64) NOT NULL,
    floor_number INTEGER,
    facing VARCHAR(32),
    carpet_area NUMERIC(12, 4),
    built_up_area NUMERIC(12, 4),
    super_built_up_area NUMERIC(12, 4),
    area_unit VARCHAR(16) DEFAULT 'sqft',
    bedrooms INTEGER DEFAULT 0,
    bathrooms INTEGER DEFAULT 0,
    balconies INTEGER DEFAULT 0,
    parking_slots INTEGER DEFAULT 0,
    base_price NUMERIC(20, 4),
    price_per_sqft NUMERIC(20, 4),
    floor_rise_amount NUMERIC(20, 4),
    amenity_charges NUMERIC(20, 4),
    parking_charges NUMERIC(20, 4),
    total_price NUMERIC(20, 4),
    currency VARCHAR(8) DEFAULT 'INR',
    inventory_status VARCHAR(32) DEFAULT 'available',
    reserved_by_deal_id UUID,
    booked_by_deal_id UUID,
    channel_partner_id UUID,
    reserved_at TIMESTAMP WITH TIME ZONE,
    reservation_expires_at TIMESTAMP WITH TIME ZONE,
    booked_at TIMESTAMP WITH TIME ZONE,
    sold_at TIMESTAMP WITH TIME ZONE,
    last_reservation_idempotency_key VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 2. Numerical Precision Guarantee
All monetary columns utilize SQL `Numeric(20, 4)` and Python `Decimal` objects. Floating-point conversions are prohibited in commercial calculations, eliminating IEEE-754 rounding drift.
