"""Таблица пропусков анкет в ленте Оценивать.

Revision ID: 002
Revises: 001
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_skips",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_user_id", "to_user_id", name="uq_profile_skip_pair"),
    )
    op.create_index("ix_profile_skips_from_user_id", "profile_skips", ["from_user_id"])
    op.create_index("ix_profile_skips_to_user_id", "profile_skips", ["to_user_id"])


def downgrade() -> None:
    op.drop_index("ix_profile_skips_to_user_id", table_name="profile_skips")
    op.drop_index("ix_profile_skips_from_user_id", table_name="profile_skips")
    op.drop_table("profile_skips")
