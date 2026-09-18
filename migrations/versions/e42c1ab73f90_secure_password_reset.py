"""secure password reset tokens

Revision ID: e42c1ab73f90
Revises: d18a9f302e45
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa


revision = 'e42c1ab73f90'
down_revision = 'd18a9f302e45'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token_digest', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_digest'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(
        'ix_password_reset_token_token_digest',
        'password_reset_token',
        ['token_digest'],
    )

    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_index('ix_user_reset_token')
        batch_op.drop_column('reset_token_expires')
        batch_op.drop_column('reset_token')


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('reset_token', sa.String(length=100)))
        batch_op.add_column(sa.Column('reset_token_expires', sa.DateTime()))
        batch_op.create_index('ix_user_reset_token', ['reset_token'])

    op.drop_index(
        'ix_password_reset_token_token_digest',
        table_name='password_reset_token',
    )
    op.drop_table('password_reset_token')
