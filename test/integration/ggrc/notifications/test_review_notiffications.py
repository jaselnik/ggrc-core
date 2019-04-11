# -*- coding: utf-8 -*-

# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for notifications for models with Reviewable mixin."""
import collections

import ddt
import freezegun
from mock import mock
from mock import patch

from ggrc.notifications import fast_digest
from ggrc.models import all_models

from integration.ggrc import TestCase, Api
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc.review import build_reviewer_acl

# pylint: disable=invalid-name


@ddt.ddt
class TestReviewNotification(TestCase):
  """Test notification on Review status change."""

  def setUp(self):
    super(TestReviewNotification, self).setUp()
    self.client.get("/login")
    self.generator = generator.ObjectGenerator()
    self.api = Api()

  @ddt.data(
      (all_models.Review.NotificationTypes.EMAIL_TYPE, 1),
      (all_models.Review.NotificationTypes.ISSUE_TRACKER, 0),
  )
  @ddt.unpack
  def test_notification_add_new_review(
      self, notification_type, expected_notifications
  ):
    """After creation of new review notification should be created"""
    program = factories.ProgramFactory()
    resp, _ = self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context": None,
            "notification_type": notification_type,
            "status": all_models.Review.STATES.UNREVIEWED,
            "access_control_list": build_reviewer_acl(),
        },
    )
    self.assertEqual(201, resp.status_code)
    self.assertEqual(
        expected_notifications, len(all_models.Notification.query.all())
    )

  @ddt.data(
      (all_models.Review.NotificationTypes.EMAIL_TYPE, 1),
      (all_models.Review.NotificationTypes.ISSUE_TRACKER, 0),
  )
  @ddt.unpack
  def test_reviewable_attributes(self, notification_type,
                                 expected_notifications):
    """Review change state to Unreviewed

     Notification with notification type STATUS_UNREVIEWED created
    """
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED,
          reviewable=program,
          notification_type=notification_type
      )
    review_id = review.id
    reviewable = review.reviewable

    self.api.modify_object(reviewable, {"title": "new title"})
    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)

    review_notif_types = all_models.Review.NotificationObjectTypes

    notyf_unreviewed_type = all_models.Notification.query.join(
        all_models.NotificationType
    ).filter(
        all_models.NotificationType.name ==
        review_notif_types.STATUS_UNREVIEWED
    ).all()
    self.assertEqual(expected_notifications, len(notyf_unreviewed_type))

  @ddt.data(
      (all_models.Review.NotificationTypes.EMAIL_TYPE, 1),
      (all_models.Review.NotificationTypes.ISSUE_TRACKER, 0),
  )
  @ddt.unpack
  def test_map_snapshotable_notification(self, notification_type,
                                         expected_notifications):
    """Map snapshotable should change review status and add notification"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED,
          reviewable=program,
          notification_type=notification_type
      )
      review_id = review.id

    self.generator.generate_relationship(
        source=program,
        destination=factories.ProductFactory(),
        context=None,
    )

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)
    review_notif_types = all_models.Review.NotificationObjectTypes

    notyf_unreviewed_type = all_models.Notification.query.join(
        all_models.NotificationType
    ).filter(
        all_models.NotificationType.name ==
        review_notif_types.STATUS_UNREVIEWED
    ).all()
    self.assertEqual(expected_notifications, len(notyf_unreviewed_type))

  @ddt.data(
      (all_models.Review.NotificationTypes.EMAIL_TYPE, 1),
      (all_models.Review.NotificationTypes.ISSUE_TRACKER, 0),
  )
  @ddt.unpack
  def test_proposal_apply_notification(self, notification_type,
                                       expected_notifications):
    """Reviewable object changed via proposal -> notification created"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      review = factories.ReviewFactory(
          status=all_models.Review.STATES.REVIEWED,
          reviewable=program,
          notification_type=notification_type
      )
      review_id = review.id

      proposal_content = {
          "fields": {
              "title": "new title"
          },
      }
      proposal = factories.ProposalFactory(
          instance=program, content=proposal_content, agenda="agenda content"
      )
    self.api.modify_object(proposal, {"status": proposal.STATES.APPLIED})

    review = all_models.Review.query.get(review_id)
    self.assertEqual(review.status, all_models.Review.STATES.UNREVIEWED)
    review_notif_types = all_models.Review.NotificationObjectTypes

    notyf_unreviewed_type = all_models.Notification.query.join(
        all_models.NotificationType
    ).filter(
        all_models.NotificationType.name ==
        review_notif_types.STATUS_UNREVIEWED
    ).all()
    self.assertEqual(expected_notifications, len(notyf_unreviewed_type))

  @patch("google.appengine.api.mail.send_mail")
  def test_reviewer_notification_on_create_review(self, _):
    """Reviewer should receive email notification"""
    reviewer = factories.PersonFactory()
    reviewer_role_id = all_models.AccessControlRole.query.filter_by(
        name="Reviewers",
        object_type="Review",
    ).one().id
    program = factories.ProgramFactory()
    email_message = "email email_message"
    self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context":
            None,
            "notification_type":
            all_models.Review.NotificationTypes.EMAIL_TYPE,
            "status":
            all_models.Review.STATES.UNREVIEWED,
            "email_message":
            email_message,
            "access_control_list":
            [{
                "ac_role_id": reviewer_role_id,
                "person": {
                    "id": reviewer.id
                },
            }],
        },
    )
    with mock.patch.object(
        fast_digest.DIGEST_TMPL, "render"
    ) as bodybuilder_mock:
      fast_digest.send_notification()
      template_args = bodybuilder_mock.call_args[1]
      self.assertListEqual([], template_args["proposals"])
      self.assertListEqual([], template_args["review_owners"])
      self.assertEqual(1, len(template_args["review_reviewers"]))
      self.assertEqual(
          program.id, template_args["review_reviewers"][0].reviewable.id
      )
      self.assertEqual(
          email_message, template_args["review_reviewers"][0].email_message
      )

  @patch("google.appengine.api.mail.send_mail")
  def test_self_reviewer_notification_on_create_review(self, _):
    """Auto assigned Reviewer should NOT receive email notification"""
    current_user = all_models.Person.query.filter_by(
        email="user@example.com"
    ).one()
    reviewer_role_id = all_models.AccessControlRole.query.filter_by(
        name="Reviewers",
        object_type="Review",
    ).one().id
    program = factories.ProgramFactory()
    email_message = "email email_message"
    self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context":
            None,
            "notification_type":
            all_models.Review.NotificationTypes.EMAIL_TYPE,
            "status":
            all_models.Review.STATES.REVIEWED,
            "email_message":
            email_message,
            "access_control_list": [
                {
                    "ac_role_id": reviewer_role_id,
                    "person": {
                        "id": current_user.id
                    },
                }
            ],
        },
    )
    with mock.patch.object(
        fast_digest.DIGEST_TMPL, "render"
    ) as bodybuilder_mock:
      fast_digest.send_notification()

      # assert no email sent
      bodybuilder_mock.assert_not_called()

  @patch("google.appengine.api.mail.send_mail")
  def test_reviewer_owner_notification(self, _):
    """Object owners should receive notifications

    System should send notification(s) to object's managers,
    primary contacts, secondary contacts,
    if object is reverted to 'Unreviewed'.
    """
    reviewer = factories.PersonFactory(name='reviewers')
    reviewer_role_id = all_models.AccessControlRole.query.filter_by(
        name="Reviewers",
        object_type="Review",
    ).one().id

    with factories.single_commit():
      program_primary_contact = factories.PersonFactory(name='primary')
      program_secondary_contact = factories.PersonFactory(name='secondary')
      program = factories.ProgramFactory()
      program.add_person_with_role_name(program_primary_contact,
                                        "Primary Contacts")
      program.add_person_with_role_name(program_secondary_contact,
                                        "Secondary Contacts")
    email_message = "email email_message"
    self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context":
            None,
            "notification_type":
            all_models.Review.NotificationTypes.EMAIL_TYPE,
            "status":
            all_models.Review.STATES.REVIEWED,
            "email_message":
            email_message,
            "access_control_list":
            [{
                "ac_role_id": reviewer_role_id,
                "person": {
                    "id": reviewer.id
                },
            }],
        },
    )

    self.api.put(program, {"title": "new title"})

    with mock.patch.object(
        fast_digest.DIGEST_TMPL, "render"
    ) as bodybuilder_mock:
      fast_digest.send_notification()

      # 4 emails to each user
      self.assertEqual(3, bodybuilder_mock.call_count)
      call_count = _call_counter(bodybuilder_mock)
      # 1 email to reviewer -> need to review
      self.assertEqual(1, call_count["review_reviewers"])

      # 1 emails to owners -> object state updated
      self.assertEqual(2, call_count["review_owners"])

  @patch("google.appengine.api.mail.send_mail")
  @freezegun.freeze_time("2019-01-15 12:00:00")
  def test_notification_subject(self, send_mail_mock):
    """Test that emails are sent with proper subject."""
    expected_subject = "GGRC Change requests review digest " \
                       "for 01/15/2019 04:00:00 PST"

    reviewer = factories.PersonFactory()
    reviewer_role_id = all_models.AccessControlRole.query.filter_by(
        name="Reviewers",
        object_type="Review",
    ).one().id

    with factories.single_commit():
      program_manager = factories.PersonFactory()
      program = factories.ProgramFactory()
      program.add_person_with_role_name(program_manager, "Program managers")

    email_message = "email email_message"
    _, review = self.generator.generate_object(
        all_models.Review,
        {
            "reviewable": {
                "type": program.type,
                "id": program.id,
            },
            "context": None,
            "notification_type":
                all_models.Review.NotificationTypes.EMAIL_TYPE,
            "status": all_models.Review.STATES.REVIEWED,
            "email_message": email_message,
            "access_control_list": [{
                "ac_role_id": reviewer_role_id,
                "person": {
                    "id": reviewer.id
                },
            }],
        },
    )

    self.api.modify_object(review.reviewable, {"title": "new title"})
    with mock.patch.object(fast_digest.DIGEST_TMPL, "render"):
      fast_digest.send_notification()
      for call_item in send_mail_mock.call_args_list:
        self.assertEqual(expected_subject, call_item[1]["subject"])


def _call_counter(mocked_obj):
  """Return count of call for given params from mock

  eg if mock called 3 times:
  1) mock(a=[1],b=[],c=[])
  2) mock(a=[1],b=[],c=[])
  3) mock(a=[],b=[],c=[1])

  return {
    'a': 2
    'c': 1
  }
  """
  res = collections.defaultdict(int)
  for call_item in mocked_obj.call_args_list:
    params = call_item[1]
    for param in params:
      if params[param]:
        res[param] += 1
  return res
