"""Rename event categories; add likes.seen_by_target_at."""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "likes",
        sa.Column("seen_by_target_at", sa.DateTime(timezone=True), nullable=True),
    )

    # События: переименовать строки категории
    op.execute(
        """
        UPDATE events
        SET category = REPLACE(REPLACE(category, '🎊 Праздники', '☀️ Гулять'), 'Праздники', 'Гулять')
        WHERE category ILIKE '%Праздники%'
        """
    )
    op.execute(
        """
        UPDATE events
        SET category = REPLACE(REPLACE(category, '🍕 Посиделки', '🎉 Все тусовки'), 'Посиделки', 'Все тусовки')
        WHERE category ILIKE '%Посиделки%'
        """
    )

    # Категории: Праздники → Гулять (или деактивировать, если Гулять уже есть)
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM event_categories WHERE name = 'Праздники') THEN
            IF EXISTS (SELECT 1 FROM event_categories WHERE name = 'Гулять') THEN
              UPDATE event_categories SET is_active = false WHERE name = 'Праздники';
            ELSE
              UPDATE event_categories
              SET name = 'Гулять', emoji = '☀️', filter_type = 'type', is_active = true
              WHERE name = 'Праздники';
            END IF;
          END IF;
        END $$;
        """
    )

    # Посиделки → Все тусовки
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM event_categories WHERE name = 'Посиделки') THEN
            IF EXISTS (SELECT 1 FROM event_categories WHERE name = 'Все тусовки') THEN
              UPDATE event_categories SET is_active = false WHERE name = 'Посиделки';
            ELSE
              UPDATE event_categories
              SET name = 'Все тусовки', emoji = '🎉', filter_type = 'all', is_active = true
              WHERE name = 'Посиделки';
            END IF;
          END IF;
        END $$;
        """
    )

    op.execute(
        """
        UPDATE event_categories
        SET is_active = false
        WHERE name IN ('Праздники', 'Посиделки')
        """
    )

    op.execute("UPDATE event_categories SET emoji = '🔥', filter_type = 'time', is_active = true WHERE name = 'Сегодня'")
    op.execute("UPDATE event_categories SET emoji = '📍', filter_type = 'geo', is_active = true WHERE name = 'Рядом'")
    op.execute("UPDATE event_categories SET emoji = '🎮', filter_type = 'type', is_active = true WHERE name = 'Игры'")
    op.execute("UPDATE event_categories SET emoji = '🏠', filter_type = 'type', is_active = true WHERE name = 'На хату'")
    op.execute("UPDATE event_categories SET emoji = '☀️', filter_type = 'type', is_active = true WHERE name = 'Гулять'")
    op.execute("UPDATE event_categories SET emoji = '🎉', filter_type = 'all', is_active = true WHERE name = 'Все тусовки'")

    op.execute(
        """
        INSERT INTO event_categories (name, emoji, filter_type, is_active)
        SELECT 'Гулять', '☀️', 'type', true
        WHERE NOT EXISTS (SELECT 1 FROM event_categories WHERE name = 'Гулять')
        """
    )
    op.execute(
        """
        INSERT INTO event_categories (name, emoji, filter_type, is_active)
        SELECT 'Все тусовки', '🎉', 'all', true
        WHERE NOT EXISTS (SELECT 1 FROM event_categories WHERE name = 'Все тусовки')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE event_categories
        SET name = 'Праздники', emoji = '🎊', filter_type = 'type'
        WHERE name = 'Гулять'
        """
    )
    op.execute(
        """
        UPDATE event_categories
        SET name = 'Посиделки', emoji = '🍕', filter_type = 'type'
        WHERE name = 'Все тусовки'
        """
    )
    op.drop_column("likes", "seen_by_target_at")
