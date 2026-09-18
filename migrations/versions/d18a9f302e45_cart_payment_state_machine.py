"""cart and payment state machine

Revision ID: d18a9f302e45
Revises: c7f42b901d12
Create Date: 2026-09-17
"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa


revision = 'd18a9f302e45'
down_revision = 'c7f42b901d12'
branch_labels = None
depends_on = None


def _deduplicate_carts():
    connection = op.get_bind()
    rows = connection.execute(
        sa.text('SELECT id, user_id FROM cart ORDER BY user_id, id')
    ).fetchall()
    seen = set()
    duplicate_ids = []
    for cart_id, user_id in rows:
        if user_id in seen:
            duplicate_ids.append(cart_id)
        else:
            seen.add(user_id)
    for cart_id in duplicate_ids:
        connection.execute(
            sa.text('DELETE FROM cart_item WHERE cart_id = :cart_id'),
            {'cart_id': cart_id},
        )
        connection.execute(
            sa.text('DELETE FROM cart WHERE id = :cart_id'),
            {'cart_id': cart_id},
        )


def _backfill_attempts():
    connection = op.get_bind()
    rows = connection.execute(
        sa.text('SELECT id, payload, status FROM payment_attempt ORDER BY id DESC')
    ).fetchall()
    active_hashes = set()
    for attempt_id, payload, old_status in rows:
        try:
            parsed = json.loads(payload)
            canonical = json.dumps(
                parsed, ensure_ascii=False, sort_keys=True, separators=(',', ':')
            )
        except (TypeError, ValueError):
            canonical = payload or str(attempt_id)
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        if old_status == 'PROCESSED':
            status = 'FINALIZED'
            snapshot_key = None
        elif digest in active_hashes:
            status = 'FAILED'
            snapshot_key = None
        else:
            status = 'CREATED'
            snapshot_key = digest
            active_hashes.add(digest)
        connection.execute(sa.text(
            'UPDATE payment_attempt SET snapshot_hash = :digest, '
            'snapshot_key = :snapshot_key, status = :status '
            'WHERE id = :attempt_id'
        ), {
            'digest': digest,
            'snapshot_key': snapshot_key,
            'status': status,
            'attempt_id': attempt_id,
        })


def upgrade():
    _deduplicate_carts()
    with op.batch_alter_table('cart') as batch_op:
        # Keep an index beginning with user_id available for the MySQL FK.
        batch_op.create_unique_constraint('uq_cart_user', ['user_id'])
        batch_op.drop_constraint('uq_cart_user_restaurant', type_='unique')

    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.alter_column(
            'min_order_amount', existing_type=sa.Float(),
            type_=sa.Numeric(12, 2), existing_nullable=True,
        )
        batch_op.create_check_constraint(
            'chk_restaurant_min_order_nonnegative',
            'min_order_amount IS NULL OR min_order_amount >= 0',
        )

    with op.batch_alter_table('dish') as batch_op:
        batch_op.create_check_constraint('chk_dish_price_nonnegative', 'price >= 0')
    with op.batch_alter_table('cart_item') as batch_op:
        batch_op.create_check_constraint(
            'chk_cart_item_quantity_positive', 'quantity > 0'
        )

    op.add_column('payment_attempt', sa.Column(
        'snapshot_hash', sa.String(64), nullable=False, server_default=''
    ))
    op.add_column('payment_attempt', sa.Column('snapshot_key', sa.String(64)))
    op.add_column('payment_attempt', sa.Column('checkout_url', sa.String(1000)))
    op.add_column('payment_attempt', sa.Column('error_code', sa.String(50)))
    op.add_column('payment_attempt', sa.Column('last_error', sa.Text()))
    op.add_column('payment_attempt', sa.Column(
        'retry_count', sa.Integer(), nullable=False, server_default='0'
    ))
    op.add_column('payment_attempt', sa.Column(
        'updated_at', sa.DateTime(), nullable=False,
        server_default=sa.func.current_timestamp(),
    ))
    _backfill_attempts()
    with op.batch_alter_table('payment_attempt') as batch_op:
        batch_op.alter_column(
            'payment_request_id', existing_type=sa.String(255), nullable=True
        )
        batch_op.alter_column(
            'status', existing_type=sa.String(20), type_=sa.String(32),
            existing_nullable=False, server_default=None,
        )
        batch_op.alter_column(
            'snapshot_hash', existing_type=sa.String(64), nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'retry_count', existing_type=sa.Integer(), nullable=False,
            server_default=None,
        )
        batch_op.create_unique_constraint(
            'uq_payment_attempt_snapshot_key', ['snapshot_key']
        )
        batch_op.create_check_constraint(
            'chk_payment_attempt_amount_positive', 'amount > 0'
        )
        batch_op.create_check_constraint(
            'chk_payment_attempt_retry_nonnegative', 'retry_count >= 0'
        )
        batch_op.create_check_constraint(
            'chk_payment_attempt_status',
            "status IN ('CREATING', 'CREATED', 'PAID_PENDING_FINALIZE', "
            "'FINALIZED', 'FINALIZE_FAILED', 'FAILED', 'CANCELLED', 'EXPIRED')",
        )
        batch_op.create_index(
            'ix_payment_attempt_snapshot_hash', ['snapshot_hash']
        )

    op.execute(sa.text("UPDATE `order` SET total_amount = 0 WHERE total_amount IS NULL"))
    with op.batch_alter_table('order') as batch_op:
        batch_op.alter_column(
            'total_amount', existing_type=sa.Float(), type_=sa.Numeric(12, 2),
            nullable=False, existing_nullable=True,
        )
        batch_op.add_column(sa.Column('payment_attempt_id', sa.Integer()))
        batch_op.create_foreign_key(
            'fk_order_payment_attempt', 'payment_attempt',
            ['payment_attempt_id'], ['id'],
        )
        batch_op.create_unique_constraint(
            'uq_order_payment_attempt', ['payment_attempt_id']
        )
        batch_op.create_check_constraint(
            'chk_order_total_nonnegative', 'total_amount >= 0'
        )

    with op.batch_alter_table('order_detail') as batch_op:
        batch_op.create_check_constraint(
            'chk_order_detail_quantity_positive', 'quantity > 0'
        )
        batch_op.create_check_constraint(
            'chk_order_detail_price_nonnegative', 'unit_price >= 0'
        )

    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE `order` SET payment_status = 'FAILED' "
        "WHERE payment_status = 'REFUNDED'"
    ))
    if connection.dialect.name == 'mysql':
        op.alter_column(
            'order', 'payment_status',
            existing_type=sa.Enum(
                'UNPAID', 'PAID', 'FAILED', 'REFUNDED', name='paymentstatus'
            ),
            type_=sa.Enum('UNPAID', 'PAID', 'FAILED', name='paymentstatus'),
            existing_nullable=False,
        )


def downgrade():
    connection = op.get_bind()
    if connection.dialect.name == 'mysql':
        op.alter_column(
            'order', 'payment_status',
            existing_type=sa.Enum('UNPAID', 'PAID', 'FAILED', name='paymentstatus'),
            type_=sa.Enum(
                'UNPAID', 'PAID', 'FAILED', 'REFUNDED', name='paymentstatus'
            ),
            existing_nullable=False,
        )
    with op.batch_alter_table('order_detail') as batch_op:
        batch_op.drop_constraint('chk_order_detail_price_nonnegative', type_='check')
        batch_op.drop_constraint('chk_order_detail_quantity_positive', type_='check')
    with op.batch_alter_table('order') as batch_op:
        batch_op.drop_constraint('chk_order_total_nonnegative', type_='check')
        batch_op.drop_constraint('uq_order_payment_attempt', type_='unique')
        batch_op.drop_constraint('fk_order_payment_attempt', type_='foreignkey')
        batch_op.drop_column('payment_attempt_id')
        batch_op.alter_column(
            'total_amount', existing_type=sa.Numeric(12, 2),
            type_=sa.Float(), nullable=True,
        )
    with op.batch_alter_table('payment_attempt') as batch_op:
        batch_op.drop_index('ix_payment_attempt_snapshot_hash')
        batch_op.drop_constraint('chk_payment_attempt_status', type_='check')
        batch_op.drop_constraint('chk_payment_attempt_retry_nonnegative', type_='check')
        batch_op.drop_constraint('chk_payment_attempt_amount_positive', type_='check')
        batch_op.drop_constraint('uq_payment_attempt_snapshot_key', type_='unique')
        batch_op.alter_column(
            'payment_request_id', existing_type=sa.String(255), nullable=False
        )
        batch_op.alter_column(
            'status', existing_type=sa.String(32), type_=sa.String(20),
            existing_nullable=False, server_default='PENDING',
        )
        for column in (
            'updated_at', 'retry_count', 'last_error', 'error_code',
            'checkout_url', 'snapshot_key', 'snapshot_hash',
        ):
            batch_op.drop_column(column)
    with op.batch_alter_table('cart_item') as batch_op:
        batch_op.drop_constraint('chk_cart_item_quantity_positive', type_='check')
    with op.batch_alter_table('dish') as batch_op:
        batch_op.drop_constraint('chk_dish_price_nonnegative', type_='check')
    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.drop_constraint(
            'chk_restaurant_min_order_nonnegative', type_='check'
        )
        batch_op.alter_column(
            'min_order_amount', existing_type=sa.Numeric(12, 2),
            type_=sa.Float(), existing_nullable=True,
        )
    with op.batch_alter_table('cart') as batch_op:
        batch_op.create_unique_constraint(
            'uq_cart_user_restaurant', ['user_id', 'restaurant_id']
        )
        batch_op.drop_constraint('uq_cart_user', type_='unique')
