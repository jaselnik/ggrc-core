# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests QueryHelper _get_ids logic."""
import datetime

import ddt
import flask

from ggrc.query import builder
from ggrc.models import all_models

from integration import ggrc
from integration.ggrc import api_helper
from integration.ggrc import generator
from integration.ggrc.models import factories


@ddt.ddt
class TestQueryHelper(ggrc.TestCase):
  # pylint: disable=protected-access
  """Basic integration tests QueryHelper _get_ids method."""

  def setUp(self):
    super(TestQueryHelper, self).setUp()
    self.api = api_helper.Api()
    self.gen = generator.ObjectGenerator()

  def _set_user(self, **data):
    """Set flask.g._current_user with the newly created

    Args:
      data: data which contains user_role and data with name and email address
    Returns:
      logged in models.Person object
    """
    user_id = self.gen.generate_person(**data)[1].id
    flask.g._current_user = all_models.Person.query.get(user_id)
    return flask.g._current_user

  def _set_admin_user(self):
    """Login as Administrator user"""
    return self._set_user(
        data={
            "name": "test_admin",
            "email": "admin@example.com",
        },
        user_role="Administrator"
    )

  @ddt.data(
      ("id", "ids"),
      ("slug", "slugs"),
  )
  @ddt.unpack
  def test_clean_filters(self, attr, query_filter):
    """Test QueryHelper._clean_filters method"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmt = factories.AssessmentFactory()
    query = [{
        "object_name": "TestObject",
        "filters": {"expression": {
            "left": {
                "object_name": "Audit",
                "op": {"name": "relevant"},
                query_filter: [str(getattr(audit, attr))]
            },
            "op": {"name": "AND"},
            "right": {
                "object_name": "Assessment",
                "op": {"name": "relevant"},
                query_filter: [str(getattr(asmt, attr))]
            }
        }}
    }]
    left_expression = {
        "ids": [audit.id],
        "object_name": "Audit",
        "op": {"name": "relevant"},
    }
    left_expression[query_filter] = [getattr(audit, attr)]
    right_expression = {
        "ids": [asmt.id],
        "object_name": "Assessment",
        "op": {"name": "relevant"},
    }
    right_expression[query_filter] = [getattr(asmt, attr)]
    self.assertEqual(
        builder.QueryHelper(query).query,
        [{
            "object_name": "TestObject",
            "filters": {
                "expression": {
                    "ids": [],
                    "left": left_expression,
                    "op": {"name": "AND"},
                    "right": right_expression,
                }
            }
        }],
    )

  def test_get_ids_assessment(self):
    """Test _get_ids method for object_name == 'Assessment'"""
    self._set_admin_user()
    with factories.single_commit():
      asmt1_id = factories.AssessmentFactory().id
      factories.AssessmentFactory(verified_date=datetime.datetime.now())
    query = [{
        "object_name": "Assessment",
        "filters": {
            "expression": {
                "left": "verified",
                "op": {"name": "="},
                "right": "false",
            },
        }
    }]
    helper = builder.QueryHelper(query=query)
    self.assertEqual(
        helper._get_ids(query[0]),
        [asmt1_id],
    )

  def test_get_ids_revision(self):
    """Test _get_ids method for object_name == 'Revision'"""
    self._set_admin_user()
    with factories.single_commit():
      control = factories.ControlFactory()
      control_id = control.id
    rev_id = all_models.Revision.query.filter_by(
        resource_type=all_models.Control.__name__
    ).first().id
    expected_ids = [rev_id]
    query = [{
        "object_name": "Revision",
        "type": "ids",
        "limit": [0, 1],
        "filters": {
            "expression": {
                "op": {"name": "AND"},
                "left": {
                    "op": {"name": "="},
                    "left": "resource_type",
                    "right": "Control"
                },
                "right": {
                    "op": {"name": "="},
                    "left": "resource_id",
                    "right": control_id
                }
            },
        },
    }]
    helper = builder.QueryHelper(query=query)
    self.assertEqual(
        helper._get_ids(query[0]),
        expected_ids,
    )

  @ddt.data(
      {
          "left": "title",
          "op": {"name": "="},
          "right": "control_title"
      },
      {
          "left": "child_type",
          "op": {"name": "="},
          "right": "Control"
      },
  )
  def test_get_ids_snapshot(self, expression_data):
    """Test _get_ids method for object_name == 'Snapshot'"""
    self._set_admin_user()
    with factories.single_commit():
      control = factories.ControlFactory(title="control_title")
      program = factories.ProgramFactory()
      audit = factories.AuditFactory(program=program)
      factories.RelationshipFactory(source=control, destination=program)
      last_revision = all_models.Revision.query.filter(
          all_models.Revision.resource_id == control.id,
          all_models.Revision.resource_type == control.type,
      ).order_by(all_models.Revision.id.desc()).first()

      snapshot = factories.SnapshotFactory(
          parent=audit,
          child_id=control.id,
          child_type=control.type,
          revision=last_revision,
      )

    query = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": expression_data,
        },
        "type": "ids",
    }]
    helper = builder.QueryHelper(query=query)
    self.assertEqual(
        helper._get_ids(query[0]),
        [snapshot.id],
    )

  def test_get_ids_comment(self):
    """Test _get_ids method for object_name == 'Comment'"""
    user = self._set_user(
        data={
            "name": "test_creator",
            "email": "creator@example.com",
        },
        user_role="Creator",
    )
    with factories.single_commit():
      evidence = factories.EvidenceFactory()
      comment = factories.CommentFactory(description=factories.random_str())
      factories.RelationshipFactory(source=evidence, destination=comment)
      comment.add_person_with_role_name(user, "Admin")

    query = [{
        "fields": [],
        "filters": {
            "expression": {
                "object_name": "Evidence",
                "op": {
                    "name": "relevant",
                },
                "ids": [evidence.id],
            }
        },
        "object_name": "Comment",
    }]
    helper = builder.QueryHelper(query=query)
    self.assertEqual(
        helper._get_ids(query[0]),
        [comment.id],
    )
