# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
migrate_risk_comments_to_external

Create Date: 2019-04-04 13:16:24.987519
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name


from alembic import op

from ggrc.migrations.utils import external_comments


# revision identifiers, used by Alembic.
revision = '482a30c8cb03'
down_revision = '0ab3201db92f'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection, obj_type = op.get_bind(), "Risk"
  external_comments.move_to_external_comments(connection, obj_type)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
