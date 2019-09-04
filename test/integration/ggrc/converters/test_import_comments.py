# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests import of comments."""

from collections import OrderedDict

import ddt

from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from ggrc.models import Assessment


@ddt.ddt
class TestCommentsImport(TestCase):
  """Test comments import"""

  @classmethod
  def setUpClass(cls):
    TestCase.clear_data()
    cls.response1 = TestCase._import_file("import_comments.csv")
    cls.response2 = TestCase._import_file(
        "import_comments_without_assignee_roles.csv")

  def setUp(self):
    """Log in before performing queries."""
    self._check_csv_response(self.response1, {})
    self._check_csv_response(self.response2, {})
    self.client.get("/login")

  @ddt.data(("Assessment 1", ["comment", "new_comment1", "new_comment2"]),
            ("Assessment 2", ["some comment"]),
            ("Assessment 3", ["<a href=\"goooge.com\">link</a>"]),
            ("Assessment 4", ["comment1", "comment2", "comment3"]),
            ("Assessment 5", ["one;two", "three;", "four", "hello"]),
            ("Assessment 6", ["a normal comment with {} characters"]))
  @ddt.unpack
  def test_assessment_comments(self, slug, expected_comments):
    """Test assessment comments import"""
    asst = Assessment.query.filter_by(slug=slug).first()
    comments = [comment.description for comment in asst.comments]
    self.assertEqual(comments, expected_comments)
    for comment in asst.comments:
      assignee_roles = comment.assignee_type
      self.assertIn("Assignees", assignee_roles)
      self.assertIn("Creators", assignee_roles)


class TestLCACommentsImport(TestCase):
  """Test import LCA comments"""

  def setUp(self):
    """Set up audit and cad for test cases."""
    super(TestLCACommentsImport, self).setUp()
    self.api = api_helper.Api()
    with factories.single_commit():
      self.audit = factories.AuditFactory()
      self.asmt = factories.AssessmentFactory(
          audit=self.audit,
          context=self.audit.context,
          status="In Progress",
      )
      factories.RelationshipFactory(
          source=self.audit,
          destination=self.asmt,
      )

  def test_custom_comment_import(self):
    """Test success import LCA comment for Dropdown CAD"""
    with factories.single_commit():
      cad = factories.CustomAttributeDefinitionFactory(
          attribute_type="Dropdown",
          definition_type="assessment",
          definition_id=self.asmt.id,
          multi_choice_options="comment_required",
          multi_choice_mandatory="1,2,3",
          mandatory=True,
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=self.asmt,
          attribute_value="comment_required",
      )
    self.assertEqual(self.asmt.status, "In Progress")
    response = self.import_data(OrderedDict([
        ("object_type", "LCA Comment"),
        ("description", "test description"),
        ("custom_attribute_definition", cad.id),
        ("context_id", self.asmt.context_id),
    ]))
    self._check_csv_response(response, {})
    response = self.api.put(self.asmt, {
        "status": "Completed",
    })
    self.assertEqual(response.status_code, 200)
