# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Replace sox_302_enabled with verification_workflow
in assessments and assessment_templates tables.

Create Date: 2019-11-18 12:17:54.598449
"""

# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = '9c97923e1c92'
down_revision = '007ee00ff963'


def upgrade():
  """
    Drop column sox_302_enabled in assessments and
    assessment_templates tables.

    Add column verification_workflow in assessments and
    assessment_templates tables.
  """

  for table_name in ("assessments", "assessment_templates"):
    op.execute("""
      ALTER TABLE {}
      DROP COLUMN sox_302_enabled
    """.format(table_name))

    op.execute("""
      ALTER TABLE {}
      ADD COLUMN verification_workflow ENUM('STANDARD', 'SOX302', 'MLV')
        DEFAULT 'STANDARD' NOT NULL,
      ADD COLUMN review_levels_count TINYINT(1)
    """.format(table_name))


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""

  raise NotImplementedError("Downgrade is not supported")
