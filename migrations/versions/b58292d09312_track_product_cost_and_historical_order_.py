"""Track product cost and historical order item cost

Revision ID: b58292d09312
Revises: 760a42b7e499
Create Date: 2026-10-26 10:52:27.650833
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision = "b58292d09312"
down_revision = "760a42b7e499"
branch_labels = None
depends_on = None


def upgrade():
    # Store the product's cost at the time an order is placed.
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "cost_at_purchase",
                sa.Numeric(precision=10, scale=2),
                nullable=True,
            )
        )

        batch_op.create_check_constraint(
            "check_order_item_cost_at_purchase_non_negative",
            "cost_at_purchase IS NULL OR cost_at_purchase >= 0",
        )

    # Store the current cost price of a product.
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "cost_price",
                sa.Numeric(precision=10, scale=2),
                nullable=True,
            )
        )

        batch_op.create_check_constraint(
            "check_product_cost_price_non_negative",
            "cost_price IS NULL OR cost_price >= 0",
        )


def downgrade():
    # Remove the product cost constraint and column.
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint(
            "check_product_cost_price_non_negative",
            type_="check",
        )
        batch_op.drop_column("cost_price")

    # Remove the historical order cost constraint and column.
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            "check_order_item_cost_at_purchase_non_negative",
            type_="check",
        )
        batch_op.drop_column("cost_at_purchase")