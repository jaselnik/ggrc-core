# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
create processes table

Create Date: 2020-03-31 09:17:47.288187
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '01fb30722cd2'
down_revision = '55984900c508'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.create_table(
      "processes",
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('modified_by_id', sa.Integer, nullable=True),
      sa.Column('created_at', sa.DateTime(), nullable=False),
      sa.Column('updated_at', sa.DateTime(), nullable=False),
      sa.Column('description', sa.Text, nullable=False),
      sa.Column('start_date', sa.Date(), nullable=True),
      sa.Column('end_date', sa.Date(), nullable=True),
      sa.Column('slug', sa.String(length=250), nullable=False),
      sa.Column('title', sa.String(length=250), nullable=False),
      sa.Column('infrastructure', sa.Boolean(), nullable=True),
      sa.Column('version', sa.String(length=250), nullable=True),
      sa.Column('notes', sa.Text(), nullable=False),
      sa.Column('network_zone_id', sa.Integer(), nullable=True),
      sa.Column('context_id', sa.Integer(), nullable=True),
      sa.Column('status', sa.String(length=250), nullable=False,
                default='Draft'),
      sa.Column('recipients', sa.String(length=250), nullable=True),
      sa.Column('send_by_default', sa.Boolean(), nullable=True),
      sa.Column('test_plan', sa.Text(), nullable=False),
      sa.Column('folder', sa.Text(), nullable=False),
      sa.Column('readonly', sa.Boolean(), nullable=False),
      sa.Column('external_id', sa.Integer, nullable=True),
      sa.Column('external_slug', sa.String(255), nullable=True),
      sa.Column('created_by_id', sa.Integer(), nullable=True),
      sa.PrimaryKeyConstraint('id'),
      sa.UniqueConstraint('slug', name='uq_slug_processes'),
      sa.UniqueConstraint('title', name='uq_title_processes'),
      sa.UniqueConstraint('external_id', name='uq_external_id'),
      sa.UniqueConstraint('external_slug', name='uq_external_slug'),
      sa.ForeignKeyConstraint(['context_id'], ['contexts.id'],
                              name='fk_processes_contexts')
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
