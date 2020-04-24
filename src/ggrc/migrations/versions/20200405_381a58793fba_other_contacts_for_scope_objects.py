# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Other Contacts for Scope objects

Create Date: 2020-04-05 16:17:14.970555
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import datetime

from alembic import op
import sqlalchemy as sa

from ggrc.migrations import utils
from ggrc.migrations.utils import migrator, acr_propagation
from ggrc.migrations.utils import (
    acr_propagation_constants_scope_other_contacts as propagation_rule
)

# revision identifiers, used by Alembic.
revision = '381a58793fba'
down_revision = '5ac4fe417bf7'

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


def update_scope_recipients(connection, table_name, object_type):
  """Update recipients for existing controls."""
  connection.execute(
      sa.text("""
          UPDATE {table_name}
          SET recipients = concat(recipients, ',Other Contacts')
      """.format(table_name=table_name)))

  objects = connection.execute(
      sa.text("""
          SELECT id FROM {table_name}
      """.format(table_name=table_name))).fetchall()

  object_ids = [obj.id for obj in objects]
  utils.add_to_objects_without_revisions_bulk(
      connection,
      object_ids,
      object_type,
      action="modified",
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  user_id = migrator.get_migration_user_id(connection)

  for object_type, table_name in SCOPE_OBJ_NAME_TBL_MAP.items():
    query = acr_propagation.ACR_TABLE.insert().values(
        name="Other Contacts",
        object_type=object_type,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        modified_by_id=user_id,
        internal=False,
        non_editable=True,
        mandatory=False,
        read=True,
        update=True,
        delete=True,
    )
    result = connection.execute(query)
    utils.add_to_objects_without_revisions(
        connection,
        result.lastrowid,
        "AccessControlRole"
    )
    update_scope_recipients(connection, table_name, object_type)

  acr_propagation.propagate_roles(
      propagation_rule.GGRC_NEW_ROLES_PROPAGATION,
      with_update=True
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
