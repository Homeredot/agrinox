"""Rwanda agricultural knowledge base and conversations

Revision ID: 0007_knowledge_base
Revises: 0006_soil_quality
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_knowledge_base"
down_revision = "0006_soil_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("title_en", sa.String(240), nullable=False),
        sa.Column("title_rw", sa.String(240), nullable=False),
        sa.Column("content_en", sa.Text(), nullable=False),
        sa.Column("content_rw", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("author", sa.String(180), nullable=False),
        sa.Column("reviewer", sa.String(180), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_articles_slug", "knowledge_articles", ["slug"], unique=True)
    op.create_index("ix_knowledge_articles_category", "knowledge_articles", ["category"])
    op.create_index("ix_knowledge_articles_review_status", "knowledge_articles", ["review_status"])

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(180), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("published_date", sa.String(40), nullable=True),
    )
    op.create_index("ix_knowledge_sources_article_id", "knowledge_sources", ["article_id"])

    op.create_table(
        "knowledge_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("language", sa.String(2), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_conversations_owner_id", "knowledge_conversations", ["owner_id"])
    op.create_index("ix_knowledge_conversations_updated_at", "knowledge_conversations", ["updated_at"])

    op.create_table(
        "knowledge_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("knowledge_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("response_mode", sa.String(40), nullable=True),
        sa.Column("model_name", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_messages_conversation_id", "knowledge_messages", ["conversation_id"])
    op.create_index("ix_knowledge_messages_created_at", "knowledge_messages", ["created_at"])

    op.create_table(
        "knowledge_retrievals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("knowledge_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("knowledge_articles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.String(1000), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("article_title", sa.String(240), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_retrievals_message_id", "knowledge_retrievals", ["message_id"])
    op.create_index("ix_knowledge_retrievals_article_id", "knowledge_retrievals", ["article_id"])


def downgrade() -> None:
    op.drop_table("knowledge_retrievals")
    op.drop_table("knowledge_messages")
    op.drop_table("knowledge_conversations")
    op.drop_table("knowledge_sources")
    op.drop_table("knowledge_articles")
