"""V8 baseline for existing and new databases.

Revision ID: 20260712_0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "20260712_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent baseline: it creates missing tables without deleting or changing
    # existing data, then Alembic records this revision. Future schema changes
    # should be added as explicit revisions.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Intentionally non-destructive. A production downgrade must never drop all
    # student data automatically.
    pass
