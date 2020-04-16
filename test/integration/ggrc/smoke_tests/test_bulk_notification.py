# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""
  Tests cover part of Smoke test in cases "Bulk verify email notification"

  Unable to change without QA Team approval
"""

import json
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

  def test_save_successfully(self):
    """Test assessment save finished successfully"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(status="Not Started")
      cad_id = factories.CustomAttributeDefinitionFactory(
          definition_id=asmt.id,
          title="test_text_lca",
          definition_type="assessment",
          attribute_type="Text"
      ).id

    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": "test value",
                "title": "test_text_lca",
                "type": "Text",
                "definition_id": asmt.id,
                "id": cad_id,
                "extra": {},
            }]
        }]
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/cavs/save",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Saving certifications in bulk is finished",
    )
    self.assertIn(
        "Answers for the following certifications are saved successfully:",
        body,
    )
    self.assertNotIn(
        "Answers for the following certifications are partially saved:",
        body,
    )
    self.assertNotIn(
        "Failed to save answers for the following certifications:",
        body,
    )

  def test_saved_partially(self):
    """Test assessment save finished partially"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(status="Not Started")
      cad_id = factories.CustomAttributeDefinitionFactory(
          definition_id=asmt.id,
          title="dropdown_lca",
          definition_type="assessment",
          attribute_type="Dropdown",
          multi_choice_options="one,two",
      ).id
      data = {
          "assessments_ids": [],
          "attributes": [{
              "assessment": {"id": asmt.id, "slug": asmt.slug},
              "values": [{
                  "value": "three",
                  "title": "dropdown_lca",
                  "type": "Dropdown",
                  "definition_id": asmt.id,
                  "id": cad_id,
                  "extra": {},
              }]
          }]
      }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post(
          "/api/bulk_operations/cavs/save",
          data=json.dumps(data),
          headers=self.headers
      )
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Saving certifications in bulk is finished",
    )
    self.assertNotIn(
        "Answers for the following certifications are saved successfully:",
        body,
    )
    self.assertIn(
        "Answers for the following certifications are partially saved:",
        body,
    )
    self.assertNotIn(
        "Failed to save answers for the following certifications:",
        body,
    )

  def test_saved_failed(self):
    """Test assessment save failed"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(status="Not Started")
      cad_dropdown_id = factories.CustomAttributeDefinitionFactory(
          definition_id=asmt.id,
          title="dropdown_lca",
          definition_type="assessment",
          attribute_type="Dropdown",
      ).id

    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": "one",
                "title": "dropdown_lca",
                "type": "Dropdown",
                "definition_id": asmt.id,
                "id": cad_dropdown_id,
                "extra": {},
            }]
        }]
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post(
          "/api/bulk_operations/cavs/save",
          data=json.dumps(data),
          headers=self.headers
      )
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Saving certifications in bulk is finished",
    )
    self.assertNotIn(
        "Answers for the following certifications are saved successfully:",
        body,
    )
    self.assertNotIn(
        "Answers for the following certifications are partially saved:",
        body,
    )
    self.assertIn(
        "Failed to save answers for the following certifications:",
        body,
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
    self.assertEqual(
        mail_title,
        "Completing certifications in bulk is finished",
    )
    self.assertIn(
        "The following certifications are completed successfully:",
        body,
    )
    self.assertNotIn(
        "Failed to complete the following certifications:",
        body,
    )
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  def test_not_completed(self):
    """Test assessment complete failed notification, missed mandatory lca"""
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
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [],
        } for asmt in assessments],
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/complete",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Completing certifications in bulk is finished",
    )
    self.assertNotIn(
        "The following certifications are completed successfully:",
        body,
    )
    self.assertIn(
        "Failed to complete the following certifications:",
        body,
    )
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

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

    data = {
        "assessments_ids": assessments_ids,
        "attributes": [{
            "assessment": {"id": assmt.id, "slug": assmt.slug},
            "values": [{
                "value": "1",
                "title": "lca_title",
                "type": "Dropdown",
                "definition_id": assmt.id,
                "id": None,
                "extra": None,
            }]
        } for assmt in assessments]
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post("/api/bulk_operations/complete",
                                  data=json.dumps(data),
                                  headers=self.headers)
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Completing certifications in bulk is finished",
    )
    self.assertNotIn(
        "The following certifications are completed successfully:",
        body,
    )
    self.assertIn(
        "Failed to complete the following certifications:",
        body,
    )
    for asmt_title in assessments_titles:
      self.assertIn(asmt_title, body)

  def test_complete_failed(self):
    """Test assessment failed to update and assessment failed to complete"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory()
      asmt2 = factories.AssessmentFactory()
      assessments_titles = [asmt1.title, asmt2.title]
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Dropdown",
          title="test dropdown lca",
      )
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
          title="test text lca",
          mandatory=True,
      )
    data = {
        "assessments_ids": [asmt1.id, asmt2.id],
        "attributes": [{
            "assessment": {"id": asmt1.id, "slug": asmt1.slug},
            "values": [{
                "value": "test value",
                "title": "test dropdown lca",
                "type": "Dropdown",
                "definition_id": asmt1.id,
                "id": None,
                "extra": None,
            }]
        }, {
            "assessment": {"id": asmt2.id, "slug": asmt2.slug},
            "values": [],
        }]
    }
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.client.post(
          "/api/bulk_operations/complete",
          data=json.dumps(data),
          headers=self.headers,
      )
    self.assert200(response)
    send_mock.assert_called_once()
    _, mail_title, body = send_mock.call_args[0]
    self.assertEqual(
        mail_title,
        "Completing certifications in bulk is finished",
    )
    self.assertNotIn(
        "The following certifications are completed successfully:",
        body,
    )
    self.assertIn(
        "Failed to complete the following certifications:",
        body,
    )
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
