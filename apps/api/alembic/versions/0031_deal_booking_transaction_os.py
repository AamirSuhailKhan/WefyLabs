"""Part 18 — Real Estate Deal, Booking & Transaction OS.

Revision ID: 0031_deal_booking_transaction_os
Revises: 0030_enterprise_runtime
Create Date: 2026-09-24 12:00:00.000000

Creates:
  - deals
  - deal_stage_history
  - deal_offers
  - deal_reservations
  - deal_bookings
  - deal_commissions
  - deal_closings
  - deal_post_sales
  - deal_documents
  - deal_approval_requests
  - deal_commercial_audit_logs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0031_deal_booking_transaction_os'
down_revision = '0030_enterprise_runtime'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    uuid_type = postgresql.UUID(as_uuid=True) if bind.dialect.name == 'postgresql' else sa.CHAR(36)
    json_type = postgresql.JSONB() if bind.dialect.name == 'postgresql' else sa.JSON()
    money_type = sa.Numeric(precision=20, scale=4)

    # 1. deals
    if 'deals' not in tables:
        op.create_table(
            'deals',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('lead_id', uuid_type, sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('property_id', uuid_type, sa.ForeignKey('property_listings.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('assigned_agent_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('legacy_deal_transaction_id', uuid_type, sa.ForeignKey('deal_transactions.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('deal_reference', sa.String(50), nullable=False, index=True),
            sa.Column('deal_title', sa.String(255), nullable=False),
            sa.Column('current_stage', sa.String(30), nullable=False, server_default='opportunity', index=True),
            sa.Column('previous_stage', sa.String(30), nullable=True),
            sa.Column('stage_entered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('stage_duration_hours', sa.Integer(), nullable=True),
            sa.Column('agreed_price', money_type, nullable=True),
            sa.Column('offer_price', money_type, nullable=True),
            sa.Column('final_transaction_price', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='AED'),
            sa.Column('commission_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('commission_amount', money_type, nullable=True),
            sa.Column('commission_split_details', json_type, nullable=True),
            sa.Column('closing_probability_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='80.00'),
            sa.Column('risk_level', sa.String(20), nullable=False, server_default='medium'),
            sa.Column('risk_factors', json_type, nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE', index=True),
            sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('close_reason', sa.String(255), nullable=True),
            sa.Column('lost_reason', sa.String(255), nullable=True),
            sa.Column('idempotency_key', sa.String(128), nullable=True, index=True),
            sa.Column('tags', json_type, nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('metadata_json', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column('deleted_by', sa.String(36), nullable=True),
            sa.UniqueConstraint('organization_id', 'deal_reference', name='uq_deal_ref_per_org'),
            sa.UniqueConstraint('organization_id', 'idempotency_key', name='uq_deal_idempotency_per_org'),
        )

    # 2. deal_stage_history
    if 'deal_stage_history' not in tables:
        op.create_table(
            'deal_stage_history',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('from_stage', sa.String(30), nullable=True),
            sa.Column('to_stage', sa.String(30), nullable=False),
            sa.Column('transitioned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
            sa.Column('transitioned_by_id', sa.String(64), nullable=True),
            sa.Column('transitioned_by_type', sa.String(20), nullable=False, server_default='HUMAN'),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('duration_hours_in_previous_stage', sa.Integer(), nullable=True),
            sa.Column('metadata_json', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 3. deal_offers
    if 'deal_offers' not in tables:
        op.create_table(
            'deal_offers',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('offer_price', money_type, nullable=False),
            sa.Column('currency', sa.String(3), nullable=False, server_default='AED'),
            sa.Column('listing_price', money_type, nullable=True),
            sa.Column('discount_amount', money_type, nullable=True),
            sa.Column('discount_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('payment_plan', sa.String(50), nullable=True),
            sa.Column('token_amount', money_type, nullable=True),
            sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
            sa.Column('possession_date_requested', sa.DateTime(timezone=True), nullable=True),
            sa.Column('special_conditions', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='DRAFT', index=True),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('offer_history', json_type, nullable=False),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('counter_offer_price', money_type, nullable=True),
            sa.Column('submitted_by_id', sa.String(64), nullable=True),
            sa.Column('accepted_by_id', sa.String(64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 4. deal_reservations
    if 'deal_reservations' not in tables:
        op.create_table(
            'deal_reservations',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('property_id', uuid_type, sa.ForeignKey('property_listings.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('reservation_amount', money_type, nullable=True),
            sa.Column('currency', sa.String(3), nullable=False, server_default='AED'),
            sa.Column('reserved_price', money_type, nullable=True),
            sa.Column('reserved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='ACTIVE', index=True),
            sa.Column('reservation_form_url', sa.String(512), nullable=True),
            sa.Column('reservation_form_signed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reservation_notes', sa.Text(), nullable=True),
            sa.Column('reserved_by_agent_id', sa.String(64), nullable=True),
            sa.Column('customer_name', sa.String(255), nullable=True),
            sa.Column('customer_phone', sa.String(30), nullable=True),
            sa.Column('customer_email', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 5. deal_bookings
    if 'deal_bookings' not in tables:
        op.create_table(
            'deal_bookings',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('booking_reference', sa.String(50), nullable=False, index=True),
            sa.Column('token_amount', money_type, nullable=True),
            sa.Column('token_paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('token_payment_mode', sa.String(30), nullable=True),
            sa.Column('token_receipt_reference', sa.String(100), nullable=True),
            sa.Column('booked_price', money_type, nullable=False),
            sa.Column('currency', sa.String(3), nullable=False, server_default='AED'),
            sa.Column('payment_plan_type', sa.String(50), nullable=True),
            sa.Column('down_payment_amount', money_type, nullable=True),
            sa.Column('down_payment_due_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='PENDING_PAYMENT', index=True),
            sa.Column('booked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('booking_form_signed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('booking_form_url', sa.String(512), nullable=True),
            sa.Column('payment_schedule', json_type, nullable=True),
            sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cancellation_reason', sa.Text(), nullable=True),
            sa.Column('forfeiture_amount', money_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('organization_id', 'booking_reference', name='uq_booking_ref_per_org'),
        )

    # 6. deal_commissions
    if 'deal_commissions' not in tables:
        op.create_table(
            'deal_commissions',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('broker_id', uuid_type, sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('transaction_price', money_type, nullable=False),
            sa.Column('currency', sa.String(3), nullable=False, server_default='AED'),
            sa.Column('commission_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column('gross_commission', money_type, nullable=False),
            sa.Column('tax_deducted', money_type, nullable=True),
            sa.Column('net_commission', money_type, nullable=True),
            sa.Column('commission_splits', json_type, nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', index=True),
            sa.Column('invoice_reference', sa.String(100), nullable=True, index=True),
            sa.Column('invoiced_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('payment_reference', sa.String(100), nullable=True),
            sa.Column('payment_mode', sa.String(30), nullable=True),
            sa.Column('disputed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('dispute_reason', sa.Text(), nullable=True),
            sa.Column('dispute_resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 7. deal_closings
    if 'deal_closings' not in tables:
        op.create_table(
            'deal_closings',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('closing_checklist', json_type, nullable=True),
            sa.Column('registration_authority', sa.String(100), nullable=True),
            sa.Column('registration_number', sa.String(100), nullable=True, index=True),
            sa.Column('registration_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('title_deed_number', sa.String(100), nullable=True, index=True),
            sa.Column('title_deed_issued_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('handover_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('keys_handed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('handover_notes', sa.Text(), nullable=True),
            sa.Column('status', sa.String(30), nullable=False, server_default='IN_PROGRESS', index=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 8. deal_post_sales
    if 'deal_post_sales' not in tables:
        op.create_table(
            'deal_post_sales',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('customer_satisfaction_score', sa.Integer(), nullable=True),
            sa.Column('nps_score', sa.Integer(), nullable=True),
            sa.Column('feedback_text', sa.Text(), nullable=True),
            sa.Column('feedback_collected_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('referral_given', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('referral_lead_ids', json_type, nullable=True),
            sa.Column('after_sales_interactions', json_type, nullable=True),
            sa.Column('success_factors', json_type, nullable=True),
            sa.Column('obstacle_factors', json_type, nullable=True),
            sa.Column('days_to_close', sa.Integer(), nullable=True),
            sa.Column('ai_recommendation_followed', sa.Boolean(), nullable=True),
            sa.Column('ai_recommendations_accepted', sa.Integer(), nullable=True),
            sa.Column('ai_recommendations_rejected', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 9. deal_documents
    if 'deal_documents' not in tables:
        op.create_table(
            'deal_documents',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('document_type', sa.String(100), nullable=False, index=True),
            sa.Column('document_name', sa.String(255), nullable=False),
            sa.Column('required_at_stage', sa.String(30), nullable=False),
            sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('status', sa.String(30), nullable=False, server_default='REQUIRED', index=True),
            sa.Column('file_url', sa.String(512), nullable=True),
            sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('uploaded_by_id', sa.String(64), nullable=True),
            sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('verified_by_id', sa.String(64), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 10. deal_approval_requests
    if 'deal_approval_requests' not in tables:
        op.create_table(
            'deal_approval_requests',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('requested_by_id', sa.String(64), nullable=True),
            sa.Column('requested_by_type', sa.String(20), nullable=False, server_default='HUMAN'),
            sa.Column('action_type', sa.String(50), nullable=False, index=True),
            sa.Column('action_payload', json_type, nullable=True),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('idempotency_key', sa.String(128), nullable=False, unique=True, index=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', index=True),
            sa.Column('reviewed_by_id', sa.String(64), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('review_notes', sa.Text(), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # 11. deal_commercial_audit_logs
    if 'deal_commercial_audit_logs' not in tables:
        op.create_table(
            'deal_commercial_audit_logs',
            sa.Column('id', uuid_type, primary_key=True),
            sa.Column('deal_id', uuid_type, sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('organization_id', uuid_type, nullable=False, index=True),
            sa.Column('event_type', sa.String(100), nullable=False, index=True),
            sa.Column('actor_id', sa.String(64), nullable=True),
            sa.Column('actor_type', sa.String(20), nullable=False, server_default='HUMAN'),
            sa.Column('resource_type', sa.String(50), nullable=False),
            sa.Column('resource_id', sa.String(64), nullable=False),
            sa.Column('previous_state', json_type, nullable=True),
            sa.Column('new_state', json_type, nullable=True),
            sa.Column('change_summary', sa.Text(), nullable=True),
            sa.Column('idempotency_key', sa.String(128), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        )


def downgrade():
    op.drop_table('deal_commercial_audit_logs')
    op.drop_table('deal_approval_requests')
    op.drop_table('deal_documents')
    op.drop_table('deal_post_sales')
    op.drop_table('deal_closings')
    op.drop_table('deal_commissions')
    op.drop_table('deal_bookings')
    op.drop_table('deal_reservations')
    op.drop_table('deal_offers')
    op.drop_table('deal_stage_history')
    op.drop_table('deals')
