# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add external ID and external slug to Risk

Create Date: 2019-03-22 14:09:54.112523
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = '0ab3201db92f'
down_revision = '25a1b9502690'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column('risks',
                sa.Column('external_id', sa.Integer,
                          autoincrement=False, nullable=True))
  op.add_column("risks",
                sa.Column("external_slug", sa.String(250),
                          nullable=True))
  op.create_unique_constraint("uq_external_id", "risks", ["external_id"])
  op.create_unique_constraint("uq_external_slug", "risks", ["external_slug"])


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
