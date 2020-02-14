# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Extend 5OBJ with Q-side fields.

Here 5OBJ refer to Contracts, Policies, Objectives, Requirements, and Threats.
All this objects should be extended with the following Q-side fields:
"external_id", "external_slug", and "created_by_id".

Create Date: 2020-02-13 11:35:00.848875
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = "051c48c538d0"
down_revision = "2fa14dd1e8a6"


FIVE_OBJ = (
    "contracts",
    "policies",
    "objectives",
    "requirements",
    "threats",
)


def extend_with_q_fields(tablename):
  """Extend `tablename` with Q-side fields.

  Add the following new fields on the table:
    - "external_id" (unique);
    - "external_slug" (unique);
    - "created_by_id".
  """
  op.add_column(tablename,
                sa.Column("external_id", sa.Integer, nullable=True))
  op.add_column(tablename,
                sa.Column("external_slug", sa.String(255), nullable=True))
  op.add_column(tablename,
                sa.Column("created_by_id", sa.Integer, nullable=True))

  op.create_unique_constraint(
      "uq_external_id",
      tablename,
      ["external_id"],
  )
  op.create_unique_constraint(
      "uq_external_slug",
      tablename,
      ["external_slug"],
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  for tablename in FIVE_OBJ:
    extend_with_q_fields(tablename)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
