# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add notes column to evidence

Create Date: 2019-09-24 08:33:07.944851
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = '394f80f98f02'
down_revision = 'ac75e70c9081'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.execute("""
      ALTER TABLE evidence
        ADD notes TEXT;
  """)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
