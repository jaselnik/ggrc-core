# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Migrate Contracts and Policies data into separate tables.

Contracts data would be migrated into "contracts" table and Policies data
would be migrated into "policies" table.

Create Date: 2020-02-11 13:52:18.775208
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import logging

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2fa14dd1e8a6"
down_revision = "6d770a51ccd3"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def migrate_directive_data(connection, directive_type, tablename):
  """Migrate data of directives of provided type into provided table.

  Args:
    connection (sqlalchemy.Connection): A database onnection.
    directive_type (str): A type of directvies to migrate.
    tablename (str): A name of a table where to migrate the data.
  """
  sql_q = """
      INSERT INTO {tablename} (
          id,
          modified_by_id,
          context_id,
          start_date,
          end_date,
          created_at,
          updated_at,
          title,
          slug,
          kind,
          status,
          description,
          notes,
          test_plan,
          folder,
          workflow_state
      )
      SELECT
          id,
          modified_by_id,
          context_id,
          start_date,
          end_date,
          created_at,
          updated_at,
          title,
          slug,
          kind,
          status,
          description,
          notes,
          test_plan,
          folder,
          workflow_state
        FROM directives
       WHERE meta_kind = '{meta_kind}'
  """.format(
      tablename=tablename,
      meta_kind=directive_type,
  )

  result = connection.execute(sa.text(sql_q))
  logger.info("%d '%s' was moved to '%s' table",
              result.rowcount, directive_type, tablename)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  migrate_directive_data(connection, "Contract", "contracts")
  migrate_directive_data(connection, "Policy", "policies")


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
