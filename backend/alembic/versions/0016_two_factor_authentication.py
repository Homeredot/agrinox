"""two-factor authentication

Revision ID: 0016_two_factor_authentication
Revises: 0015_email_notifications
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_two_factor_authentication"
down_revision = "0015_email_notifications"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("two_factor_method", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("two_factor_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "two_factor_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("pending_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_two_factor_challenges_user_id", "two_factor_challenges", ["user_id"])
    op.create_index("ix_two_factor_challenges_token_hash", "two_factor_challenges", ["token_hash"], unique=True)
    op.create_index("ix_two_factor_challenges_purpose", "two_factor_challenges", ["purpose"])
    op.create_index("ix_two_factor_challenges_expires_at", "two_factor_challenges", ["expires_at"])


def downgrade():
    op.drop_table("two_factor_challenges")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("two_factor_enabled_at")
        batch.drop_column("totp_secret_encrypted")
        batch.drop_column("two_factor_method")
