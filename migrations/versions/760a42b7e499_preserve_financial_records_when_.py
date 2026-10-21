"""Preserve financial records when deleting users.

Revision ID: 760a42b7e499
Revises: 3adea7290764
"""

from alembic import op
import sqlalchemy as sa


revision = "760a42b7e499"
down_revision = "3adea7290764"
branch_labels = None
depends_on = None


FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
}


def upgrade():
    # Preserve transaction records if their user is deleted.
    with op.batch_alter_table(
        "balance_transactions",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.INTEGER(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "fk_balance_transactions_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_balance_transactions_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Preserve payment records if their user is deleted.
    with op.batch_alter_table(
        "payments",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.INTEGER(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "fk_payments_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_payments_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    # Restoring NOT NULL is impossible if records already have no user.
    connection = op.get_bind()

    for table in ("balance_transactions", "payments"):
        null_count = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL")
        ).scalar_one()

        if null_count:
            raise RuntimeError(
                f"Cannot downgrade: {table} contains {null_count} record(s) "
                "without a user. Reconcile those records before downgrading."
            )

    with op.batch_alter_table(
        "payments",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_payments_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_payments_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.alter_column(
            "user_id",
            existing_type=sa.INTEGER(),
            nullable=False,
        )

    with op.batch_alter_table(
        "balance_transactions",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_balance_transactions_user_id_users",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_balance_transactions_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.alter_column(
            "user_id",
            existing_type=sa.INTEGER(),
            nullable=False,
        )