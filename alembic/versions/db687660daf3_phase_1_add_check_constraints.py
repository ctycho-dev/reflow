"""phase_1_add_check_constraints

Revision ID: db687660daf3
Revises: 52b4edeaf6f8
Create Date: 2026-06-07 12:31:35.991492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db687660daf3'
down_revision: Union[str, Sequence[str], None] = '52b4edeaf6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        'ck_campaigns_enrolled_count_nonneg',
        'campaigns', 'enrolled_count >= 0')
    op.create_check_constraint(
        'ck_campaigns_enrolled_within_cap',
        'campaigns', 'enrolled_count <= max_recipients')
    op.create_check_constraint(
        'ck_campaigns_max_recipients_positive',
        'campaigns', 'max_recipients > 0')
    op.create_check_constraint(
        'ck_campaigns_window_valid',
        'campaigns', 'ends_at > starts_at')
    op.create_check_constraint(
        'ck_enrollments_volume_nonneg',
        'enrollments', 'total_volume >= 0')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_enrollments_volume_nonneg', 'enrollments', type_='check')
    op.drop_constraint('ck_campaigns_window_valid', 'campaigns', type_='check')
    op.drop_constraint('ck_campaigns_max_recipients_positive', 'campaigns', type_='check')
    op.drop_constraint('ck_campaigns_enrolled_within_cap', 'campaigns', type_='check')
    op.drop_constraint('ck_campaigns_enrolled_count_nonneg', 'campaigns', type_='check')
