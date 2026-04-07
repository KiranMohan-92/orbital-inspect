"""Add offline evaluation layer columns to dataset_registry.

Revision ID: 20260407_0005
Revises: 20260405_0004
Create Date: 2026-04-07

Adds record_count and checksum_sha256 to dataset_registry for benchmark
dataset versioning and integrity verification.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260407_0005"
down_revision = "20260405_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataset_registry",
        sa.Column("record_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "dataset_registry",
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dataset_registry", "checksum_sha256")
    op.drop_column("dataset_registry", "record_count")
