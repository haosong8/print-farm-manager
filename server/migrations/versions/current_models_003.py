"""Update printers table with camera configuration fields

Revision ID: 20250325_cam_cfg
Revises: 20250325_sched_prod_comp
Create Date: 2025-03-25 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250325_cam_cfg'
down_revision = '20250325_sched_prod_comp'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('printers', sa.Column('camera_resolution_width', sa.Integer(), nullable=True))
    op.add_column('printers', sa.Column('camera_resolution_height', sa.Integer(), nullable=True))
    op.add_column('printers', sa.Column('camera_scaling_factor', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('printers', 'camera_scaling_factor')
    op.drop_column('printers', 'camera_resolution_height')
    op.drop_column('printers', 'camera_resolution_width')
