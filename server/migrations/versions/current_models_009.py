"""Add ON DELETE CASCADE to component_gcode_association FKs

Revision ID: 20250423_cascade_fks
Revises: 20250416_add_heated_chamber
Create Date: 2025-04-23 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250423_cascade_fks'
down_revision = '20250416_add_heated_chamber'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('component_gcode_association') as batch_op:
        # drop the existing FKs
        batch_op.drop_constraint('component_gcode_association_product_component_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('component_gcode_association_gcode_id_fkey',               type_='foreignkey')
        # re-create them with ON DELETE CASCADE
        batch_op.create_foreign_key(
            'component_gcode_association_product_component_id_fkey',
            'product_components', ['product_component_id'], ['id'],
            ondelete='CASCADE'
        )
        batch_op.create_foreign_key(
            'component_gcode_association_gcode_id_fkey',
            'gcodes', ['gcode_id'], ['gcode_id'],
            ondelete='CASCADE'
        )

def downgrade():
    with op.batch_alter_table('component_gcode_association') as batch_op:
        batch_op.drop_constraint('component_gcode_association_product_component_id_fkey', type_='foreignkey')
        batch_op.drop_constraint('component_gcode_association_gcode_id_fkey',               type_='foreignkey')
        # restore original FKs without ON DELETE
        batch_op.create_foreign_key(
            'component_gcode_association_product_component_id_fkey',
            'product_components', ['product_component_id'], ['id']
        )
        batch_op.create_foreign_key(
            'component_gcode_association_gcode_id_fkey',
            'gcodes', ['gcode_id'], ['gcode_id']
        )
