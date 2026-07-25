"""Слот миграции (награда блогеру считается по транзакциям, без новой колонки).

Revision ID: 003
Revises: 002
Create Date: 2026-07-25

"""
from typing import Sequence, Union

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ранее планировалась колонка profiles_reward_batches — не нужна.
    # Награды за 100 анкет учитываются через SparksTransaction (blogger_profiles_100).
    pass


def downgrade() -> None:
    pass
