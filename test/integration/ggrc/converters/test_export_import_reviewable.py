# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests export reviewable."""
import collections

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.models import factories


class TestExportReviewable(TestCase):
  """Reviewable export tests."""

  def setUp(self):
    """Set up for Reviewable test cases."""
    super(TestExportReviewable, self).setUp()

    with factories.single_commit():
      person1 = factories.PersonFactory()
      self.person1_email = person1.email
      person2 = factories.PersonFactory()
      self.person2_email = person2.email
      program = factories.ProgramFactory(title="Test program")
      review = factories.ReviewFactory(reviewable=program)

      review.add_person_with_role_name(person1, 'Reviewers')
      review.add_person_with_role_name(person2, 'Reviewers')

    self.client.get("/login")

  def test_simple_export(self):
    """Reviewable should contain Review State and Reviewers
    in exported csv and nothing"""

    data = [
        {
            "object_name": "Program",
            "filters": {
                "expression": {}
            },
            "fields": "all"
        }
    ]
    response = self.export_csv(data)

    self.assertIn("Test program", response.data)
    self.assertIn("Review State", response.data)
    self.assertIn("Unreviewed", response.data)
    self.assertIn("Reviewers", response.data)
    self.assertIn(self.person1_email, response.data)
    self.assertIn(self.person2_email, response.data)

  # pylint: disable=invalid-name
  def test_simple_export_not_reviewable(self):
    """NON Reviewable should NOT contain Review State and Reviewers
    in exported csv"""

    factories.AuditFactory(title="Test audit")
    data = [
        {
            "object_name": "Audit",
            "filters": {
                "expression": {}
            },
            "fields": "all"
        }
    ]
    response = self.export_csv(data)

    self.assertIn("Test audit", response.data)
    self.assertNotIn("Review State", response.data)
    self.assertNotIn("Unreviewed", response.data)
    self.assertNotIn("Reviewers", response.data)


class TestImportReviewable(TestCase):
  """Reviewable import tests."""

  def setUp(self):
    """Set up for Reviewable test cases."""
    super(TestImportReviewable, self).setUp()
    self.client.get("/login")

  def test_import_reviewable(self):
    """Review State and Reviewers should be non imported."""

    program = factories.ProgramFactory()
    self.assertIsNone(program.end_date)
    resp = self.import_data(collections.OrderedDict([
        ("object_type", "Program"),
        ("code", program.slug),
        ("Review State", 'Reviewed'),
        ("Reviewers", "example1@mail.com\nexample2@mail.com")
    ]))

    program = all_models.Program.query.get(program.id)
    self.assertEqual(1, len(resp))
    self.assertEqual(1, resp[0]["updated"])
    self.assertIsNone(program.end_date)
    self.assertEqual(program.review_status, 'Unreviewed')
    self.assertFalse(program.reviewers)
