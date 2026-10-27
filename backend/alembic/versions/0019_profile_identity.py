"""profile identity and avatar

Revision ID: 0019_profile_identity
Revises: 0018_in_app_notifications
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_profile_identity"
down_revision = "0018_in_app_notifications"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("location", sa.String(length=160), nullable=True))
        batch.add_column(sa.Column("bio", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("avatar_kind", sa.String(length=12), nullable=False, server_default="vector"))
        batch.add_column(sa.Column("avatar_key", sa.String(length=30), nullable=False, server_default="farmer"))
        batch.add_column(sa.Column("avatar_color", sa.String(length=20), nullable=False, server_default="forest"))
        batch.add_column(sa.Column("profile_image_path", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("profile_image_path")
        batch.drop_column("avatar_color")
        batch.drop_column("avatar_key")
        batch.drop_column("avatar_kind")
        batch.drop_column("bio")
        batch.drop_column("location")
        batch.drop_column("phone")
