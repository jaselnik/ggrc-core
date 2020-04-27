# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Create tables for Contracts and Policies.

Create Date: 2020-02-11 12:08:07.640495
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = "6d770a51ccd3"
down_revision = "51cadec32665"


def create_table_for_directive_type(tablename):
  """Create a separate table with the given name for a directive type.

  Args:
    tablename (str): A name of a table.
  """
  op.create_table(
      tablename,

      sa.Column("id", sa.Integer, nullable=False, autoincrement=True),
      sa.Column("modified_by_id", sa.Integer, nullable=True),
      sa.Column("context_id", sa.Integer, nullable=True),
      sa.Column("start_date", sa.Date, nullable=True),
      sa.Column("end_date", sa.Date, nullable=True),
      sa.Column("created_at", sa.DateTime, nullable=False),
      sa.Column("updated_at", sa.DateTime, nullable=False),
      sa.Column("title", sa.String(length=255), nullable=False),
      sa.Column("slug", sa.String(length=255), nullable=False),
      sa.Column("kind", sa.String(length=255), nullable=True),
      sa.Column(
          "status",
          sa.String(length=255),
          nullable=False,
          default="Draft",
      ),
      sa.Column("description", sa.Text, nullable=False),
      sa.Column("notes", sa.Text, nullable=False),
      sa.Column("test_plan", sa.Text, nullable=False),
      sa.Column("folder", sa.Text, nullable=False),
      sa.Column(
          "workflow_state",
          sa.Enum(
              "Overdue",
              "Verified",
              "Finished",
              "Assigned",
              "In Progress",
          ),
          nullable=True,
      ),

      sa.PrimaryKeyConstraint("id"),
      sa.ForeignKeyConstraint(
          ["context_id"],
          ["contexts.id"],
          name="fk_{}_contexts".format(tablename),
      ),
      sa.UniqueConstraint(
          "slug",
          name="uq_{}".format(tablename),
      ),
      sa.UniqueConstraint(
          "title",
          name="uq_t_{}".format(tablename),
      ),
  )

  op.create_index(
      "ix_{}_updated_at".format(tablename),
      tablename,
      ["updated_at"],
      unique=False,
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  create_table_for_directive_type("contracts")
  create_table_for_directive_type("policies")


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
