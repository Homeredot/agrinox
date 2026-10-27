"""weather response cache

Revision ID: 0003_weather_cache
Revises: 0002_rwanda_geography
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_weather_cache"
down_revision = "0002_rwanda_geography"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="open-meteo"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_weather_cache_cache_key", "weather_cache", ["cache_key"], unique=True)
    op.create_index("ix_weather_cache_created_at", "weather_cache", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_weather_cache_created_at", table_name="weather_cache")
    op.drop_index("ix_weather_cache_cache_key", table_name="weather_cache")
    op.drop_table("weather_cache")
