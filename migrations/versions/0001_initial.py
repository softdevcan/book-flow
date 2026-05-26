"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("style_guide", sa.Text(), nullable=True),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("raw", "in_review", "approved", name="chunk_status"),
            nullable=False,
            server_default="raw",
        ),
        sa.Column("editor_notes", sa.Text(), nullable=True),
        sa.Column("scene_context", sa.Text(), nullable=True),
        sa.Column("active_version_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("book_id", "sequence_number", name="uq_chunk_book_seq"),
    )
    op.create_index("ix_chunks_book_id", "chunks", ["book_id"])

    op.create_table(
        "translation_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.Integer(),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("editor_notes", sa.Text(), nullable=True),
        sa.Column("pipeline", sa.String(32), nullable=True),
        sa.Column("stage1_model", sa.String(128), nullable=True),
        sa.Column("stage2_model", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_translation_versions_chunk_id", "translation_versions", ["chunk_id"])

    # Circular FK chunks.active_version_id -> translation_versions.id, added now
    # with use_alter so SQLite ALTER works inside batch operations.
    with op.batch_alter_table("chunks") as batch:
        batch.create_foreign_key(
            "fk_chunk_active_version",
            "translation_versions",
            ["active_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_term", sa.String(255), nullable=False),
        sa.Column("target_term", sa.String(255), nullable=False),
        sa.UniqueConstraint("book_id", "source_term", name="uq_glossary_book_source"),
    )
    op.create_index("ix_glossary_terms_book_id", "glossary_terms", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_glossary_terms_book_id", table_name="glossary_terms")
    op.drop_table("glossary_terms")
    with op.batch_alter_table("chunks") as batch:
        batch.drop_constraint("fk_chunk_active_version", type_="foreignkey")
    op.drop_index("ix_translation_versions_chunk_id", table_name="translation_versions")
    op.drop_table("translation_versions")
    op.drop_index("ix_chunks_book_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("books")
    sa.Enum(name="chunk_status").drop(op.get_bind(), checkfirst=True)
