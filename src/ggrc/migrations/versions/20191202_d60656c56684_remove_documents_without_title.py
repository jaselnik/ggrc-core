# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
remove_documents_without_title

Create Date: 2019-12-02 08:42:54.708477
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from datetime import datetime

from alembic import op

from ggrc.models import all_models
from ggrc.models.mixins import Titled
from ggrc.migrations import utils

# revision identifiers, used by Alembic.
revision = 'd60656c56684'
down_revision = '3141784ef298'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""

  conn = op.get_bind()
  migrator_id = utils.migrator.get_migration_user_id(conn)

  for model in all_models.all_models:
    if issubclass(model, Titled):
      op.execute("""
        UPDATE {model}
        SET title = 'Title was auto-generated on {timestamp}',
        modified_by_id={migrator_id}
        WHERE title IS NULL
        OR title = '' or title REGEXP '{regexp}'
      """.format(model=model.__tablename__,
                 timestamp=datetime.utcnow(),
                 migrator_id=migrator_id,
                 regexp="^[ ]*$"))


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
