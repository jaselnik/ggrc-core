# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add table and roles for AccountBalance

Create Date: 2019-03-15 12:36:08.029776
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name
import datetime

import sqlalchemy as sa

from alembic import op

from ggrc.migrations.utils import (
    acr_propagation_constants_account_balance as acr_constants
)
from ggrc.migrations.utils import acr_propagation
from ggrc.migrations import utils
from ggrc.migrations.utils import migrator

revision = '048e54271df8'
down_revision = '0d7a3a0aa3da'

ACCOUNT_BALANCE_ACRS = [
    ('Admin', True, True, True, True),
    ('Assignee', True, True, True, True),
    ('Verifier', True, True, True, True),
    ('Primary Contacts', True, True, True, False),
    ('Secondary Contacts', True, True, True, False),
    ('Product Managers', True, True, True, False),
    ('Technical Leads', True, True, True, False),
    ('Technical / Program Managers', True, True, True, False),
    ('Legal Counsels', True, True, True, False),
    ('System Owners', True, True, True, False),
    ('Compliance Contacts', True, True, True, False),
    ('Line of Defense One Contacts', True, True, True, False),
    ('Vice Presidents', True, True, True, False),
]


def create_account_balances_table():
  """Create account_balances table"""
  op.create_table(
      'account_balances',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('title', sa.String(length=250), nullable=False),
      sa.Column('description', sa.String(length=2000), nullable=True),
      sa.Column('start_date', sa.Date(), nullable=True),
      sa.Column('end_date', sa.Date(), nullable=True),
      sa.Column('slug', sa.String(length=250), nullable=False),
      sa.Column('infrastructure', sa.Boolean(), nullable=True),
      sa.Column('version', sa.String(length=250), nullable=True),
      sa.Column('notes', sa.Text(), nullable=False),
      sa.Column('network_zone_id', sa.Integer(), nullable=True),
      sa.Column('context_id', sa.Integer(), nullable=True),
      sa.Column('status', sa.String(length=250), nullable=False),
      sa.Column(
          'os_state',
          sa.String(length=16),
          nullable=False,
          server_default='Unreviewed',
      ),
      sa.Column('recipients', sa.String(length=250), nullable=True),
      sa.Column('send_by_default', sa.Boolean(), nullable=False, default=True),
      sa.Column('test_plan', sa.Text(), nullable=False),
      sa.Column('folder', sa.Text(), nullable=False),
      sa.Column('created_at', sa.DateTime(), nullable=False),
      sa.Column('updated_at', sa.DateTime(), nullable=False),
      sa.Column('modified_by_id', sa.Integer(), nullable=True),

      sa.ForeignKeyConstraint(
          ['context_id'],
          ['contexts.id'],
          name='fk_account_balances_context_id'
      ),
      sa.ForeignKeyConstraint(
          ['modified_by_id'],
          ['people.id'],
          name='fk_account_balances_modified_by_id'
      ),
      sa.PrimaryKeyConstraint('id')
  )

  op.create_unique_constraint(
      "uq_account_balances_slug",
      "account_balances",
      ["slug"]
  )
  op.create_unique_constraint(
      "uq_account_balances_title",
      "account_balances",
      ["title"]
  )
  op.create_index(
      'ix_account_balances_contexts',
      'account_balances',
      ['context_id'],
      unique=False,
  )
  op.create_index(
      'ix_account_balances_updated_at',
      'account_balances',
      ['updated_at'],
      unique=False,
  )


def create_acrs():
  """Create ACRs for AccountBalance model"""
  connection = op.get_bind()
  migrator_id = migrator.get_migration_user_id(connection)
  for name, read, update, delete, mandatory in ACCOUNT_BALANCE_ACRS:
    query = acr_propagation.ACR_TABLE.insert().values(
        name=name,
        object_type="AccountBalance",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        modified_by_id=migrator_id,
        internal=False,
        non_editable=True,
        mandatory=mandatory,
        # Mandatory roles are default to user
        default_to_current_user=mandatory,
        my_work=1,
        read=read,
        update=update,
        delete=delete,
    )
    result = connection.execute(query)
    utils.add_to_objects_without_revisions(
        connection,
        result.lastrowid,
        "AccessControlRole"
    )


def propagate_acr():
  """Create propagation system ACRs for AccountBalance model"""
  acr_propagation.propagate_roles(
      acr_constants.GGRC_BASIC_PERMISSIONS_PROPAGATION,
      with_update=True
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  create_account_balances_table()
  create_acrs()
  propagate_acr()


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
