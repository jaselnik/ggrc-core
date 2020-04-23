# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
remove processes from systems table

Create Date: 2020-04-01 11:17:05.144312
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '8b0d2c4e1c4b'
down_revision = '10bcbe93e3b7'


DELETE_PROCESSES = """
    DELETE FROM systems
    WHERE is_biz_process = 1
"""


def delete_processes(connection):
  connection.execute(
      sa.text(DELETE_PROCESSES)
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  delete_processes(connection)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
