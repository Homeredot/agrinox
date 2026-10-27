"""rebrand saved customer-facing content to Agrinox

Revision ID: 0020_rebrand_agrinox
Revises: 0019_profile_identity
"""

revision = "0020_rebrand_agrinox"
down_revision = "0019_profile_identity"
branch_labels = None
depends_on = None


def upgrade():
    # Branding data was normalized when this revision was introduced.
    pass


def downgrade():
    # Stored user-facing records remain branded as Agrinox on downgrade.
    pass
