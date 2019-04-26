# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Adding GGRCQ attributes to risks table

Create Date: 2019-04-08 10:16:04.863977
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b74156ce58c2"
down_revision = "482a30c8cb03"


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""

  op.add_column("risks", sa.Column("due_date",
                                   sa.Date,
                                   nullable=True))

  op.add_column("risks", sa.Column("created_by_id",
                                   sa.Integer,
                                   nullable=True))

  op.add_column("risks", sa.Column("last_submitted_at",
                                   sa.DateTime,
                                   nullable=True))

  op.add_column("risks", sa.Column("last_submitted_by_id",
                                   sa.Integer,
                                   nullable=True))

  op.add_column("risks", sa.Column("last_verified_by_id",
                                   sa.Integer,
                                   nullable=True))

  op.add_column("risks", sa.Column("last_verified_at",
                                   sa.DateTime,
                                   nullable=True))


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
