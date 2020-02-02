# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
standarts_regulations_migrate_comments_to_externalcomments

Create Date: 2020-02-02 11:48:12.148924
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import logging
from alembic import op

from ggrc.migrations.utils import external_comments


# revision identifiers, used by Alembic.
revision = '2676dfcbc2a1'
down_revision = '73e92a2a54df'


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  conn = op.get_bind()
  models_to_migrate = ("Standard", "Regulation")
  for model_name in models_to_migrate:
    data = external_comments.move_to_external_comments(conn, model_name)
    logger.info("Processing -> %s: %s comments migrated", model_name, data)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
