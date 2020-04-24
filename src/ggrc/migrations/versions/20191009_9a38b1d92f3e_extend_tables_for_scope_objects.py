# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
extend_tables_for_scope_objects

Create Date: 2019-10-09 11:52:33.525522
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '9a38b1d92f3e'
down_revision = 'ddc897e22d54'

scope_tables_names = {
    'access_groups',
    'account_balances',
    'data_assets',
    'facilities',
    'markets',
    'org_groups',
    'vendors',
    'products',
    'projects',
    'systems',
    'key_reports',
    'product_groups',
    'metrics',
    'technology_environments',
}


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  for name in scope_tables_names:
    op.add_column(name, sa.Column('external_id', sa.Integer,
                                  autoincrement=False, nullable=True))
    op.add_column(name, sa.Column('external_slug', sa.String(255),
                                  autoincrement=False, nullable=True))
    op.add_column(name, sa.Column('created_by_id', sa.Integer, nullable=True))
    op.create_unique_constraint('uq_external_id', name, ['external_id'])
    op.create_unique_constraint('uq_external_slug', name, ['external_slug'])


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
