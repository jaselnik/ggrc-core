# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
migrate risks to markdown

Create Date: 2019-04-16 12:27:19.798851
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from collections import namedtuple
import datetime

import sqlalchemy as sa

from alembic import op

from ggrc.migrations import utils
from ggrc.migrations.utils import html_markdown_parser

# revision identifiers, used by Alembic.
revision = '62d98cc2f69a'
down_revision = '2dd5e1292b9c'


REGEX_HTML = r"(<[a-zA-Z]+>)+|(<\/[a-zA-Z]+>)+"


def parse_html(value):
  """Parse html to markdown."""
  parser = html_markdown_parser.HTML2MarkdownParser()
  parser.feed(value)
  return parser.get_data()


def update_comments(connection):
  """Parse comments from html to markdown."""
  comments_data = connection.execute(
      sa.text("""
            SELECT c.id, c.description
            FROM risks as c
            JOIN relationships as r
            ON r.source_type = "Comment" and r.source_id = c.id
              and r.destination_type = "Risk"
            WHERE c.description REGEXP :reg_exp
            UNION
            SELECT c.id, c.description
            FROM comments as c
            JOIN relationships as r
            ON r.destination_type = "Comment" and r.destination_id = c.id
              and r.source_type = "Risk"
            where c.description REGEXP :reg_exp
        """),
      reg_exp=REGEX_HTML
  ).fetchall()
  comments_ids = [c_id for c_id, _ in comments_data]
  comments_table = sa.sql.table(
      'comments',
      sa.Column('id', sa.Integer()),
      sa.Column('description', sa.Text, nullable=True),
      sa.Column('updated_at', sa.DateTime, nullable=False),
  )
  for comment_id, description in comments_data:
    op.execute(comments_table.update().values(
        description=parse_html(description),
        updated_at=datetime.datetime.utcnow(),
    ).where(comments_table.c.id == comment_id))
  utils.add_to_objects_without_revisions_bulk(
      connection, comments_ids, "Comment", "modified",
  )


def update_risk_cavs(connection):
  """Parse cavs from html to markdown."""
  cavs_data = connection.execute(
      sa.text("""
            select cav.id, cav.attribute_value, cav.attributable_id
            from custom_attribute_values cav
            join custom_attribute_definitions cad
              on cad.id = cav.custom_attribute_id
            where cad.definition_type = "risk"
              and attribute_value REGEXP :reg_exp
        """),
      reg_exp=REGEX_HTML
  ).fetchall()
  risks_ids = {data[2] for data in cavs_data}
  cavs_ids = {data[0] for data in cavs_data}
  cavs_table = sa.sql.table(
      'custom_attribute_values',
      sa.Column('id', sa.Integer()),
      sa.Column('attribute_value', sa.Text, nullable=False),
      sa.Column('updated_at', sa.DateTime, nullable=False),
  )
  for cav_id, attribute_value, _ in cavs_data:
    op.execute(cavs_table.update().values(
        attribute_value=parse_html(attribute_value),
        updated_at=datetime.datetime.utcnow(),
    ).where(cavs_table.c.id == cav_id))
  utils.add_to_objects_without_revisions_bulk(
      connection, cavs_ids, "CustomAttributeValue", "modified",
  )
  return risks_ids


def update_risk_attr(connection):
  """Parse Risk attributes from html to markdown."""
  risks_data = connection.execute(
      sa.text("""
            SELECT id, title, description, test_plan, notes,
                   risk_type, threat_source, threat_event, vulnerability
            FROM risks
            WHERE title REGEXP :reg_exp
            OR description REGEXP :reg_exp
            OR test_plan REGEXP :reg_exp
            OR notes REGEXP :reg_exp
            OR risk_type REGEXP :reg_exp
            OR threat_source REGEXP :reg_exp
            OR threat_event REGEXP :reg_exp
            OR vulnerability REGEXP :reg_exp
        """),
      reg_exp=REGEX_HTML
  ).fetchall()
  risks_ids = {data[0] for data in risks_data}

  risks_table = sa.sql.table(
      'risks',
      sa.Column('id', sa.Integer()),
      sa.Column('title', sa.String(250), nullable=False),
      sa.Column('description', sa.Text, nullable=False),
      sa.Column('test_plan', sa.Text, nullable=False),
      sa.Column('notes', sa.Text, nullable=False),
      sa.Column('risk_type', sa.Text, nullable=False),
      sa.Column('threat_source', sa.Text, nullable=False),
      sa.Column('threat_event', sa.Text, nullable=False),
      sa.Column('vulnerability', sa.Text, nullable=False),
      sa.Column('updated_at', sa.DateTime, nullable=False),
  )
  RiskData = namedtuple('RiskData', [
      'c_id', 'title', 'description', 'test_plan', 'notes',
      'risk_type', 'threat_source', 'threat_event', 'vulnerability'
  ])
  for item in risks_data:
    risk_item = RiskData(*item)
    op.execute(risks_table.update().values(
        title=parse_html(risk_item.title),
        description=parse_html(risk_item.description),
        test_plan=parse_html(risk_item.test_plan),
        notes=parse_html(risk_item.notes),
        risk_type=parse_html(risk_item.risk_type),
        threat_source=parse_html(risk_item.threat_source),
        threat_event=parse_html(risk_item.threat_event),
        vulnerability=parse_html(risk_item.vulnerability),
        updated_at=datetime.datetime.utcnow(),
    ).where(risks_table.c.id == risk_item.c_id))
  return risks_ids


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  update_comments(connection)
  risks_ids_cavs = update_risk_cavs(connection)
  risks_ids_attr = update_risk_attr(connection)
  risks_ids = risks_ids_attr.union(risks_ids_cavs)
  if risks_ids:
    utils.add_to_objects_without_revisions_bulk(
        connection, risks_ids, "Risk", "modified",
    )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
