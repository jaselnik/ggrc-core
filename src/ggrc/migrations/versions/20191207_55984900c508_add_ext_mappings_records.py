# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Fill `external_mappings` table with mappings between CADs on C and Q.

Create Date: 2019-12-07 10:41:48.084931
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import datetime
import logging

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.

revision = '55984900c508'
down_revision = '18b61f3b870c'


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


DATE_NOW = datetime.datetime.utcnow().replace(microsecond=0).isoformat()


def _get_count_of_cad_ids_for_mapping(connection):
  """Get count of CAD IDs to be inserted into `external_mappings`.

  Args:
    connection (sqlalchemy.Connection): A database connection.

  Returns:
    A number of CAD IDs.
  """

  query = """
      SELECT COUNT(*)
        FROM (SELECT DISTINCT cad.id
                FROM external_custom_attribute_definitions AS ecad
                     JOIN custom_attribute_definitions AS cad
                     ON cad.previous_id = ecad.id
               WHERE ecad.external_id IS NOT NULL) AS count_1
  """

  result = connection.execute(sa.text(query)).fetchone()
  return result[0]


def _fill_external_mappings_tbl(connection):
  """Fill `external_mappings` table with mappings between C and Q CADs.

  Args:
    connection (sqlalchemy.Connection): A database connection.
  """
  query = """
      INSERT INTO external_mappings (
             object_type,
             external_type,
             object_id,
             external_id,
             created_at)
      SELECT DISTINCT
             "CustomAttributeDefinition" AS object_type,
             "CustomAttributeDefinition" AS external_type,
             cad.id,
             ecad.external_id,
             :date_time
        FROM external_custom_attribute_definitions AS ecad
             JOIN custom_attribute_definitions AS cad
             ON cad.previous_id = ecad.id
       WHERE ecad.external_id IS NOT NULL
  """

  connection.execute(sa.text(query),
                     date_time=DATE_NOW)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  ids_count = _get_count_of_cad_ids_for_mapping(connection)

  if ids_count:
    _fill_external_mappings_tbl(connection)

  logger.info("%d mapper records where created.", ids_count)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
