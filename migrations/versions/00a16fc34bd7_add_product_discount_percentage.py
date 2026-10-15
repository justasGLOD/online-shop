"""Add product discount percentage

Revision ID: 00a16fc34bd7
Revises: 882b7b77ff1e
Create Date: 2026-10-15 13:24:51.004044

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00a16fc34bd7'
down_revision = '882b7b77ff1e'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "discount_percent",
                sa.Numeric(precision=5, scale=2),
                server_default="0.00",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "check_product_discount_percent_range",
            "discount_percent >= 0 AND discount_percent <= 100",
        )

def downgrade():
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint(
            "check_product_discount_percent_range",
            type_="check",
        )
        batch_op.drop_column("discount_percent")
