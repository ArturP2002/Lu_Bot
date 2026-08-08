"""Координаты пользователей и тусовок для геопоиска.

Revision ID: 004
Revises: 003
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("geo_source", sa.String(length=16), nullable=True))
    op.create_index(
        "ix_users_geo_lat_lon",
        "users",
        ["latitude", "longitude"],
        postgresql_where=sa.text("latitude IS NOT NULL AND longitude IS NOT NULL"),
    )

    op.add_column("events", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("geo_source", sa.String(length=16), nullable=True))
    op.create_index(
        "ix_events_geo_lat_lon",
        "events",
        ["latitude", "longitude"],
        postgresql_where=sa.text("latitude IS NOT NULL AND longitude IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_events_geo_lat_lon", table_name="events")
    op.drop_column("events", "geo_source")
    op.drop_column("events", "longitude")
    op.drop_column("events", "latitude")

    op.drop_index("ix_users_geo_lat_lon", table_name="users")
    op.drop_column("users", "geo_source")
    op.drop_column("users", "longitude")
    op.drop_column("users", "latitude")
