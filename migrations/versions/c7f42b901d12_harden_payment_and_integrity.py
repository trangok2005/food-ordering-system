"""harden payment and integrity

Revision ID: c7f42b901d12
Revises: b8895307db44
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7f42b901d12'
down_revision = 'b8895307db44'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payment_attempt',
        sa.Column('order_code', sa.String(length=30), nullable=False),
        sa.Column('payment_request_id', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='PENDING'),
        sa.Column('result_order_ids', sa.String(length=255), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_code'),
        sa.UniqueConstraint('payment_request_id'),
    )
    op.create_index('ix_payment_attempt_user_id', 'payment_attempt', ['user_id'])
    op.add_column('dish_pairing', sa.Column('lift', sa.Float(), nullable=True))
    op.create_unique_constraint('uq_restaurant_owner', 'restaurant', ['owner_id'])
    op.create_unique_constraint('uq_review_order_dish', 'review',
                                ['order_id', 'dish_id'])
    op.create_index('ix_order_restaurant_status_deadline', 'order',
                    ['restaurant_id', 'status', 'confirm_deadline'])
    op.create_index('ix_order_user_created', 'order', ['user_id', 'created_date'])


def downgrade():
    op.drop_index('ix_order_user_created', table_name='order')
    op.drop_index('ix_order_restaurant_status_deadline', table_name='order')
    op.drop_constraint('uq_review_order_dish', 'review', type_='unique')
    op.drop_constraint('uq_restaurant_owner', 'restaurant', type_='unique')
    op.drop_column('dish_pairing', 'lift')
    op.drop_index('ix_payment_attempt_user_id', table_name='payment_attempt')
    op.drop_table('payment_attempt')
