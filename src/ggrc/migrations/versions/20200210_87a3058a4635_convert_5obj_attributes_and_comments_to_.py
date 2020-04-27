# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Convert 5OBJ attributes and comments to markdown.

The "5OBJ" term refers to the following objects: Contracts, Policies,
Objectives, Requirements, and Threats.

Create Date: 2020-02-10 12:32:35.052202
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op

from ggrc.migrations.markdown import contract
from ggrc.migrations.markdown import objective
from ggrc.migrations.markdown import policy
from ggrc.migrations.markdown import requirement
from ggrc.migrations.markdown import threat


# revision identifiers, used by Alembic.
revision = "87a3058a4635"
down_revision = "051c48c538d0"


CONVERTERS = (
    contract.ContractConverter(),
    objective.ObjectiveConverter(),
    policy.PolicyConverter(),
    requirement.RequirementConverter(),
    threat.ThreatConverter(),
)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  for converter in CONVERTERS:
    converter.convert_to_markdown(connection)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
