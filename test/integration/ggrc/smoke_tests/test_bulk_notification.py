# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""
  Tests cover part of Smoke test in cases "Bulk verify email notification"

  Unable to change without QA Team approval
"""

import json
import unittest
import mock

from ggrc import models
from integration.ggrc import Api
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc.generator import ObjectGenerator


class TestBulkCompleteNotification(TestCase):
  """Base class for testing notification creation for assignable mixin."""

  def setUp(self):
    super(TestBulkCompleteNotification, self).setUp()
    self.client.get("/login")
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.init_taskqueue()

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_complete_successfully(self):
    """Test assessment complete finished successfully"""
    assessments = []
    with factories.single_commit():
      for _ in range(3):
        assessments.append(factories.AssessmentFactory())
      assessments_ids = [assessment.id for assessment in assessments]
      assessments_titles = [assessment.title for assessment in assessments]

    data = {
        "assessments_ids": assessments_ids,
        "attributes": [],
    }

    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/complete",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertIn("Bulk Assessments update is finished successfully", body)
    self.assertNotIn("Bulk Assessments update is finished partially", body)
    self.assertNotIn("Bulk Assessments update has failed", body)
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_not_completed(self):
    """Test assessment complete finished partially notification"""
    assessments = []
    with factories.single_commit():
      for _ in range(3):
        assessments.append(factories.AssessmentFactory())
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          mandatory=True,
      )
      assessments_ids = [assessment.id for assessment in assessments]
      assessments_titles = [assessment.title for assessment in assessments]

    data = {
        "assessments_ids": assessments_ids,
        "attributes": [],
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/complete",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertNotIn("Bulk Assessments update is finished successfully", body)
    self.assertNotIn("Bulk Assessments update has failed", body)
    self.assertIn("Bulk Assessments update is finished partially", body)
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_attributes_failed(self):
    """Test notification if bulk couldn't fill attributes"""
    assessments = []
    with factories.single_commit():
      for _ in range(3):
        assessment = factories.AssessmentFactory()
        assessments.append(assessment)
        factories.CustomAttributeDefinitionFactory(
            definition_type="assessment",
            definition_id=assessment.id,
            attribute_type="Dropdown",
            title="lca_title",
        )
      assessments_ids = [assmt.id for assmt in assessments]
      assessments_titles = [assmt.title for assmt in assessments]

    bulk_update = [{"assessment_id": assmt.id,
                    "attribute_definition_id": None,
                    "slug": assmt.slug} for assmt in assessments]
    data = {
        "assessments_ids": assessments_ids,
        "attributes": [{
            "attribute_value": "lcavalue",
            "attribute_title": "lca_title",
            "attribute_type": "Dropdown",
            "extra": None,
            "bulk_update": bulk_update
        }],
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/complete",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertNotIn("Bulk Assessments update is finished successfully", body)
    self.assertNotIn("Bulk Assessments update is finished partially", body)
    self.assertIn("Bulk Assessments update has failed", body)
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  def test_verify_successfully(self):
    """Test bulk assessment verify finished successfully"""
    assessments = []
    user = models.Person.query.first()
    with factories.single_commit():
      for _ in range(3):
        assmt = factories.AssessmentFactory(status="In Review")
        assessments.append(assmt)
        assmt.add_person_with_role_name(user, "Verifiers")
      assessments_ids = [assessment.id for assessment in assessments]
      assessments_titles = [assessment.title for assessment in assessments]

    data = {
        "assessments_ids": assessments_ids,
        "attributes": [],
    }

    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/verify",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertIn("Bulk Assessments update is finished successfully", body)
    self.assertNotIn("Bulk Assessments update is finished partially", body)
    self.assertNotIn("Bulk Assessments update has failed", body)
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  def test_not_verified(self):
    """Test bulk assessment verify fail notification"""
    assessments = []
    with factories.single_commit():
      for _ in range(3):
        assessments.append(factories.AssessmentFactory())
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          mandatory=True,
      )
      assessments_ids = [assessment.id for assessment in assessments]
      assessments_titles = [assessment.title for assessment in assessments]
    _, user = self.object_generator.generate_person(user_role="Creator")
    self.api.set_user(user)
    data = {
        "assessments_ids": assessments_ids,
        "attributes": [],
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.api.client.post("/api/bulk_operations/verify",
                                      data=json.dumps(data),
                                      headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertNotIn("Bulk Assessments update is finished successfully", body)
    self.assertIn("Bulk Assessments update has failed", body)
    self.assertNotIn("Bulk Assessments update is finished partially", body)
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  def test_send_notification_for_del_object(self):
    """Test that bulk verify had finished with asmnt del during the operation.
    Testcase here emulates the situation when user open bulk verify in one
    browser tab and delete asmnt in another tab, without refreshing asmnts
    list in the first tab. In that case bulk verify would finish and the right
    notification for deleted asmnt should be send.
    """
    # pylint: disable=invalid-name

    data = {
        "assessments_ids": [123],
        "attributes": [],
    }

    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.api.client.post(
          "/api/bulk_operations/verify",
          data=json.dumps(data),
          headers=self.headers
      )

    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(mail_title, "Bulk update of Assessments is finished")
    self.assertNotIn("Bulk Assessments update is finished successfully", body)
    self.assertNotIn("Bulk Assessments update is finished partially", body)
    self.assertNotIn("Bulk Assessments update has failed", body)
    self.assertIn(
        "Assessments with following ids were deleted "
        "before or during Bulk Update", body)
