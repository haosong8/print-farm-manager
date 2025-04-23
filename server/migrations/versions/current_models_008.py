"""Add heated_chamber column to printers table

Revision ID: 20250416_add_heated_chamber
Revises: 20250325_drop_printer_id
Create Date: 2025-04-16 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20250416_add_heated_chamber'
down_revision = '20250325_drop_printer_id'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))

def upgrade():
    # Add the heated_chamber boolean column, defaulting existing rows to False
    with op.batch_alter_table('printers') as batch_op:
        if not column_exists('printers', 'heated_chamber'):
            batch_op.add_column(
                sa.Column(
                    'heated_chamber',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('false')
                )
            )
            # remove server_default if you don't want it persisted on the schema
            batch_op.alter_column('heated_chamber', server_default=None)

def downgrade():
    # Drop the heated_chamber column if it exists
    with op.batch_alter_table('printers') as batch_op:
        if column_exists('printers', 'heated_chamber'):
            batch_op.drop_column('heated_chamber')
