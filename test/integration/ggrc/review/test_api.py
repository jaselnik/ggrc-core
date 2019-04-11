# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base TestCase for proposal api."""
import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase, generator
from integration.ggrc.models import factories

from integration.ggrc.api_helper import Api
from integration.ggrc.review import build_reviewer_acl


@ddt.ddt
class TestReviewApi(TestCase):
  """Base TestCase class proposal api tests."""

  def setUp(self):
    super(TestReviewApi, self).setUp()
    self.api = Api()
    self.api.client.get("/login")
    self.generator = generator.ObjectGenerator()

  def test_simple_get(self):
    """Test simple get"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          email_message="test email message",
          notification_type="email",
          reviewable=program,
          status=all_models.Review.STATES.UNREVIEWED,
      )
    resp = self.api.get(all_models.Review, review.id)
    self.assert200(resp)
    self.assertIn("review", resp.json)
    resp_review = resp.json["review"]
    self.assertEqual(all_models.Review.STATES.UNREVIEWED,
                     resp_review["status"])
    self.assertEqual(all_models.Review.NotificationTypes.EMAIL_TYPE,
                     resp_review["notification_type"])
    self.assertEqual("test email message",
                     resp_review["email_message"])

  def test_collection_get(self):
    """Test simple collection get"""
    with factories.single_commit():
      review1 = factories.ReviewFactory(
          status=all_models.Review.STATES.UNREVIEWED
      )
      review2 = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED
      )

    resp = self.api.get_collection(all_models.Review,
                                   [review1.id, review2.id])
    self.assert200(resp)
    self.assertIn("reviews_collection", resp.json)
    self.assertIn("reviews", resp.json["reviews_collection"])
    self.assertEquals(2, len(resp.json["reviews_collection"]["reviews"]))

  def test_create_review(self):
    """Create review via API, check that single relationship is created"""
    program = factories.ProgramFactory()
    program_id = program.id
    resp = self.api.post(
        all_models.Review,
        {
            "review": {
                "reviewable": {
                    "type": program.type,
                    "id": program.id,
                },
                "context": None,
                "notification_type": "email",
                "status": all_models.Review.STATES.UNREVIEWED,
                "access_control_list": build_reviewer_acl()
            },
        },
    )
    self.assertEqual(201, resp.status_code)
    review_id = resp.json["review"]["id"]
    review = all_models.Review.query.get(review_id)
    self.assertEqual(all_models.Review.STATES.UNREVIEWED, review.status)
    self.assertEqual(program.type, review.reviewable_type)
    self.assertEqual(program_id, review.reviewable_id)

    control_review_rel_count = all_models.Relationship.query.filter(
        all_models.Relationship.source_id == review.id,
        all_models.Relationship.source_type == review.type,
        all_models.Relationship.destination_id == program_id,
        all_models.Relationship.destination_type == program.type,
    ).union(
        all_models.Relationship.query.filter(
            all_models.Relationship.destination_id == review.id,
            all_models.Relationship.destination_type == review.type,
            all_models.Relationship.source_id == program_id,
            all_models.Relationship.source_type == program.type,
        )
    ).count()
    self.assertEqual(1, control_review_rel_count)

  def test_delete_review(self):
    """Test delete review via API"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      program_id = program.id
      review = factories.ReviewFactory(reviewable=program)
      review_id = review.id
    resp = self.api.delete(review)
    self.assert200(resp)
    review = all_models.Review.query.get(review_id)
    program = all_models.Program.query.get(program_id)

    self.assertIsNone(review)
    self.assertEquals(0, len(program.related_objects(_types=["Review"])))

  def test_last_reviewed(self):
    """last_reviewed_by, last_reviewed_by should be set if reviewed"""
    program = factories.ProgramFactory()
    resp, review = self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context": None,
            "status": all_models.Review.STATES.UNREVIEWED,
            "access_control_list": build_reviewer_acl(),
            "notification_type": all_models.Review.NotificationTypes.EMAIL_TYPE
        },
    )
    review_id = review.id
    resp = self.api.put(
        review,
        {
            "status": all_models.Review.STATES.REVIEWED,
        },
    )
    self.assert200(resp)
    self.assertIsNotNone(resp.json["review"]["last_reviewed_by"])
    self.assertIsNotNone(resp.json["review"]["last_reviewed_at"])

    review = all_models.Review.query.get(review_id)
    self.assertIsNotNone(review.last_reviewed_by)
    self.assertIsNotNone(review.last_reviewed_at)

  def test_reviewable_revisions(self):
    """Check that proper revisions are created"""
    program = factories.ProgramFactory()
    resp, review = self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context": None,
            "status": all_models.Review.STATES.UNREVIEWED,
            "access_control_list": build_reviewer_acl(),
            "notification_type": all_models.Review.NotificationTypes.EMAIL_TYPE
        },
    )
    program_id = program.id
    reviewable = review.reviewable

    program_revisions = all_models.Revision.query.filter_by(
        resource_id=program_id,
        resource_type=program.type
    ).order_by(
        all_models.Revision.id,
    ).all()
    self.assertEquals(2, len(program_revisions))
    self.assertEquals(all_models.Review.STATES.UNREVIEWED,
                      program_revisions[0].content["review_status"])
    self.assertEquals(all_models.Review.STATES.UNREVIEWED,
                      program_revisions[1].content["review_status"])
    resp = self.api.put(
        review,
        {
            "status": all_models.Review.STATES.REVIEWED,
        },
    )
    self.assert200(resp)

    program_revisions = all_models.Revision.query.filter_by(
        resource_id=program_id,
        resource_type=program.type
    ).order_by(
        all_models.Revision.id,
    ).all()
    self.assertEquals(3, len(program_revisions))
    self.assertEquals(all_models.Review.STATES.REVIEWED,
                      program_revisions[2].content["review_status"])

    resp = self.api.put(
        reviewable,
        {
            "description": "some new description"
        }
    )
    self.assert200(resp)

    program_revisions = all_models.Revision.query.filter_by(
        resource_id=program_id,
        resource_type=program.type
    ).order_by(
        all_models.Revision.id,
    ).all()
    self.assertEquals(4, len(program_revisions))
    self.assertEquals(all_models.Review.STATES.UNREVIEWED,
                      program_revisions[3].content["review_status"])
