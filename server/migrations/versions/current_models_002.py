"""Update models for product scheduling

Revision ID: 20250325_sched_prod_comp
Revises: 20250325_add_filament_total
Create Date: 2025-03-25 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250325_sched_prod_comp'
down_revision = '20250325_add_filament_total'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add new column "material" to the gcodes table.
    op.add_column('gcodes', sa.Column('material', sa.String(100), nullable=False, server_default='PLA'))
    op.alter_column('gcodes', 'material', server_default=None)
    
    # 2. Add new column "supported_materials" to the printers table.
    op.add_column('printers', sa.Column('supported_materials', sa.String(), nullable=False, server_default=''))
    op.alter_column('printers', 'supported_materials', server_default=None)
    
    # 3. Add new column "component_name" to the product_components table.
    op.add_column('product_components', sa.Column('component_name', sa.String(255), nullable=False, server_default='component'))
    op.alter_column('product_components', 'component_name', server_default=None)
    
    # 4. Create the many-to-many association table for product components and gcodes.
    op.create_table(
        'component_gcode_association',
        sa.Column('product_component_id', sa.Integer, sa.ForeignKey('product_components.id'), primary_key=True),
        sa.Column('gcode_id', sa.Integer, sa.ForeignKey('gcodes.gcode_id'), primary_key=True)
    )

def downgrade():
    op.drop_table('component_gcode_association')
    op.drop_column('product_components', 'component_name')
    op.drop_column('printers', 'supported_materials')
    op.drop_column('gcodes', 'material')
