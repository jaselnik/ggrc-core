# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Migration for migrate Standards and Regulations data into external_directives.


Create Date: 2020-02-04 07:16:59.501808
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import logging
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = '487d915e647e'
down_revision = '943ddd068e02'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


MODELS_NAMES = ("Standard", "Regulation")


def migrate_data(connection, models_names):
  """
  Migrate data from directives to external_directives table.
  Args:
    models_names: collection with strings of models names
    connection: base MySQL connection

  """
  for model_name in models_names:
    query = sa.text(
        """
            INSERT INTO external_directives
            (
                id,
                kind,
                title,
                slug,
                status,
                description,
                notes,
                folder,
                test_plan,
                created_at,
                updated_at,
                modified_by_id,
                start_date,
                end_date
              )
            SELECT
                id,
                meta_kind,
                title,
                slug,
                status,
                description,
                notes,
                folder,
                test_plan,
                created_at,
                updated_at,
                modified_by_id,
                start_date,
                end_date
            FROM directives
            WHERE meta_kind = '{}'
        """.format(model_name)
    )
    res = connection.execute(query)
    # pylint: disable=logging-not-lazy
    logger.info("%d '%s' was moved to external_directives table" %
                (res.rowcount, model_name))


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  migrate_data(connection, MODELS_NAMES)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
