"""plant lens image screening cases

Revision ID: 0010_plant_lens
Revises: 0009_smart_irrigation
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_plant_lens"
down_revision = "0009_smart_irrigation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plant_lens_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop_id", sa.String(length=80), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("prediction_json", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="pending_expert"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plant_lens_cases_owner_id", "plant_lens_cases", ["owner_id"])
    op.create_index("ix_plant_lens_cases_crop_id", "plant_lens_cases", ["crop_id"])
    op.create_index("ix_plant_lens_cases_review_status", "plant_lens_cases", ["review_status"])
    op.create_index("ix_plant_lens_cases_created_at", "plant_lens_cases", ["created_at"])
    op.create_index("ix_plant_lens_owner_created", "plant_lens_cases", ["owner_id", "created_at"])


def downgrade():
    op.drop_table("plant_lens_cases")
