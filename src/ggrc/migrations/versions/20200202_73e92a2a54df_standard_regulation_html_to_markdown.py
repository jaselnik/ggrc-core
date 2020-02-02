# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Convert Standard and Regulation attributes and comments to markdown.

Create Date: 2020-02-02 11:14:34.305073
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name


from alembic import op

from ggrc.migrations.markdown import standard
from ggrc.migrations.markdown import regulation


# revision identifiers, used by Alembic.
revision = '73e92a2a54df'
down_revision = '51cadec32665'


converters = [
    standard.StandardConverter(),
    regulation.RegulationConverter(),
]


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()

  for converter in converters:
    converter.convert_to_markdown(connection)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
