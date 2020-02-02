# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
create_external_directives_table

Create Date: 2020-02-02 19:45:12.736279
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '943ddd068e02'
down_revision = '2676dfcbc2a1'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.create_table(
      "external_directives",
      sa.Column("id", sa.Integer, nullable=False, autoincrement=False),
      sa.Column("kind", sa.String(length=255), nullable=False),
      sa.Column("title", sa.String(length=255), nullable=False),
      sa.Column("slug", sa.String(length=255), nullable=False),
      sa.Column("status", sa.String(length=255), nullable=False,
                default="Draft"),
      sa.Column("description", sa.Text, nullable=False),
      sa.Column("notes", sa.Text, nullable=False),
      sa.Column("folder", sa.Text),
      sa.Column("test_plan", sa.Text),
      sa.Column("workflow_state", sa.Enum('Overdue',
                                          'Verified',
                                          'Finished',
                                          'Assigned',
                                          'In Progress')),
      sa.Column("external_slug", sa.String(length=255)),
      sa.Column("external_id", sa.Integer),
      sa.Column("created_at", sa.DateTime, nullable=False),
      sa.Column("created_by_id", sa.Integer),
      sa.Column("updated_at", sa.DateTime, nullable=False),
      sa.Column("modified_by_id", sa.Integer),
      sa.Column("context_id", sa.Integer),
      sa.Column("start_date", sa.Date),
      sa.Column("end_date", sa.Date),

      sa.PrimaryKeyConstraint('id'),
      sa.ForeignKeyConstraint(
          ["context_id"],
          ["contexts.id"],
          name="fk_external_directives_contexts"
      )
  )

  op.create_index('ix_external_directives_updated_at',
                  'external_directives',
                  ['updated_at'],
                  unique=False)

  op.create_unique_constraint(
      "uq_external_slug", "external_directives", ["external_slug"])

  op.create_unique_constraint(
      "uq_slug", "external_directives", ["slug"])

  op.create_unique_constraint(
      "uq_title", "external_directives", ["title"])


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
