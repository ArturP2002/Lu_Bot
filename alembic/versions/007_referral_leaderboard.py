"""Бонус лидерборда и учёт рефералов после верификации."""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_leaderboard_bonus", sa.Integer(), server_default="0", nullable=False))
    op.execute("""
        UPDATE referrals SET counted_at = NULL
        WHERE referred_id IN (SELECT id FROM users WHERE NOT verified OR NOT profile_completed)
    """)
    op.execute("""
        UPDATE users SET referral_count = (
            SELECT count(*) FROM referrals r JOIN users invited ON invited.id = r.referred_id
            WHERE r.referrer_id = users.id AND invited.verified AND invited.profile_completed
        )
    """)


def downgrade() -> None:
    op.drop_column("users", "referral_leaderboard_bonus")
