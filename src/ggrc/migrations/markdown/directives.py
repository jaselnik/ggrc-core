# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for directives converter from html to markdown."""

import datetime
from collections import namedtuple

import sqlalchemy as sa
from alembic import op

from ggrc.migrations.markdown import base


class DirectivesConverter(base.BaseConverter):
  """Base class for convert html to markdown for directives objects """

  TABLE_NAME = "directives"

  def update_attributes(self, connection):
    """Updates scope object attributes from html to markdown.

    Args:
      connection: SQLAlchemy connection object.
    Returns:
      List of object ids that were modified.
    """
    objects_data = self._get_objects_data(connection)
    obj_ids = {obj[0] for obj in objects_data}
    self._processing_attributes(objects_data)

    return obj_ids

  def _get_objects_data(self, connection):
    """Gets objects data.

    Args:
      connection: SQLAlchemy connection object.
    Returns:
      List of object records.
    """
    objs_data = connection.execute(
        sa.text("""
                SELECT id, notes, description, test_plan
                FROM {table_name}
                WHERE (notes REGEXP :reg_exp
                  OR description REGEXP :reg_exp
                  OR test_plan REGEXP :reg_exp)
                AND meta_kind = '{kind}'
            """.format(table_name=self.TABLE_NAME, kind=self.OBJECT_TYPE)),
        reg_exp=self.REGEX_HTML
    ).fetchall()

    return objs_data

  def _processing_attributes(self, objects_data):
    """Converts scope objects attributes from html to markdown.

    Args:
      objects_data: List of object data records.
    """
    object_table = sa.sql.table(
        self.TABLE_NAME,
        sa.Column('id', sa.Integer()),
        sa.Column('notes', sa.Text, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('test_plan', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    data_structure = namedtuple('DirectiveData', [
        'c_id', 'notes', 'description', 'test_plan'])
    for obj in objects_data:
      obj = data_structure(*obj)
      op.execute(object_table.update().values(
          notes=self._parse_html(obj.notes),
          description=self._parse_html(obj.description),
          test_plan=self._parse_html(obj.test_plan),
          updated_at=datetime.datetime.utcnow(),
      ).where(object_table.c.id == obj.c_id))
