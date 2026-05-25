"""add source_language and target_language to books

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows as EN->TR (current behavior). New
    # rows must always set both fields explicitly via the API.
    with op.batch_alter_table("books") as batch:
        batch.add_column(
            sa.Column("source_language", sa.String(8), nullable=False, server_default="en")
        )
        batch.add_column(
            sa.Column("target_language", sa.String(8), nullable=False, server_default="tr")
        )


def downgrade() -> None:
    with op.batch_alter_table("books") as batch:
        batch.drop_column("target_language")
        batch.drop_column("source_language")
