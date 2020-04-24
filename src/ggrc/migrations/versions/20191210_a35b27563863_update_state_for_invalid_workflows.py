# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Update state for invalid workflows.

Create Date: 2019-12-10 12:32:50.253923
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name


from alembic import op

from ggrc.migrations import utils


# revision identifiers, used by Alembic.
revision = 'a35b27563863'
down_revision = '381a58793fba'


def get_workflows_without_active_cycles(conn):
  """Get workflows with no active cycles"""

  res = conn.execute("""
    SELECT id
    FROM workflows
    WHERE status='Active'
    AND NOT EXISTS (
    SELECT 1
      FROM cycles
      WHERE cycles.workflow_id = workflows.id)
  """)

  ids = [workflow[0] for workflow in res.fetchall()]
  return ids


def update_workflows():
  """Update workflow status to Inactive to all wf without cycles."""

  res = op.execute("""
      UPDATE workflows
      SET status='Inactive'
      WHERE status='Active'
      AND NOT EXISTS (
      SELECT 1
        FROM cycles
        WHERE cycles.workflow_id = workflows.id)
    """)

  return res


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""

  conn = op.get_bind()
  ids = get_workflows_without_active_cycles(conn)
  utils.add_to_objects_without_revisions_bulk(
      conn, ids, obj_type="Workflow", action="modified"
  )
  update_workflows()


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
