# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
migrate data from system to process

Create Date: 2020-03-31 13:11:41.573099
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '10bcbe93e3b7'
down_revision = '01fb30722cd2'


GET_PROCESSES_QUERY = """
    SELECT `id`, `modified_by_id`, `created_at`, `updated_at`,
           `description`, `start_date`, `end_date`, `slug`, `title`,
           `infrastructure`, `version`, `notes`, `network_zone_id`,
           `context_id`, `status`, `recipients`, `send_by_default`,
           `test_plan`, `folder`, `readonly`, `external_id`,
           `external_slug`, `created_by_id`
    FROM systems WHERE `is_biz_process` = 1
"""

INSERT_PROCESS_QUERY = """
    INSERT INTO `processes` (`id`, `modified_by_id`, `created_at`,
                             `updated_at`, `description`, `start_date`,
                             `end_date`, `slug`, `title`, `infrastructure`,
                             `version`, `notes`, `network_zone_id`,
                             `context_id`, `status`, `recipients`,
                             `send_by_default`, `test_plan`, `folder`,
                             `readonly`, `external_id`, `external_slug`,
                             `created_by_id`
    ) VALUES (:id, :modified_by_id, :created_at,
              :updated_at, :description, :start_date,
              :end_date, :slug, :title, :infrastructure,
              :version, :notes, :network_zone_id,
              :context_id, :status, :recipients,
              :send_by_default, :test_plan, :folder,
              :readonly, :external_id,
              :external_slug, :created_by_id)
"""


def get_processes(connection):
  """Gets processes

  Args:
    connection: Instance of database connection.
  Returns:
    List of processes.
  """
  processes = connection.execute(
      sa.text(GET_PROCESSES_QUERY)
  ).fetchall()

  return processes


def add_processes(connection, processes):
  """Adds processes to process table.

  Args:
    connection: Instance of database connection.
    processes: List of processes.
  """
  for process in processes:
    connection.execute(
        sa.text(INSERT_PROCESS_QUERY),
        id=process.id,
        modified_by_id=process.modified_by_id,
        created_at=process.created_at,
        updated_at=process.updated_at,
        description=process.description,
        start_date=process.start_date,
        end_date=process.end_date,
        slug=process.slug,
        title=process.title,
        infrastructure=process.infrastructure,
        version=process.version,
        notes=process.notes,
        network_zone_id=process.network_zone_id,
        context_id=process.context_id,
        status=process.status,
        recipients=process.recipients,
        send_by_default=process.send_by_default,
        test_plan=process.test_plan,
        folder=process.folder,
        readonly=process.readonly,
        external_id=process.external_id,
        external_slug=process.external_slug,
        created_by_id=process.created_by_id
    )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  processes = get_processes(connection)
  add_processes(connection, processes)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
