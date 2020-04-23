# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Remove Primary & Secondary Contacts ACR for Scope Objects.

Create Date: 2020-04-03 13:02:17.785852
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import logging

from alembic import op
import sqlalchemy as sa

from ggrc.migrations import utils


# revision identifiers, used by Alembic.
revision = "5ac4fe417bf7"
down_revision = "8b0d2c4e1c4b"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


SCOPE_OBJ_NAME_TBL_MAP = {
    "AccessGroup": "access_groups",
    "AccountBalance": "account_balances",
    "DataAsset": "data_assets",
    "Facility": "facilities",
    "Market": "markets",
    "OrgGroup": "org_groups",
    "Vendor": "vendors",
    "Product": "products",
    "Project": "projects",
    "System": "systems",
    "Process": "processes",
    "KeyReport": "key_reports",
    "ProductGroup": "product_groups",
    "Metric": "metrics",
    "TechnologyEnvironment": "technology_environments",
}


SELECT_IDS_SQL = """
  SELECT id
    FROM {tablename} ;
"""


DELETE_BY_IDS_SQL = """
  DELETE
    FROM {tablename}
   WHERE id IN :ids ;
"""


SELECT_ACR_SQL = """
  SELECT acr.id
    FROM access_control_roles AS acr
   WHERE acr.object_type IN :object_types
     AND acr.name IN :acr_names ;
"""


SELECT_ACL_SQL = """
  SELECT acl.id
    FROM access_control_list AS acl
   WHERE acl.object_type IN :object_types
     AND acl.ac_role_id IN :acr_ids ;
"""


SELECT_ACP_SQL = """
  SELECT acp.id
    FROM access_control_people AS acp
   WHERE acp.ac_list_id IN :acl_ids ;
"""


def _get_contact_acrs(connection):
  """Get IDs of Primary & Secondary Contacts ACRs of Scope objects.

  Args:
    connection (sqlalchemy.Connection): A database connection.

  Returns:
    List of ACR IDs.
  """
  result = connection.execute(
      sa.text(SELECT_ACR_SQL),
      object_types=SCOPE_OBJ_NAME_TBL_MAP.keys(),
      acr_names=(
          "Primary Contacts",
          "Secondary Contacts",
      ),
  ).fetchall()

  return [item.id for item in result]


def _get_acls_by_acrs(connection, acr_ids):
  """Get ACL IDs of Scope objects by ACRs.

  Args:
    connection (sqlalchemy.Connection): A database connection.
    acr_ids (List[int]): A list of ACR IDs.

  Returns:
    List of ACL IDs.
  """
  if not acr_ids:
    return []

  result = connection.execute(
      sa.text(SELECT_ACL_SQL),
      object_types=SCOPE_OBJ_NAME_TBL_MAP.keys(),
      acr_ids=acr_ids,
  ).fetchall()

  return [item.id for item in result]


def _get_acps_by_acls(connection, acl_ids):
  """Get ACP IDs of Scope objects by ACLs.

  Args:
    connection (sqlalchemy.Connection): A database connection.
    acl_ids (List[int]): A list of ACL IDs.

  Returns:
    List of ACL IDs.
  """
  if not acl_ids:
    return []

  result = connection.execute(
      sa.text(SELECT_ACP_SQL),
      acl_ids=acl_ids,
  ).fetchall()

  return [item.id for item in result]


def _delete_records(connection, sql_query, ids, object_type):
  """Delete ACRs by IDs.

  Args:
    connection (sqlalchemy.Connection): A database connection.
    sql_query (str): A string with plain SQL query.
    ids (List[int]): A list of records IDs.
    object_type (str): A type of the object which records should be deleted.
  """
  if ids:
    connection.execute(
        sa.text(sql_query),
        ids=ids,
    )
    utils.add_to_objects_without_revisions_bulk(
        connection,
        ids,
        object_type,
        "deleted",
    )

    logger.info("%d %s records were deleted.", len(ids), object_type)


def delete_primary_secondary_contacts_acr(connection):
  """Delete Primary & Secondary Contacts ACRs of Scope objects.

  Args:
    connection (sqlalchemy.Connection): A database connection.
  """
  acr_ids = _get_contact_acrs(connection)
  acl_ids = _get_acls_by_acrs(connection, acr_ids)
  acp_ids = _get_acps_by_acls(connection, acl_ids)

  _delete_records(
      connection=connection,
      sql_query=DELETE_BY_IDS_SQL.format(tablename="access_control_people"),
      ids=acp_ids,
      object_type="AccessControlPerson",
  )

  _delete_records(
      connection=connection,
      sql_query=DELETE_BY_IDS_SQL.format(tablename="access_control_list"),
      ids=acl_ids,
      object_type="AccessControlList",
  )

  _delete_records(
      connection=connection,
      sql_query=DELETE_BY_IDS_SQL.format(tablename="access_control_roles"),
      ids=acr_ids,
      object_type="AccessControlRole",
  )


def _get_scope_objects_ids(connection, scope_object_table):
  """Get IDs of Scope objects.

  Args:
    connection (sqlalchemy.Connection): A database connection.
    scope_object_table (str): A name of Scope object table.

  Returns:
    List of Scope objects IDs.
  """
  result = connection.execute(
      sa.text(SELECT_IDS_SQL.format(tablename=scope_object_table))
  ).fetchall()

  return [item.id for item in result]


def update_revisions_of_scope_objects(connection):
  """Add Scope objects to `objects_without_revisions` table."""
  for scope_object, scope_object_table in SCOPE_OBJ_NAME_TBL_MAP.iteritems():
    ids = _get_scope_objects_ids(connection, scope_object_table)
    utils.add_to_objects_without_revisions_bulk(
        connection,
        ids,
        scope_object,
        "modified",
    )

    logger.info(
        "%d %s records were added to objects without revisions.",
        len(ids),
        scope_object,
    )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  delete_primary_secondary_contacts_acr(connection)
  update_revisions_of_scope_objects(connection)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
