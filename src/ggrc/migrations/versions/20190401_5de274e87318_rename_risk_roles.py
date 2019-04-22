# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
rename Risk roles

Create Date: 2019-04-01 09:13:29.247890
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import datetime

import sqlalchemy as sa
from sqlalchemy import func
from alembic import op

from ggrc.migrations import utils
from ggrc.migrations.utils import migrator


# revision identifiers, used by Alembic.
revision = '5de274e87318'
down_revision = 'b74156ce58c2'


ROLE_MAPPING = {
    "Primary Contacts": "Risk Owners",
    "Secondary Contacts": "Other Contacts",
}


def update_role_names(connection, migrator_id):
  """Updates role names for Risk model. """
  roles_table = sa.sql.table(
      "access_control_roles",
      sa.Column('object_type', sa.String(length=250), nullable=False),
      sa.Column('name', sa.String(length=250), nullable=False),
      sa.Column('updated_at', sa.DateTime, nullable=False),
      sa.Column('modified_by_id', sa.Integer, nullable=True)
  )

  for old_role_name, new_role_name in ROLE_MAPPING.iteritems():
    connection.execute(
        roles_table.update().where(
            roles_table.c.object_type == "Risk"
        ).where(
            roles_table.c.name == old_role_name
        ).values(name=new_role_name,
                 updated_at=datetime.datetime.utcnow(),
                 modified_by_id=migrator_id)
    )


def update_recipients(connection, migrator_id):
  """Updates recipients field for Risk model. """
  risk_table = sa.sql.table(
      "risks",
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('recipients', sa.String(length=250), nullable=True),
      sa.Column('updated_at', sa.DateTime, nullable=False),
      sa.Column('modified_by_id', sa.Integer, nullable=True)
  )

  # replace all None data with empty string for recipients field
  for old_role_name, new_role_name in ROLE_MAPPING.iteritems():
    connection.execute(risk_table.update().values(
        recipients=func.replace(risk_table.c.recipients,
                                old_role_name, new_role_name),
        updated_at=datetime.datetime.utcnow(),
        modified_by_id=migrator_id
    ))
  risk_entities = connection.execute(
      risk_table.select().where(risk_table.c.recipients != '')
  ).fetchall()

  if risk_entities:
    risk_ids = [entity.id for entity in risk_entities]
    utils.add_to_objects_without_revisions_bulk(connection, risk_ids,
                                                "Risk", action="modified")


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  migrator_id = migrator.get_migration_user_id(connection)
  update_recipients(connection, migrator_id)
  update_role_names(connection, migrator_id)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
