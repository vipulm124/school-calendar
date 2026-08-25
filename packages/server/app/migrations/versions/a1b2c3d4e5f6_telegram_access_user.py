"""Add telegram_access_user for bot allowlist approvals

Revision ID: a1b2c3d4e5f6
Revises: 48ceb309ac59
Create Date: 2026-08-24 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "48ceb309ac59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_access_user",
        sa.Column("telegram_user_id", sa.VARCHAR(length=32), nullable=False),
        sa.Column("status", sa.VARCHAR(length=20), nullable=False),
        sa.Column("display_name", sa.VARCHAR(length=255), nullable=True),
        sa.Column("username", sa.VARCHAR(length=255), nullable=True),
        sa.Column("chat_id", sa.VARCHAR(length=32), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), nullable=False),
        sa.Column("is_deleted", sa.BOOLEAN(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("created_by", sa.VARCHAR(length=100), nullable=False),
        sa.Column("updated_by", sa.VARCHAR(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
        schema="calendar",
    )


def downgrade() -> None:
    op.drop_table("telegram_access_user", schema="calendar")
