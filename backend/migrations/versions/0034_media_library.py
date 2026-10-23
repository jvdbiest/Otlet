# SPDX-License-Identifier: AGPL-3.0-or-later
"""The médiathèque (ADR-0040): what a person says of an image (name, description, credit,
licence, address of origin), where it comes from, whether it is kept in the bank of images, and
its thumbnail. Where an image is used is read in the articles' versions, through an index of
their blocks.

Revision: 0034
Previous: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("name", "description", "credit", "licence", "source_url", "thumbnail_sha256"):
        op.add_column("media", sa.Column(name, sa.Text(), nullable=True))
    # A default fills the existing rows: no row needs to be read (they are under RLS).
    op.add_column("media", sa.Column("origin", sa.Text(), nullable=False, server_default="editor"))
    op.add_column(
        "media",
        sa.Column("in_bank", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "media_origin", "media", "origin IN ('editor', 'library', 'source', 'generated')"
    )
    op.create_check_constraint(
        "media_thumbnail_sha256",
        "media",
        "thumbnail_sha256 IS NULL OR thumbnail_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "media_lengths",
        "media",
        "coalesce(length(name), 0) <= 200 AND coalesce(length(description), 0) <= 500"
        " AND coalesce(length(credit), 0) <= 300 AND coalesce(length(licence), 0) <= 100"
        " AND coalesce(length(source_url), 0) <= 2000",
    )
    # « Used in »: the versions whose blocks hold an image, found by containment.
    op.execute(
        "CREATE INDEX article_versions_content ON article_versions"
        " USING gin ((document -> 'content') jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX article_versions_content")
    for constraint in ("media_lengths", "media_thumbnail_sha256", "media_origin"):
        op.drop_constraint(constraint, "media")
    for name in (
        "in_bank",
        "origin",
        "thumbnail_sha256",
        "source_url",
        "licence",
        "credit",
        "description",
        "name",
    ):
        op.drop_column("media", name)
