# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests import reviewable."""
from collections import OrderedDict

import ddt

from ggrc.converters import errors
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc.review import generate_review_object


@ddt.ddt
class TestImportReviewable(TestCase):
  """Reviewable import tests."""

  def setUp(self):
    """Set up for Reviewable test cases."""
    super(TestImportReviewable, self).setUp()
    self.generator = generator.ObjectGenerator()
    self.client.get("/login")

  def test_simple_import(self):
    """Disallow user to change review state"""
    program = factories.ProgramFactory()

    resp, _ = generate_review_object(program)
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("Review State", "REVIEWED"),
        ]
    )
    response = self.import_data(import_data)
    expected_response = {
        "Program": {
            "row_warnings": {
                errors.READONLY_WILL_BE_IGNORED.format(
                    column_name="Review State", line=3),
            },
        }
    }
    self._check_csv_response(response, expected_response)

    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.UNREVIEWED, program.review_status
    )

  def test_change_attribute(self):
    """Reviewable changed via import
    Review -> UNREVIEWED
    Email Notification added
    """
    program = factories.ProgramFactory(title="Test program")

    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("Title*", "Brand new TiTle"),
            ("Program Managers", "user@example.com"),
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.UNREVIEWED, program.review_status
    )
    notification = all_models.Notification.query.filter_by(
        object_id=review.id, object_type="Review"
    ).one()
    self.assertTrue(notification)

  def test_snapshottable_import(self):
    """Revert state for snapshottable object via import.
    Review -> UNREVIEWED
    Email Notification added
    """
    program = factories.ProgramFactory(
        title="Test program"
    )
    product = factories.ProductFactory()
    product_slug = product.slug

    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("map:Product", product_slug)
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.UNREVIEWED,
        program.review_status
    )
    notification = all_models.Notification.query.filter_by(
        object_id=review.id, object_type="Review"
    ).one()
    self.assertTrue(notification)

  def test_comment_import(self):
    """Don't revert state when comment added.
    Review -> REVIEWED
    """
    program = factories.ProgramFactory()
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    del review
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("comments", "some comments")
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.REVIEWED,
        program.review_status
    )

  def test_reference_url_import(self):
    """Don't revert state when reference url added.
    Review -> REVIEWED
    """
    program = factories.ProgramFactory()
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    del review
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("reference url", "test@test.com")
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.REVIEWED,
        program.review_status
    )

  def test_non_snapshottable_import(self):
    """Reviewable mapped to non snapshotable via import
    Review -> REVIEWED
    """
    program = factories.ProgramFactory()
    issue = factories.IssueFactory()
    issue_slug = issue.slug
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    del review
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("map:Issue", issue_slug),
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.REVIEWED, program.review_status
    )

  def test_without_changes_import(self):
    """Import snapshotable without changes.
    Review -> REVIEWED
    """
    program = factories.ProgramFactory()
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)

    del review
    program_id = program.id
    self.assertEqual(201, resp.status_code)
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.REVIEWED,
        program.review_status
    )

  def test_change_acl_import(self):
    """Change acl via import
    Review -> REVIEWED
    """
    program = factories.ProgramFactory()
    resp, review = generate_review_object(
        program, state=all_models.Review.STATES.REVIEWED)
    del review
    program_id = program.id
    self.assertEqual(201, resp.status_code)

    person = factories.PersonFactory()
    import_data = OrderedDict(
        [
            ("object_type", "Program"),
            ("Code*", program.slug),
            ("Program Managers", person.email)
        ]
    )
    response = self.import_data(import_data)
    self._check_csv_response(response, {})
    program = all_models.Program.query.get(program_id)
    self.assertEqual(
        all_models.Review.STATES.REVIEWED,
        program.review_status
    )

  @ddt.data(
      ("Program", all_models.Program, factories.ProgramFactory),
      ("Regulation", all_models.Regulation, factories.RegulationFactory),
      ("Standard", all_models.Standard, factories.StandardFactory),
  )
  @ddt.unpack
  def test_reviewable_warning_columns(self, object_type, object_class,
                                      object_factory):
    """Test warning while editing review state or reviewers columns"""
    obj = object_factory()
    obj_id = obj.id

    import_data = OrderedDict(
        [
            ("object_type", object_type),
            ("Code*", obj.slug),
            ("Review State", "REVIEWED"),
            ("Reviewers", "test@test.com"),
        ]
    )
    response = self.import_data(import_data)
    expected_response = {
        object_type: {
            "row_warnings": {
                errors.READONLY_WILL_BE_IGNORED.format(
                    column_name="Review State", line=3),
                errors.READONLY_WILL_BE_IGNORED.format(
                    column_name="Reviewers", line=3),
            },
        }
    }
    self._check_csv_response(response, expected_response)
    obj = object_class.query.get(obj_id)
    self.assertEqual(
        all_models.Review.STATES.UNREVIEWED, obj.review_status
    )
    self.assertFalse(obj.reviewers)
