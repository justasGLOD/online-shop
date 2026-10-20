"""Add email verification and marketing preferences.

Revision ID: 7bcddb90c53e
Revises: 26eccda61263
"""
from alembic import op
import sqlalchemy as sa

revision = "7bcddb90c53e"
down_revision = "26eccda61263"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve access for existing users; marketing stays opt-in.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column(
            "email_verified", sa.Boolean(),
            server_default=sa.text("1"), nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "email_verified_at", sa.DateTime(timezone=True),
            nullable=True,
        ))
        batch_op.add_column(sa.Column(
            "marketing_opt_in", sa.Boolean(),
            server_default=sa.text("0"), nullable=False,
        ))

    # Existing users remain verified; future database inserts default false.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "email_verified",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.text("0"),
        )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("marketing_opt_in")
        batch_op.drop_column("email_verified_at")
        batch_op.drop_column("email_verified")