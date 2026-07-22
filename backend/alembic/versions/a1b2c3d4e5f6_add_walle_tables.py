"""add walle tables

Revision ID: a1b2c3d4e5f6
Revises: fc35ffa0c18b
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "60cd5c95fde1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "walle_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform_account_id", sa.Integer(), sa.ForeignKey("platform_accounts.id"), nullable=True),
        sa.Column("app_cid", sa.String(256), nullable=False),
        sa.Column("customer_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("customer_id", sa.String(128), nullable=True),
        sa.Column("last_msg_time", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("platform_account_id", "app_cid", name="uq_conv_account_cid"),
    )
    op.create_index("ix_walle_conversations_user_id", "walle_conversations", ["user_id"])
    op.create_index("ix_walle_conversations_platform_account_id", "walle_conversations", ["platform_account_id"])
    op.create_index("ix_walle_conversations_app_cid", "walle_conversations", ["app_cid"])

    op.create_table(
        "walle_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform_account_id", sa.Integer(), sa.ForeignKey("platform_accounts.id"), nullable=True),
        sa.Column("app_cid", sa.String(256), nullable=False),
        sa.Column("msg_id", sa.String(256), nullable=False),
        sa.Column("sender_type", sa.String(32), nullable=False, server_default=""),
        sa.Column("sender_id", sa.String(128), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("msg_time", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("platform_account_id", "msg_id", name="uq_msg_account_msgid"),
    )
    op.create_index("ix_walle_messages_user_id", "walle_messages", ["user_id"])
    op.create_index("ix_walle_messages_platform_account_id", "walle_messages", ["platform_account_id"])
    op.create_index("ix_walle_messages_app_cid", "walle_messages", ["app_cid"])
    op.create_index("ix_walle_messages_msg_id", "walle_messages", ["msg_id"])


def downgrade() -> None:
    op.drop_table("walle_messages")
    op.drop_table("walle_conversations")
