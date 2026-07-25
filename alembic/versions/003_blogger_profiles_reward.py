"""Награда блогеру за каждые 100 анкет по ссылке.

Revision ID: 003
Revises: 002
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "blogger_profiles",
        sa.Column("profiles_reward_batches", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("blogger_profiles", "profiles_reward_batches")
