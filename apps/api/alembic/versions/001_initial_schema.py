"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. brokers table
    op.create_table(
        'brokers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('agency_name', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), server_default=sa.text("'Bengaluru'"), nullable=False),
        sa.Column('whatsapp_number', sa.String(length=20), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('subscription_status', sa.String(length=20), server_default=sa.text("'trial'"), nullable=False),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), server_default=sa.text("now() + interval '7 days'"), nullable=False),
        sa.Column('subscription_plan', sa.String(length=50), nullable=True),
        sa.Column('razorpay_customer_id', sa.String(length=255), nullable=True),
        sa.Column('razorpay_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("subscription_status IN ('trial', 'active', 'cancelled', 'expired')", name='ck_brokers_subscription_status'),
        sa.CheckConstraint("subscription_plan IS NULL OR subscription_plan IN ('monthly', 'annual')", name='ck_brokers_subscription_plan'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('whatsapp_number')
    )
    op.create_index(op.f('ix_brokers_email'), 'brokers', ['email'], unique=True)
    op.create_index(op.f('ix_brokers_phone'), 'brokers', ['phone'], unique=True)
    op.create_index(op.f('ix_brokers_whatsapp_number'), 'brokers', ['whatsapp_number'], unique=True)

    # 2. leads table
    op.create_table(
        'leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=50), server_default=sa.text("'manual'"), nullable=False),
        sa.Column('score', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('score_confidence', sa.Float(), server_default=sa.text('0.0'), nullable=False),
        sa.Column('budget_min', sa.BigInteger(), nullable=True),
        sa.Column('budget_max', sa.BigInteger(), nullable=True),
        sa.Column('property_type', sa.String(length=50), nullable=True),
        sa.Column('transaction_type', sa.String(length=20), nullable=True),
        sa.Column('preferred_locations', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('timeline', sa.String(length=50), nullable=True),
        sa.Column('loan_status', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('pipeline_stage', sa.String(length=30), server_default=sa.text("'new'"), nullable=False),
        sa.Column('notes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('qualified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("source IN ('whatsapp_forward', 'facebook', 'google', 'manual')", name='ck_leads_source'),
        sa.CheckConstraint("score IN ('hot', 'warm', 'cold', 'unqualified', 'pending')", name='ck_leads_score'),
        sa.CheckConstraint("property_type IS NULL OR property_type IN ('1bhk', '2bhk', '3bhk', 'villa', 'plot')", name='ck_leads_property_type'),
        sa.CheckConstraint("transaction_type IS NULL OR transaction_type IN ('buy', 'rent', 'lease')", name='ck_leads_transaction_type'),
        sa.CheckConstraint("timeline IS NULL OR timeline IN ('immediate', '1_month', '3_months', '6_months')", name='ck_leads_timeline'),
        sa.CheckConstraint("loan_status IS NULL OR loan_status IN ('pre_approved', 'in_process', 'not_started')", name='ck_leads_loan_status'),
        sa.CheckConstraint("status IN ('pending', 'active', 'qualified', 'converted', 'lost')", name='ck_leads_status'),
        sa.CheckConstraint("pipeline_stage IN ('new', 'contacted', 'viewing', 'negotiating', 'closed_won', 'closed_lost')", name='ck_leads_pipeline_stage'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leads_broker_id'), 'leads', ['broker_id'], unique=False)
    op.create_index(op.f('ix_leads_phone'), 'leads', ['phone'], unique=False)
    op.create_index('ix_leads_broker_id_score', 'leads', ['broker_id', 'score'], unique=False)
    op.create_index('ix_leads_broker_id_pipeline_stage', 'leads', ['broker_id', 'pipeline_stage'], unique=False)
    op.create_index('ix_leads_broker_deleted_created', 'leads', ['broker_id', 'deleted_at', 'created_at'], unique=False)

    # 3. conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('sender_type', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=20), server_default=sa.text("'text'"), nullable=False),
        sa.Column('whatsapp_message_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("direction IN ('inbound', 'outbound')", name='ck_conversations_direction'),
        sa.CheckConstraint("sender_type IN ('bot', 'lead', 'broker')", name='ck_conversations_sender_type'),
        sa.CheckConstraint("message_type IN ('text', 'image', 'template')", name='ck_conversations_message_type'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_lead_id'), 'conversations', ['lead_id'], unique=False)
    op.create_index('ix_conversations_lead_id_created_at', 'conversations', ['lead_id', 'created_at'], unique=False)

    # 4. scores table
    op.create_table(
        'scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("score IN ('hot', 'warm', 'cold')", name='ck_scores_score'),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='ck_scores_confidence'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scores_lead_id'), 'scores', ['lead_id'], unique=False)

    # 5. follow_ups table
    op.create_table(
        'follow_ups',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('sequence_number IN (1, 2, 3)', name='ck_follow_ups_sequence_number'),
        sa.CheckConstraint("status IN ('scheduled', 'sent', 'cancelled', 'failed')", name='ck_follow_ups_status'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_follow_ups_lead_id'), 'follow_ups', ['lead_id'], unique=False)
    op.create_index('ix_follow_ups_lead_status_scheduled', 'follow_ups', ['lead_id', 'status', 'scheduled_at'], unique=False)

    # 6. subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True),
        sa.Column('razorpay_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default=sa.text("'INR'"), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'created'"), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('created', 'active', 'cancelled', 'completed')", name='ck_subscriptions_status'),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_broker_id'), 'subscriptions', ['broker_id'], unique=False)


def downgrade() -> None:
    op.drop_table('subscriptions')
    op.drop_table('follow_ups')
    op.drop_table('scores')
    op.drop_table('conversations')
    op.drop_table('leads')
    op.drop_table('brokers')
