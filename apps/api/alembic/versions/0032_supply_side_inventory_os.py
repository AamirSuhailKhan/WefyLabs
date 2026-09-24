"""Part 19 - Real Estate Supply, Project, Unit Inventory & Channel Partner Network OS.

Revision ID: 0032_supply_side_inventory_os
Revises: 0031_deal_booking_transaction_os
Create Date: 2026-09-24 18:10:00.000000

Creates:
  - real_estate_developers
  - real_estate_projects
  - project_phases
  - project_buildings
  - project_floors
  - project_units
  - project_unit_status_logs
  - project_price_books
  - price_book_entries
  - project_media
  - channel_partners
  - cp_project_agreements
  - cp_commissions
  - inventory_availability_snapshots
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0032_supply_side_inventory_os'
down_revision = '0031_deal_booking_transaction_os'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    uuid_type = postgresql.UUID(as_uuid=True) if bind.dialect.name == 'postgresql' else sa.CHAR(36)
    json_type = postgresql.JSONB() if bind.dialect.name == 'postgresql' else sa.JSON()
    money_type = sa.Numeric(precision=20, scale=4)
    pct_type = sa.Numeric(precision=7, scale=4)

    # 1. real_estate_developers
    if 'real_estate_developers' not in tables:
        op.create_table(
            'real_estate_developers',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('developer_code', sa.String(50), nullable=False),
            sa.Column('legal_name', sa.String(255), nullable=False),
            sa.Column('trade_name', sa.String(255), nullable=True),
            sa.Column('logo_url', sa.String(512), nullable=True),
            sa.Column('rera_number', sa.String(100), nullable=True),
            sa.Column('gst_number', sa.String(50), nullable=True),
            sa.Column('pan_number', sa.String(30), nullable=True),
            sa.Column('cin_number', sa.String(30), nullable=True),
            sa.Column('primary_email', sa.String(255), nullable=True),
            sa.Column('primary_phone', sa.String(50), nullable=True),
            sa.Column('website_url', sa.String(512), nullable=True),
            sa.Column('address', sa.String(500), nullable=True),
            sa.Column('city', sa.String(100), nullable=True),
            sa.Column('state', sa.String(100), nullable=True),
            sa.Column('country_code', sa.String(2), nullable=False, server_default='IN'),
            sa.Column('rating', pct_type, nullable=True),
            sa.Column('total_projects', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('completed_projects', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('ongoing_projects', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('years_in_business', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='active'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('extended_fields', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('organization_id', 'developer_code', name='uq_org_developer_code'),
        )
        op.create_index('ix_developer_org_status', 'real_estate_developers', ['organization_id', 'status'])
        op.create_index('ix_real_estate_developers_developer_code', 'real_estate_developers', ['developer_code'])
        op.create_index('ix_real_estate_developers_broker_id', 'real_estate_developers', ['broker_id'])
        op.create_index('ix_real_estate_developers_organization_id', 'real_estate_developers', ['organization_id'])

    # 2. real_estate_projects
    if 'real_estate_projects' not in tables:
        op.create_table(
            'real_estate_projects',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('developer_id', uuid_type, sa.ForeignKey('real_estate_developers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('project_code', sa.String(50), nullable=False),
            sa.Column('project_name', sa.String(255), nullable=False),
            sa.Column('slug', sa.String(255), nullable=True),
            sa.Column('tagline', sa.String(512), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('hero_image_url', sa.String(512), nullable=True),
            sa.Column('brochure_url', sa.String(512), nullable=True),
            sa.Column('project_type', sa.String(50), nullable=False, server_default='residential'),
            sa.Column('transaction_type', sa.String(30), nullable=False, server_default='primary_sale'),
            sa.Column('status', sa.String(40), nullable=False, server_default='announced'),
            sa.Column('rera_number', sa.String(100), nullable=True),
            sa.Column('rera_expiry_date', sa.Date(), nullable=True),
            sa.Column('address', sa.String(500), nullable=True),
            sa.Column('micro_market', sa.String(100), nullable=True),
            sa.Column('locality', sa.String(100), nullable=True),
            sa.Column('city', sa.String(100), nullable=True),
            sa.Column('state', sa.String(100), nullable=True),
            sa.Column('country_code', sa.String(2), nullable=False, server_default='IN'),
            sa.Column('postal_code', sa.String(20), nullable=True),
            sa.Column('latitude', sa.Numeric(10, 7), nullable=True),
            sa.Column('longitude', sa.Numeric(10, 7), nullable=True),
            sa.Column('launch_date', sa.Date(), nullable=True),
            sa.Column('possession_date', sa.Date(), nullable=True),
            sa.Column('completion_date', sa.Date(), nullable=True),
            sa.Column('price_min', money_type, nullable=True),
            sa.Column('price_max', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sold_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reserved_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cp_commission_pct', pct_type, nullable=True),
            sa.Column('cp_commission_notes', sa.Text(), nullable=True),
            sa.Column('amenities', json_type, nullable=True),
            sa.Column('highlights', json_type, nullable=True),
            sa.Column('unit_configs', json_type, nullable=True),
            sa.Column('area_range', json_type, nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('extended_fields', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('organization_id', 'project_code', name='uq_org_project_code'),
        )
        op.create_index('ix_project_org_status', 'real_estate_projects', ['organization_id', 'status'])
        op.create_index('ix_project_city_type', 'real_estate_projects', ['city', 'project_type'])
        op.create_index('ix_project_locality', 'real_estate_projects', ['locality'])
        op.create_index('ix_project_price_min', 'real_estate_projects', ['price_min'])
        op.create_index('ix_real_estate_projects_project_code', 'real_estate_projects', ['project_code'])
        op.create_index('ix_real_estate_projects_developer_id', 'real_estate_projects', ['developer_id'])
        op.create_index('ix_real_estate_projects_broker_id', 'real_estate_projects', ['broker_id'])
        op.create_index('ix_real_estate_projects_organization_id', 'real_estate_projects', ['organization_id'])

    # 3. channel_partners (must precede project_units which FK to it)
    if 'channel_partners' not in tables:
        op.create_table(
            'channel_partners',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('cp_code', sa.String(50), nullable=False),
            sa.Column('firm_name', sa.String(255), nullable=True),
            sa.Column('contact_name', sa.String(255), nullable=False),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('phone', sa.String(50), nullable=True),
            sa.Column('whatsapp_number', sa.String(50), nullable=True),
            sa.Column('profile_image_url', sa.String(512), nullable=True),
            sa.Column('rera_number', sa.String(100), nullable=True),
            sa.Column('pan_number', sa.String(30), nullable=True),
            sa.Column('gst_number', sa.String(50), nullable=True),
            sa.Column('kyc_verified', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('kyc_verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('city', sa.String(100), nullable=True),
            sa.Column('state', sa.String(100), nullable=True),
            sa.Column('country_code', sa.String(2), nullable=False, server_default='IN'),
            sa.Column('tier', sa.String(20), nullable=False, server_default='standard'),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending_kyc'),
            sa.Column('default_commission_pct', pct_type, nullable=True),
            sa.Column('total_deals_sourced', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_deals_closed', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_commission_earned', money_type, nullable=True),
            sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('extended_fields', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('organization_id', 'cp_code', name='uq_org_cp_code'),
        )
        op.create_index('ix_cp_org_status', 'channel_partners', ['organization_id', 'status'])
        op.create_index('ix_cp_org_tier', 'channel_partners', ['organization_id', 'tier'])
        op.create_index('ix_cp_city', 'channel_partners', ['city'])
        op.create_index('ix_cp_rera', 'channel_partners', ['rera_number'])
        op.create_index('ix_channel_partners_cp_code', 'channel_partners', ['cp_code'])
        op.create_index('ix_channel_partners_email', 'channel_partners', ['email'])
        op.create_index('ix_channel_partners_phone', 'channel_partners', ['phone'])
        op.create_index('ix_channel_partners_broker_id', 'channel_partners', ['broker_id'])
        op.create_index('ix_channel_partners_organization_id', 'channel_partners', ['organization_id'])

    # 4. project_phases
    if 'project_phases' not in tables:
        op.create_table(
            'project_phases',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('phase_code', sa.String(50), nullable=False),
            sa.Column('phase_name', sa.String(255), nullable=False),
            sa.Column('phase_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('phase_type', sa.String(30), nullable=False, server_default='tower'),
            sa.Column('status', sa.String(40), nullable=False, server_default='announced'),
            sa.Column('rera_number', sa.String(100), nullable=True),
            sa.Column('total_floors', sa.Integer(), nullable=True),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('launch_date', sa.Date(), nullable=True),
            sa.Column('possession_date', sa.Date(), nullable=True),
            sa.Column('completion_date', sa.Date(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('extended_fields', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('project_id', 'phase_code', name='uq_phase_code_per_project'),
        )
        op.create_index('ix_phase_project_status', 'project_phases', ['project_id', 'status'])
        op.create_index('ix_phase_org', 'project_phases', ['organization_id'])
        op.create_index('ix_project_phases_project_id', 'project_phases', ['project_id'])

    # 5. project_buildings
    if 'project_buildings' not in tables:
        op.create_table(
            'project_buildings',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('phase_id', uuid_type, sa.ForeignKey('project_phases.id', ondelete='CASCADE'), nullable=False),
            sa.Column('building_code', sa.String(50), nullable=False),
            sa.Column('building_name', sa.String(255), nullable=False),
            sa.Column('total_floors', sa.Integer(), nullable=True),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('construction_status', sa.String(50), nullable=False, server_default='under_construction'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('phase_id', 'building_code', name='uq_building_code_per_phase'),
        )
        op.create_index('ix_building_phase', 'project_buildings', ['phase_id'])
        op.create_index('ix_building_org', 'project_buildings', ['organization_id'])

    # 6. project_floors
    if 'project_floors' not in tables:
        op.create_table(
            'project_floors',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('building_id', uuid_type, sa.ForeignKey('project_buildings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('floor_number', sa.Integer(), nullable=False),
            sa.Column('floor_name', sa.String(50), nullable=True),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('building_id', 'floor_number', name='uq_floor_per_building'),
        )
        op.create_index('ix_floor_building', 'project_floors', ['building_id'])

    # 7. project_units
    if 'project_units' not in tables:
        op.create_table(
            'project_units',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('phase_id', uuid_type, sa.ForeignKey('project_phases.id', ondelete='SET NULL'), nullable=True),
            sa.Column('building_id', uuid_type, sa.ForeignKey('project_buildings.id', ondelete='SET NULL'), nullable=True),
            sa.Column('floor_id', uuid_type, sa.ForeignKey('project_floors.id', ondelete='SET NULL'), nullable=True),
            sa.Column('property_listing_id', uuid_type, sa.ForeignKey('property_listings.id', ondelete='SET NULL'), nullable=True),
            sa.Column('unit_code', sa.String(100), nullable=False),
            sa.Column('unit_number', sa.String(50), nullable=False),
            sa.Column('unit_type', sa.String(50), nullable=False),
            sa.Column('floor_number', sa.Integer(), nullable=True),
            sa.Column('facing', sa.String(50), nullable=True),
            sa.Column('carpet_area', sa.Numeric(10, 2), nullable=True),
            sa.Column('built_up_area', sa.Numeric(10, 2), nullable=True),
            sa.Column('super_built_up_area', sa.Numeric(10, 2), nullable=True),
            sa.Column('area_unit', sa.String(20), nullable=False, server_default='sqft'),
            sa.Column('bedrooms', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('bathrooms', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('balconies', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('parking_slots', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('study_rooms', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('servant_quarters', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('base_price', money_type, nullable=True),
            sa.Column('price_per_sqft', money_type, nullable=True),
            sa.Column('floor_rise_amount', money_type, nullable=True),
            sa.Column('amenity_charges', money_type, nullable=True),
            sa.Column('parking_charges', money_type, nullable=True),
            sa.Column('total_price', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
            sa.Column('inventory_status', sa.String(30), nullable=False, server_default='available'),
            sa.Column('reserved_by_deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reserved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reservation_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('booked_by_deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('booked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('sold_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('possession_date', sa.Date(), nullable=True),
            sa.Column('last_reservation_idempotency_key', sa.String(128), nullable=True),
            sa.Column('channel_partner_id', uuid_type, sa.ForeignKey('channel_partners.id', ondelete='SET NULL'), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('extended_fields', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('project_id', 'unit_code', name='uq_unit_code_per_project'),
        )
        op.create_index('ix_unit_org_status', 'project_units', ['organization_id', 'inventory_status'])
        op.create_index('ix_unit_project_status', 'project_units', ['project_id', 'inventory_status'])
        op.create_index('ix_unit_type_status', 'project_units', ['unit_type', 'inventory_status'])
        op.create_index('ix_unit_floor_facing', 'project_units', ['floor_number', 'facing'])
        op.create_index('ix_unit_price', 'project_units', ['base_price'])
        op.create_index('ix_unit_total_price', 'project_units', ['total_price'])
        op.create_index('ix_project_units_unit_code', 'project_units', ['unit_code'])
        op.create_index('ix_project_units_unit_type', 'project_units', ['unit_type'])
        op.create_index('ix_project_units_project_id', 'project_units', ['project_id'])
        op.create_index('ix_project_units_floor_number', 'project_units', ['floor_number'])
        op.create_index('ix_project_units_broker_id', 'project_units', ['broker_id'])
        op.create_index('ix_project_units_organization_id', 'project_units', ['organization_id'])

    # 8. project_unit_status_logs
    if 'project_unit_status_logs' not in tables:
        op.create_table(
            'project_unit_status_logs',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('unit_id', uuid_type, sa.ForeignKey('project_units.id', ondelete='CASCADE'), nullable=False),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('previous_status', sa.String(30), nullable=True),
            sa.Column('new_status', sa.String(30), nullable=False),
            sa.Column('reason', sa.String(255), nullable=True),
            sa.Column('changed_by_id', uuid_type, nullable=True),
            sa.Column('changed_by_type', sa.String(30), nullable=False, server_default='user'),
            sa.Column('deal_id', uuid_type, nullable=True),
            sa.Column('outbox_event_id', uuid_type, nullable=True),
            sa.Column('metadata_json', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_unit_status_log_unit', 'project_unit_status_logs', ['unit_id'])
        op.create_index('ix_unit_status_log_org_new', 'project_unit_status_logs', ['organization_id', 'new_status'])

    # 9. project_price_books
    if 'project_price_books' not in tables:
        op.create_table(
            'project_price_books',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_until', sa.Date(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('base_price_floor', money_type, nullable=True),
            sa.Column('floor_rise_per_floor', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('published_by_id', uuid_type, nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('project_id', 'version', name='uq_pricebook_version'),
        )
        op.create_index('ix_pricebook_project_status', 'project_price_books', ['project_id', 'status'])
        op.create_index('ix_pricebook_org', 'project_price_books', ['organization_id'])

    # 10. price_book_entries
    if 'price_book_entries' not in tables:
        op.create_table(
            'price_book_entries',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('price_book_id', uuid_type, sa.ForeignKey('project_price_books.id', ondelete='CASCADE'), nullable=False),
            sa.Column('unit_id', uuid_type, sa.ForeignKey('project_units.id', ondelete='CASCADE'), nullable=True),
            sa.Column('unit_type', sa.String(50), nullable=True),
            sa.Column('floor_number', sa.Integer(), nullable=True),
            sa.Column('base_price', money_type, nullable=False),
            sa.Column('price_per_sqft', money_type, nullable=True),
            sa.Column('floor_rise_amount', money_type, nullable=True),
            sa.Column('parking_charges', money_type, nullable=True),
            sa.Column('other_charges', money_type, nullable=True),
            sa.Column('total_price', money_type, nullable=True),
            sa.Column('notes', sa.String(512), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_pbe_book_unit', 'price_book_entries', ['price_book_id', 'unit_id'])
        op.create_index('ix_pbe_book_type', 'price_book_entries', ['price_book_id', 'unit_type'])

    # 11. project_media
    if 'project_media' not in tables:
        op.create_table(
            'project_media',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('media_type', sa.String(30), nullable=False),
            sa.Column('url', sa.String(512), nullable=False),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_private', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('file_size_bytes', sa.Integer(), nullable=True),
            sa.Column('mime_type', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_project_media_project', 'project_media', ['project_id', 'media_type'])

    # 12. cp_project_agreements
    if 'cp_project_agreements' not in tables:
        op.create_table(
            'cp_project_agreements',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('channel_partner_id', uuid_type, sa.ForeignKey('channel_partners.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('valid_from', sa.Date(), nullable=False),
            sa.Column('valid_until', sa.Date(), nullable=True),
            sa.Column('commission_pct', pct_type, nullable=True),
            sa.Column('brokerage_fee', money_type, nullable=True),
            sa.Column('commission_slabs', json_type, nullable=True),
            sa.Column('is_exclusive', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('document_url', sa.String(512), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('channel_partner_id', 'project_id', name='uq_cp_project_agreement'),
        )
        op.create_index('ix_cp_agreement_project', 'cp_project_agreements', ['project_id', 'is_active'])
        op.create_index('ix_cp_agreement_org', 'cp_project_agreements', ['organization_id'])
        op.create_index('ix_cp_project_agreements_channel_partner_id', 'cp_project_agreements', ['channel_partner_id'])

    # 13. cp_commissions
    if 'cp_commissions' not in tables:
        op.create_table(
            'cp_commissions',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('channel_partner_id', uuid_type, sa.ForeignKey('channel_partners.id', ondelete='CASCADE'), nullable=False),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('unit_id', uuid_type, sa.ForeignKey('project_units.id', ondelete='SET NULL'), nullable=True),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('transaction_value', money_type, nullable=False),
            sa.Column('commission_pct', pct_type, nullable=False),
            sa.Column('commission_amount', money_type, nullable=False),
            sa.Column('gst_amount', money_type, nullable=True),
            sa.Column('tds_amount', money_type, nullable=True),
            sa.Column('net_payable', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
            sa.Column('payment_status', sa.String(30), nullable=False, server_default='pending'),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('payment_reference', sa.String(255), nullable=True),
            sa.Column('invoice_number', sa.String(100), nullable=True),
            sa.Column('invoice_url', sa.String(512), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_cp_commission_cp_status', 'cp_commissions', ['channel_partner_id', 'payment_status'])
        op.create_index('ix_cp_commission_org', 'cp_commissions', ['organization_id'])
        op.create_index('ix_cp_commission_deal', 'cp_commissions', ['deal_id'])
        op.create_index('ix_cp_commissions_unit_id', 'cp_commissions', ['unit_id'])
        op.create_index('ix_cp_commissions_project_id', 'cp_commissions', ['project_id'])

    # 14. inventory_availability_snapshots
    if 'inventory_availability_snapshots' not in tables:
        op.create_table(
            'inventory_availability_snapshots',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False),
            sa.Column('project_id', uuid_type, sa.ForeignKey('real_estate_projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('snapshot_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reserved_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('booked_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sold_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('blocked_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('under_offer_units', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('by_unit_type', json_type, nullable=True),
            sa.Column('by_phase', json_type, nullable=True),
            sa.Column('price_range_available', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_inv_snapshot_project_at', 'inventory_availability_snapshots', ['project_id', 'snapshot_at'])
        op.create_index('ix_inv_snapshot_org', 'inventory_availability_snapshots', ['organization_id'])


def downgrade():
    op.drop_table('inventory_availability_snapshots')
    op.drop_table('cp_commissions')
    op.drop_table('cp_project_agreements')
    op.drop_table('project_media')
    op.drop_table('price_book_entries')
    op.drop_table('project_price_books')
    op.drop_table('project_unit_status_logs')
    op.drop_table('project_units')
    op.drop_table('project_floors')
    op.drop_table('project_buildings')
    op.drop_table('project_phases')
    op.drop_table('channel_partners')
    op.drop_table('real_estate_projects')
    op.drop_table('real_estate_developers')
