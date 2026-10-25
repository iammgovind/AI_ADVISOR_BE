"""create bank_accounts and statement_uploads tables

Revision ID: 0002_bank_statement
Revises: 0001_create_users
Create Date: 2025-01-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_bank_statement"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("account_number", sa.String(length=50), nullable=False),
        sa.Column("account_holder", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bank_accounts_user_id"), "bank_accounts", ["user_id"])

    op.create_table(
        "statement_uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("total_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_statement_uploads_user_id"), "statement_uploads", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_statement_uploads_user_id"), table_name="statement_uploads")
    op.drop_table("statement_uploads")
    op.drop_index(op.f("ix_bank_accounts_user_id"), table_name="bank_accounts")
    op.drop_table("bank_accounts")
