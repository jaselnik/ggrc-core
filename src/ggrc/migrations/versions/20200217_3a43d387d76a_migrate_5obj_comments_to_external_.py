# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Migrate 5OBJ's comments to external comments table.

Here 5OBJ refer to Contracts, Policies, Objectives, Requirements, and Threats.
All comments related to 5OBJ should be moved from `comments` table into
`external_comments` one.

Create Date: 2020-02-17 11:16:30.913351
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import logging

from alembic import op

from ggrc.migrations.utils import external_comments


# revision identifiers, used by Alembic.
revision = "3a43d387d76a"
down_revision = "87a3058a4635"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


FIVE_OBJ = (
    "Contract",
    "Policy",
    "Objective",
    "Requirement",
    "Threat",
)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  for obj_type in FIVE_OBJ:
    count = external_comments.move_to_external_comments(connection, obj_type)
    logger.info("Processing -> %s: %s comments migrated", obj_type, count)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
