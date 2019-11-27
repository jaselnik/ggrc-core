# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=invalid-name

"""
Create review_levels and review_levels_people tables.

It will be used to store assessment review levels data.

Create Date: 2019-11-21 12:56:00.105699
"""

from alembic import op

revision = 'e4c2bb2c4fce'
down_revision = '9c97923e1c92'


def upgrade():
  """Create review_levels and review_levels_people tables."""

  op.execute("""
    CREATE TABLE review_levels (

      id INT(11) NOT NULL AUTO_INCREMENT,
      level_number TINYINT NOT NULL,
      assessment_id INT(11) NOT NULL,
      status ENUM (
        "Not Started",
        "In Review",
        "Reviewed"
      ) DEFAULT "Not Started",
      completed_at DATETIME DEFAULT NULL,
      verified_by INT(11) DEFAULT NULL,
      context_id INT(11),

      PRIMARY KEY (id),

      KEY ix_review_levels_assessment_id (assessment_id),

      CONSTRAINT fk_review_level_assessment FOREIGN KEY (assessment_id)
        REFERENCES assessments (id) ON DELETE CASCADE,
      CONSTRAINT fk_review_levels_contexts FOREIGN KEY (context_id)
        REFERENCES contexts (id) ON DELETE SET NULL
    )
  """)

  op.execute("""
    CREATE TABLE review_levels_people (

      review_level_id INT(11) NOT NULL,
      person_id INT(11) NOT NULL,

      KEY ix_rlp_review_level_id (review_level_id),
      KEY ix_rlp_person_id (person_id),

      CONSTRAINT fk_rlp_review_levels FOREIGN KEY (review_level_id)
        REFERENCES review_levels (id) ON DELETE CASCADE,
      CONSTRAINT fk_rlp_people FOREIGN KEY (person_id)
        REFERENCES people (id) ON DELETE CASCADE
    )
  """)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""

  raise NotImplementedError("Downgrade is not supported")
