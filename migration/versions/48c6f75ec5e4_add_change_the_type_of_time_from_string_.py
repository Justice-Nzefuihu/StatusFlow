"""add change the type of time from string to time in status table

Revision ID: 48c6f75ec5e4
Revises: eeb1a6c03778
Create Date: 2025-07-26 03:40:22.354637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48c6f75ec5e4'
down_revision: Union[str, Sequence[str], None] = 'eeb1a6c03778'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('statuses', sa.Column('schedule_time', sa.Time(), nullable=False))
    op.drop_column('statuses', 'time')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('statuses', sa.Column('time', sa.VARCHAR(length=12), autoincrement=False, nullable=False))
    op.drop_column('statuses', 'schedule_time')
    # ### end Alembic commands ###
