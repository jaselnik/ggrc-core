# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Change 'risk_type' to optional

Create Date: 2019-05-11 11:25:04.552633
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = 'b194e332fa65'
down_revision = '9d89d2061961'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  script = """ALTER TABLE risks MODIFY risk_type text"""
  op.execute(script)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
