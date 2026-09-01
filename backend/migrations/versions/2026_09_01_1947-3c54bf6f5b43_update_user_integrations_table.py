"""Update user integrations table

Revision ID: 3c54bf6f5b43
Revises: e95014be1d14
Create Date: 2026-09-01 19:47:18.306331

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3c54bf6f5b43"
down_revision: Union[str, Sequence[str], None] = "e95014be1d14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "user_integrations_user_id_fkey"
UNIQUE_NAME = "uq_user_integrations_provider"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_integrations",
        sa.Column("provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "user_integrations",
        sa.Column("encrypted_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_integrations",
        sa.Column("status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "user_integrations", sa.Column("scopes", sa.Text(), nullable=True)
    )
    op.add_column(
        "user_integrations",
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "user_integrations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE user_integrations
        SET provider = 'github',
            encrypted_token = github_access_token,
            status = 'connected'
        WHERE github_access_token IS NOT NULL
        """
    )
    op.execute("DELETE FROM user_integrations WHERE github_access_token IS NULL")

    op.alter_column("user_integrations", "provider", nullable=False)
    op.alter_column("user_integrations", "encrypted_token", nullable=False)
    op.alter_column("user_integrations", "status", nullable=False)
    op.drop_column("user_integrations", "github_access_token")

    op.create_index(
        op.f("ix_user_integrations_user_id"),
        "user_integrations",
        ["user_id"],
        unique=False,
    )
    op.create_unique_constraint(
        UNIQUE_NAME,
        "user_integrations",
        ["user_id", "provider"],
    )
    op.drop_constraint(op.f(FK_NAME), "user_integrations", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "user_integrations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f(FK_NAME), "user_integrations", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "user_integrations",
        "users",
        ["user_id"],
        ["id"],
    )
    op.drop_constraint(UNIQUE_NAME, "user_integrations", type_="unique")
    op.drop_index(
        op.f("ix_user_integrations_user_id"), table_name="user_integrations"
    )

    op.add_column(
        "user_integrations",
        sa.Column("github_access_token", sa.VARCHAR(), nullable=True),
    )
    op.execute(
        """
        UPDATE user_integrations
        SET github_access_token = encrypted_token
        WHERE provider = 'github'
        """
    )
    op.execute("DELETE FROM user_integrations WHERE provider <> 'github'")

    op.drop_column("user_integrations", "updated_at")
    op.drop_column("user_integrations", "connected_at")
    op.drop_column("user_integrations", "scopes")
    op.drop_column("user_integrations", "status")
    op.drop_column("user_integrations", "encrypted_token")
    op.drop_column("user_integrations", "provider")
