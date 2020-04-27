# -*- coding: utf-8 -*-

# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for notifications for models with assignable mixin."""

import collections

import ddt
from freezegun import freeze_time
from mock import patch

from ggrc.models import Assessment, all_models
from ggrc.models import Revision
from ggrc.notifications import common
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc.notifications import TestNotifications


@ddt.ddt
class TestCommentNotification(TestNotifications):
  """Test notification on assessment comments."""

  def setUp(self):
    """Set up test."""
    super(TestCommentNotification, self).setUp()
    self.client.get("/login")
    self._fix_notification_init()
    self.generator = generator.ObjectGenerator()

  @patch("ggrc.notifications.common.send_email")
  def test_notification_entries(self, _):
    """Test setting notification entries for assessment comments.

    Check if the correct notification entries are created when a comment gets
    posted.
    """
    audit = factories.AuditFactory()
    assessment = factories.AssessmentFactory(audit=audit)
    self.generator.generate_comment(
        assessment, "Verifiers", "some comment", send_notification="true")

    notifications = self._get_notifications(notif_type="comment_created").all()
    self.assertEqual(len(notifications), 1,
                     "Missing comment notification entry.")
    notif = notifications[0]
    revisions = Revision.query.filter_by(resource_type='Notification',
                                         resource_id=notif.id).count()
    self.assertEqual(revisions, 1)

    self.client.get("/_notifications/send_daily_digest")

    notifications = self._get_notifications(notif_type="comment_created").all()
    self.assertEqual(len(notifications), 0,
                     "Found a comment notification that was not sent.")

  @patch("ggrc.notifications.common.send_email")
  def test_grouping_comments(self, _):  # pylint: disable=too-many-locals
    """Test that comments are grouped by parent object in daily digest data."""

    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_slug = audit.slug
      asmt_templ = factories.AssessmentTemplateFactory(audit=audit)
      asmt_templ_slug = asmt_templ.slug

    assessments_data = [
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit_slug),
            ("Assignees*", "user@example.com"),
            ("Creators", "user@example.com"),
            ("Template", ""),
            ("Title", "A1"),
        ]),
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit_slug),
            ("Assignees*", "user@example.com"),
            ("Creators", "user@example.com"),
            ("Template", asmt_templ_slug),
            ("Title", "A2"),
        ]),
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", ""),
            ("Audit*", audit_slug),
            ("Assignees*", "user@example.com"),
            ("Creators", "user@example.com"),
            ("Template", asmt_templ_slug),
            ("Title", "A3"),
        ]),
    ]

    self.import_data(*assessments_data)

    asmt_with_no_templ = Assessment.query.filter_by(title="A1").first()
    asmt_with_templ_1 = Assessment.query.filter_by(title="A2").first()
    asmt_with_templ_2 = Assessment.query.filter_by(title="A3").first()

    asmt_ids = (asmt_with_no_templ.id,
                asmt_with_templ_1.id,
                asmt_with_templ_2.id)

    self.generator.generate_comment(
        asmt_with_no_templ, "Verifiers",
        "comment X on asmt " + str(asmt_with_no_templ.id),
        send_notification="true")
    self.generator.generate_comment(
        asmt_with_templ_2, "Verifiers",
        "comment A on asmt " + str(asmt_with_templ_2.id),
        send_notification="true")
    self.generator.generate_comment(
        asmt_with_templ_1, "Verifiers",
        "comment FOO on asmt " + str(asmt_with_templ_1.id),
        send_notification="true")
    self.generator.generate_comment(
        asmt_with_templ_1, "Verifiers",
        "comment BAR on asmt " + str(asmt_with_templ_1.id),
        send_notification="true")
    self.generator.generate_comment(
        asmt_with_no_templ, "Verifiers",
        "comment Y on asmt " + str(asmt_with_no_templ.id),
        send_notification="true")

    _, notif_data = common.get_daily_notifications()

    assignee_notifs = notif_data.get("user@example.com", {})
    common.sort_comments(assignee_notifs)
    comment_notifs = assignee_notifs.get("comment_created", {})
    self.assertEqual(len(comment_notifs), 3)  # for 3 different Assessments

    # for each group of comment notifications, check that it contains comments
    # for that particular Assessment
    for parent_obj_key, comments_info in comment_notifs.iteritems():
      self.assertIn(parent_obj_key.id, asmt_ids)
      for comment in comments_info:
        self.assertEqual(comment["parent_id"], parent_obj_key.id)
        self.assertEqual(comment["parent_type"], "Assessment")
        expected_suffix = "asmt " + str(parent_obj_key.id)
        self.assertTrue(comment["description"].endswith(expected_suffix))

  @ddt.data(
      all_models.Issue,
      all_models.Regulation,
      all_models.Standard,
  )
  @patch("ggrc.notifications.common.send_email")
  def test_models_comments(self, model, _):
    """Test setting notification entries for model comments.

    Check if the correct notification entries are created when a comment gets
    posted.
    """
    recipient_types = model.VALID_RECIPIENTS
    person = all_models.Person.query.first()
    person_email = person.email

    with factories.single_commit():
      obj = factories.get_model_factory(model.__name__)(
          recipients=",".join(recipient_types),
          send_by_default=False,
      )
      for acl in obj._access_control_list:  # pylint: disable=protected-access
        if acl.ac_role.name in recipient_types:
          factories.AccessControlPersonFactory(
              ac_list=acl,
              person=person,
          )
    self.generator.generate_comment(obj, "", "some comment",
                                    send_notification="true")

    notifications, notif_data = common.get_daily_notifications()
    self.assertEqual(len(notifications), 1,
                     "Missing comment notification entry.")

    recip_notifs = notif_data.get(person_email, {})
    comment_notifs = recip_notifs.get("comment_created", {})
    self.assertEqual(len(comment_notifs), 1)

    # Check if correct revisions count is created
    revisions = Revision.query.filter(
        Revision.resource_type == 'Notification',
        Revision.resource_id.in_([n.id for n in notifications])
    )
    self.assertEqual(revisions.count(), 1)

    self.client.get("/_notifications/send_daily_digest")
    notifications = self._get_notifications(notif_type="comment_created").all()
    self.assertEqual(len(notifications), 0,
                     "Found a comment notification that was not sent.")

  def test_old_comments(self):
    """Test if notifications will be sent for mix of old and new comments"""
    cur_user = all_models.Person.query.filter_by(
        email="user@example.com"
    ).first()
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      factories.AccessControlPersonFactory(
          ac_list=assessment.acr_name_acl_map["Assignees"],
          person=cur_user,
      )
    with freeze_time("2015-04-01 17:13:10"):
      self.generator.generate_comment(
          assessment, "", "some comment1", send_notification="true"
      )
    self.generator.generate_comment(
        assessment, "", "some comment2", send_notification="true"
    )
    response = self.client.get("/_notifications/show_pending")
    for comment in ["some comment1", "some comment2"]:
      self.assertIn(
          comment, response.data,
          "Information about comment '{}' absent in report".format(comment)
      )
