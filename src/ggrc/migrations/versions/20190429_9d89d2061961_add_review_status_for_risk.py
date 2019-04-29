# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add review status for Risk

Create Date: 2019-04-29 10:47:20.217525
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = '9d89d2061961'
down_revision = '5de274e87318'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column(
      'risks',
      sa.Column('review_status', sa.String(length=250), nullable=True),
  )
  op.add_column(
      'risks',
      sa.Column('review_status_display_name', sa.String(length=250),
                nullable=True),
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
