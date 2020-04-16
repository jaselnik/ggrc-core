# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests of assessment notifications."""
import collections
from datetime import datetime

import ddt
import mock
from pytz import timezone

from ggrc import db
from ggrc.notifications import common
from ggrc.models import Person, Assessment, AccessControlRole
from ggrc.models import all_models
from integration.ggrc import api_helper
from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


@ddt.ddt
class TestAssessmentNotification(TestCase):
  """Tests of assessment notifications"""

  @classmethod
  def setUpClass(cls):
    """Set up test cases for all tests."""
    cls.primary_role_id = AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Primary Contacts"
    ).first().id

    cls.secondary_role_id = AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Secondary Contacts"
    ).first().id

  def setUp(self):
    super(TestAssessmentNotification, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()
    self.auditor = Person.query.filter_by(email="user@example.com").one()
    self.api.set_user(self.auditor)
    audit = factories.AuditFactory()
    assignee_acr = all_models.AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Assignees",
    ).first()

    self.api.post(Assessment, {
        "assessment": {
            "title": "Assessment1",
            "context": None,
            "audit": {
                "id": audit.id,
                "type": "Audit",
            },
            "access_control_list": [
                acl_helper.get_acl_json(self.primary_role_id, self.auditor.id),
                acl_helper.get_acl_json(assignee_acr.id, self.auditor.id)
            ],
            "status": "In Progress",
        }
    })

    self.assessment = Assessment.query.filter_by(title="Assessment1").one()

    self.cad1 = factories.CustomAttributeDefinitionFactory(
        definition_type="assessment",
        title="ca1",
    )
    factories.CustomAttributeValueFactory(
        custom_attribute=self.cad1,
        attributable=self.assessment
    )

    self.cad3 = factories.CustomAttributeDefinitionFactory(
        definition_type="assessment",
        attribute_type="Checkbox",
        title="ca3",
    )
    factories.CustomAttributeValueFactory(
        custom_attribute=self.cad3,
        attributable=self.assessment
    )

    db.engine.execute(
        """
            UPDATE notifications
               SET sent_at = NOW()
        """
    )

  def test_common_attr_change(self):
    """Test notification when common attribute value is changed"""
    response = self.api.put(self.assessment, {"test_plan": "steps"})
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["ASSESSMENT PROCEDURE"],
        ("steps", "")
    )

  def test_custom_attr_change(self):
    """Test notification when custom attribute value is changed"""
    custom_attribute_values = [{
        "custom_attribute_id": self.cad1.id,
        "attribute_value": "test value",
    }]
    response = self.api.put(self.assessment, {
        "custom_attribute_values": custom_attribute_values
    })
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"].keys(), ["CA1"])

  def test_description_custom_change(self):
    """Test notification updated data when custom attribute value is changed"""
    response = self.api.put(self.assessment, {
        "title": "test_title",
        "description": "test_description"
    })
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["TITLE"],
        ("test_title", "Assessment1")
    )
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["DESCRIPTION"],
        ("test_description", "")
    )

  def test_evidence_change_assmt(self):
    """Test notification updated data when evidence values is changed"""
    with factories.single_commit():
      evidence_url = "test.com"
      evidence_file = "test_gdrive.file"
      evidence_1 = factories.EvidenceUrlFactory(link=evidence_url,
                                                title=evidence_url)
      evidence_2 = factories.EvidenceFileFactory(link=evidence_file,
                                                 title=evidence_file)
    response = self.api.put(self.assessment, {
        "actions": {"add_related": [
            {
                "id": evidence_1.id,
                "type": "Evidence",
            },
            {
                "id": evidence_2.id,
                "type": "Evidence",
            },
        ]}
    })
    self.assert200(response)
    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["EVIDENCE URL"],
        (evidence_url, "")
    )
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["EVIDENCE FILE"],
        (evidence_file, "")
    )

  def test_labels_change(self):
    """Test notification updated data when labels are changed"""
    label_new = factories.LabelFactory(name="test_label",
                                       object_type='Assessment')
    response = self.api.put(self.assessment, {'labels': [{
        "name": label_new.name,
        "id": label_new.id
    }]})
    self.assert200(response)
    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["LABELS"],
        ("test_label", "")
    )

  def test_ca_change_by_import(self):
    """Test notification when custom attribute value is changed by import"""

    with factories.single_commit():
      assessment = factories.AssessmentFactory(status="Completed")
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          title="Test GCAD",
      )
      assessment_slug = assessment.slug
      assessment_id = assessment.id
      user = all_models.Person.query.filter_by(
          email="user@example.com").first()
      assessment.add_person_with_role_name(user, "Assignees")

    from flask import g
    setattr(g, '_current_user', user)

    import_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment_slug),
        ("Test GCAD", "test value"),
    ])
    response = self.import_data(import_data)
    self._check_csv_response(response, {})

    notifs, _ = common.get_daily_notifications()

    self.assertEqual(len(notifs), 2)
    assessment = all_models.Assessment.query.get(assessment_id)
    cad = assessment.get_custom_attribute_definitions().filter_by(
        title="Test GCAD").first()
    self.assertEqual(
        [i.attribute_value for i in cad.attribute_values], ["test value"])

  def test_checkbox_attr_change(self):
    """Test notification when person attribute value is changed"""
    custom_attribute_values = [{
        "custom_attribute_id": self.cad3.id,
        "attribute_value": "1",
    }]
    response = self.api.put(self.assessment, {
        "custom_attribute_values": custom_attribute_values
    })
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"].keys(), ["CA3"])

  def test_access_conrol_list(self):
    """Test notification when access conrol list is changed"""
    creator_acr = all_models.AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Creators",
    ).first()
    assignee_acr = all_models.AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Assignees",
    ).first()
    response = self.api.put(self.assessment, {
        "access_control_list": [
            acl_helper.get_acl_json(self.secondary_role_id, self.auditor.id),
            acl_helper.get_acl_json(assignee_acr.id, self.auditor.id),
            acl_helper.get_acl_json(creator_acr.id, self.auditor.id),
        ],
    })
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["PRIMARY CONTACTS"],
        ("", "user@example.com")
    )
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["SECONDARY CONTACTS"],
        ("user@example.com", "")
    )

  def test_multiple_updates(self):
    """Test notification for multiple updates"""
    response = self.api.put(self.assessment, {"test_plan": "steps"})
    self.assert200(response)

    response = self.api.put(self.assessment, {"title": "new title"})
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    updated = notif_data["user@example.com"]["assessment_updated"]
    self.assertEqual(len(notifs), 1)
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["TITLE"],
        ("new title", "Assessment1")
    )
    self.assertEqual(
        updated[self.assessment.id]["updated_data"]["ASSESSMENT PROCEDURE"],
        ("steps", "")
    )

  # pylint: disable=invalid-name
  def test_multiple_updates_return_old_value(self):
    """Test notification for multiple updates if value did not changed"""
    old_test_plan = self.assessment.test_plan
    response = self.api.put(self.assessment, {"test_plan": "steps"})
    self.assert200(response)

    response = self.api.put(self.assessment, {"test_plan": old_test_plan})
    self.assert200(response)

    notifs, notif_data = common.get_daily_notifications()
    self.assertEqual(len(notifs), 1)
    self.assertEqual({}, notif_data)

  def test_multiply_mapping(self):
    """Test notification for multiply mapping"""
    controls = [factories.ControlFactory() for _ in xrange(5)]
    snapshots = self._create_snapshots(self.assessment.audit, controls)

    def get_relation_dict(destination_obj):
      return {
          "relationship": {
              "context": {"id": self.assessment.audit.context.id,
                          "type": self.assessment.audit.context.type},
              "source": {"id": self.assessment.id,
                         "type": self.assessment.type},
              "destination": {"id": destination_obj.id,
                              "type": destination_obj.type}
          }
      }
    notifs, _ = common.get_daily_notifications()
    self.assertFalse(len(notifs))
    self.assessment.status = "In Progress"
    post_data = [get_relation_dict(s) for s in snapshots]
    db.session.add(self.assessment)
    resp = self.api.send_request(
        self.api.client.post, obj=all_models.Relationship, data=post_data)
    self.assert200(resp)
    notifs, _ = common.get_daily_notifications()
    self.assertEqual(len(notifs), 1)

  def assert_asmnt_notifications(self):
    """Check if Assessment reopen notifications are sent."""
    notifs, _ = common.get_daily_notifications()
    self.assertGreaterEqual(len(notifs), 2)

    with mock.patch("ggrc.notifications.common.send_email") as send_email_mock:
      self.client.get("/_notifications/send_daily_digest")
      _, _, content = send_email_mock.call_args[0]
      self.assertIn("has been updated", content)
      self.assertIn("Reopened assessments", content)

  @ddt.data(
      all_models.Assessment.DONE_STATE,
      all_models.Assessment.FINAL_STATE,
  )
  def test_import_evidence_mapped(self, status):
    """Test notifications for '{}' Assessment if Evidence mapped in import."""
    object_generator = ObjectGenerator()
    _, user = object_generator.generate_person(user_role="Creator")
    assessment = factories.AssessmentFactory()
    assessment.add_person_with_role_name(user, "Verifiers")
    assessment.status = status
    db.session.commit()

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("Evidence URL", "some url"),
    ]))
    self._check_csv_response(response, {})
    self.assert_asmnt_notifications()

  @ddt.data(
      all_models.Assessment.DONE_STATE,
      all_models.Assessment.FINAL_STATE,
  )
  def test_import_lcad_changed(self, status):
    """Test notifications for '{}' Assessment if LCAD changed in import."""
    object_generator = ObjectGenerator()
    _, user = object_generator.generate_person(user_role="Creator")
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      factories.CustomAttributeDefinitionFactory(
          title="Test LCAD",
          definition_type="assessment",
          definition_id=assessment.id,
          attribute_type="Text",
      )
    assessment.add_person_with_role_name(user, "Verifiers")
    assessment.status = status
    db.session.commit()

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("Test LCAD", "some value"),
    ]))
    self._check_csv_response(response, {})
    self.assert_asmnt_notifications()

  @ddt.data(
      all_models.Assessment.DONE_STATE,
      all_models.Assessment.FINAL_STATE,
  )
  def test_import_snapshot_mapped(self, status):
    """Test notifications for '{}' Assessment if snapshot mapped in import."""
    object_generator = ObjectGenerator()
    _, user = object_generator.generate_person(user_role="Creator")
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      control = factories.ControlFactory()
    # pylint: disable=expression-not-assigned
    self._create_snapshots(assessment.audit, [control])[0]
    assessment.add_person_with_role_name(user, "Verifiers")
    assessment.status = status
    db.session.commit()

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assessment.slug),
        ("Map:control versions", control.slug),
    ]))
    self._check_csv_response(response, {})
    self.assert_asmnt_notifications()

  def test_notification_create_time(self):
    """Test for Assessment created date verification"""
    audit = factories.AuditFactory()
    time_stamp = datetime.now(timezone('US/Pacific'))
    date_format = '%m/%d/%Y %H:%M:%S %Z'
    converted_date = time_stamp.strftime(date_format)
    assignee_acr = all_models.AccessControlRole.query.filter_by(
        object_type="Assessment",
        name="Assignees",).first()
    self.api.post(Assessment, {
        "assessment": {
            "title": "Assessment1",
            "context": None,
            "audit": {
                "id": audit.id,
                "type": "Audit",
            },
            "access_control_list": [
                acl_helper.get_acl_json(self.primary_role_id, self.auditor.id),
                acl_helper.get_acl_json(assignee_acr.id, self.auditor.id)],
            "status": "In Progress",
        }
    })
    notifs, notif_data = common.get_daily_notifications()
    asmts_data = notif_data["user@example.com"]["assessment_open"].values()
    obj_created_at = asmts_data[0]["obj_created_at"].values()
    self.assertEqual(len(notifs), 1)
    self.assertEqual(obj_created_at, [converted_date])

  @mock.patch("ggrc.settings.DAILY_DIGEST_BATCH_SIZE", 1)
  def test_send_daily_email_one_chunk(self):
    """Test one user receive one daily digest email"""
    object_generator = ObjectGenerator()
    _, user = object_generator.generate_person(user_role="Creator")
    with factories.single_commit():
      assessment1 = factories.AssessmentFactory()
      assessment2 = factories.AssessmentFactory()
      assessment1.add_person_with_role_name(user, "Verifiers")
      assessment2.add_person_with_role_name(user, "Verifiers")
      assessment1.status = "Not Started"
      assessment2.status = "Not Started"
      db.session.commit()

    response = self.import_data(*[
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", assessment1.slug),
            ("Evidence URL", "test url"),
        ]),
        collections.OrderedDict([
            ("object_type", "Assessment"),
            ("Code*", assessment2.slug),
            ("Evidence URL", "test url"),
        ]),
    ])
    self._check_csv_response(response, {})
    with mock.patch("ggrc.notifications.common.send_email") as send_email_mock:
      self.client.get("/_notifications/send_daily_digest")
      send_email_mock.assert_called_once()
