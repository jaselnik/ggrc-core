# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add custom_attribute_definition_id and revision_id to Evidence

Create Date: 2020-05-11 09:16:47.824314
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = 'b4a7f3b0c400'
down_revision = '3a43d387d76a'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""

  op.execute("""
      ALTER TABLE evidence
      ADD custom_attribute_definition_id int(11) NULL,
      ADD revision_id int(11) NULL
  """)

  op.execute("""
      ALTER TABLE evidence
      ADD CONSTRAINT fk_cad FOREIGN KEY (custom_attribute_definition_id) 
          REFERENCES custom_attribute_definitions (id)
  """)

  op.execute("""
      ALTER TABLE evidence
      ADD CONSTRAINT fk_revision FOREIGN KEY (revision_id) 
          REFERENCES revisions (id)
  """)


def downgrade():
    """Downgrade database schema and/or data back to the previous revision."""
    raise NotImplementedError("Downgrade is not supported")
