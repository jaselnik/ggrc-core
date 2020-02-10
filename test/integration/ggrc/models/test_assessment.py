# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for Assessment"""

import collections
import datetime

import freezegun
import ddt
import mock

from ggrc import db
from ggrc.models import all_models
from ggrc.converters import errors
from ggrc.utils import errors as ggrc_errors

from integration import ggrc
from integration.ggrc import generator
from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc.models.test_assessment_base import TestAssessmentBase

from appengine import base


class TestAssessment(TestAssessmentBase):
  """Assessment test cases"""
  # pylint: disable=invalid-name

  def test_auto_slug_generation(self):
    """Test auto slug generation"""
    factories.AssessmentFactory(title="Some title")
    ca = all_models.Assessment.query.first()
    self.assertEqual("ASSESSMENT-{}".format(ca.id), ca.slug)

  def test_enabling_comment_notifications_by_default(self):
    """New Assessments should have comment notifications enabled by default."""
    asmt = factories.AssessmentFactory()

    self.assertTrue(asmt.send_by_default)
    recipients = asmt.recipients.split(",") if asmt.recipients else []
    self.assertEqual(
        sorted(recipients),
        ["Assignees", "Creators", "Verifiers"]
    )

  def test_audit_changes_api(self):
    """Test that users can't change the audit mapped to an assessment."""
    audit_id = factories.AuditFactory().id
    asmt = factories.AssessmentFactory()
    correct_audit_id = asmt.audit_id
    response = self.api.put(asmt, {"audit": {"type": "Audit", "id": audit_id}})
    self.assert400(response)
    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.audit_id, correct_audit_id)

  def test_put_no_audit_change(self):
    """Test that put requests works without audit changes"""
    asmt = factories.AssessmentFactory()
    correct_audit_id = asmt.audit_id
    response = self.api.put(asmt, {"audit": {
        "type": "Audit", "id": correct_audit_id
    }})
    self.assert200(response)
    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.audit_id, correct_audit_id)

  def test_audit_changes_import(self):
    """Test that users can't change the audit mapped to an assessment."""
    audit = factories.AuditFactory()
    asmt = factories.AssessmentFactory()
    correct_audit_id = asmt.audit_id
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("audit", audit.slug),
    ]))
    self._check_csv_response(response, {
        "Assessment": {
            "row_warnings": {
                errors.UNMODIFIABLE_COLUMN.format(line=3, column_name="Audit")
            }
        }
    })
    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.audit_id, correct_audit_id)

  def test_no_audit_change_imports(self):
    """Test that imports work if audit field does not contain changes."""
    factories.AuditFactory()
    asmt = factories.AssessmentFactory()
    correct_audit_id = asmt.audit_id
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("audit", asmt.audit.slug),
    ]))
    self._check_csv_response(response, {})
    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.audit_id, correct_audit_id)

  def test_empty_audit_import(self):
    """Test empty audit import"""
    factories.AuditFactory()
    asmt = factories.AssessmentFactory()
    correct_audit_id = asmt.audit_id
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("audit", ""),
    ]))
    self._check_csv_response(response, {})
    assessment = all_models.Assessment.query.first()
    self.assertEqual(assessment.audit_id, correct_audit_id)

  def test_post_mapped_roles(self):
    """Test mapped roles creation when new assessment created"""
    audit = factories.AuditFactory()
    person = factories.PersonFactory()
    person_email = person.email

    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "audit": {
                "id": audit.id,
                "type": "Audit"
            },
            "access_control_list": [
                acl_helper.get_acl_json(role_id, person.id)
                for role_id in self.assignee_roles.values()
            ],
            "context": {
                "id": audit.context.id,
                "type": "Context"
            },
            "title": "Some title"
        }
    })
    self.assertEqual(response.status_code, 201)

    db.session.add(audit)
    assessment = all_models.Assessment.query.get(
        response.json["assessment"]["id"]
    )
    for role in self.assignee_roles:
      self.assert_mapped_role(role, person_email, assessment)
      self.assert_propagated_role("{}".format(role), person_email, audit)

  def test_put_mapped_roles(self):
    """Test mapped roles creation when assessment updated"""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      audit.add_person_with_role_name(person, "Assignees")
      assessment.add_person_with_role_name(person, "Creators")
      factories.RelationshipFactory(source=audit, destination=assessment)

    # Add verifier to Assessment
    response = self.api.put(assessment, {
        "access_control_list": [
            acl_helper.get_acl_json(role_id, person.id)
            for role_id in self.assignee_roles.values()
        ]
    })
    self.assertEqual(response.status_code, 200)

    db.session.add_all([audit, assessment])
    self.assert_mapped_role("Verifiers", person_email, assessment)
    self.assert_propagated_role("Verifiers", person_email, audit)

  def test_import_mapped_roles(self):
    """Test creation of mapped roles in assessment import."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=asmnt)

      control = factories.ControlFactory()
      snapshot = self._create_snapshots(audit, [control])[0]
      factories.RelationshipFactory(source=asmnt, destination=snapshot)

      users = ["user1@mail.com", "user2@mail.com"]
      for user in users:
        factories.PersonFactory(email=user)

    users_str = "\n".join(users)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmnt.slug),
        ("Assignees", users_str),
        ("Creators", users_str),
        ("Verifiers", users_str),
    ]))
    self._check_csv_response(response, {})

    # Add objects back to session to have access to their id and type
    db.session.add_all([audit, snapshot])
    for role in ["Assignees", "Creators", "Verifiers"]:
      for user in users:
        self.assert_propagated_role(role, user, audit)
        self.assert_propagated_role(role, user, snapshot)

  def test_evidence_mapped_roles(self):
    """Test creation of mapped evidence roles."""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      for ac_role_id in self.assignee_roles.values():
        assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)

      evidence = factories.EvidenceUrlFactory()
      factories.RelationshipFactory(source=assessment, destination=evidence)
      db.session.add(evidence)

    for role in ["Assignees",
                 "Creators",
                 "Verifiers"]:
      self.assert_propagated_role(role, person_email, evidence)

  def test_deletion_mapped_roles(self):
    """Test deletion of mapped roles."""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      for ac_role_id in self.assignee_roles.values():
        assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)

    # Remove verifier and assignee from Assessment
    response = self.api.put(assessment, {
        "access_control_list": [
            acl_helper.get_acl_json(self.assignee_roles["Creators"], person.id)
        ]
    })
    self.assertEqual(response.status_code, 200)
    db.session.add(audit)
    self.assert_mapped_role("Creators", person_email, assessment)
    self.assert_propagated_role("Creators", person_email, audit)

  def test_deletion_multiple_assignee(self):
    """Test deletion of multiple mapped roles."""
    with factories.single_commit():
      persons = [factories.PersonFactory() for _ in range(2)]
      person_ids = [p.id for p in persons]
      person_email = persons[1].email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      for ac_role_id in self.assignee_roles.values():
        for person in persons:
          assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)

    # Remove assignee roles for first person
    response = self.api.put(assessment, {
        "access_control_list": [
            acl_helper.get_acl_json(role_id, person_ids[1])
            for role_id in self.assignee_roles.values()
        ]
    })
    self.assertEqual(response.status_code, 200)
    assignee_acl = all_models.AccessControlPerson.query.filter_by(
        person_id=person_ids[0]
    )
    # All roles for first person should be removed except person_profile
    self.assertEqual(assignee_acl.count(), 1)
    db.session.add(audit)
    for ac_role in self.assignee_roles.keys():
      self.assert_mapped_role(ac_role, person_email, assessment)
      self.assert_propagated_role(
          "{}".format(ac_role), person_email, audit
      )

  def test_assignee_deletion_unmap(self):
    """Test deletion of assignee roles when snapshot is unmapped."""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      for ac_role_id in self.assignee_roles.values():
        assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)
      snapshot = self._create_snapshots(audit, [factories.ControlFactory()])[0]
      rel = factories.RelationshipFactory(
          source=assessment, destination=snapshot
      )
    for ac_role in self.assignee_roles.keys():
      self.assert_propagated_role(
          "{}".format(ac_role), person_email, snapshot
      )
    response = self.api.delete(rel)
    self.assertEqual(response.status_code, 200)
    snap_acls = all_models.AccessControlPerson.query.join(
        all_models.AccessControlList
    ).filter(
        all_models.AccessControlList.object_type == "Snapshot"
    )
    self.assertEqual(snap_acls.count(), 0)

  def test_mapped_roles_saving(self):
    """Test that removing roles for one assessment will not touch second"""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessments = [
          factories.AssessmentFactory(audit=audit) for _ in range(2)
      ]
      snapshot = self._create_snapshots(audit, [factories.ControlFactory()])[0]
      snapshot_id = snapshot.id
      snap_rels = []
      for assessment in assessments:
        for ac_role_id in self.assignee_roles.values():
          assessment.add_person_with_role_id(person, ac_role_id)
        factories.RelationshipFactory(source=audit, destination=assessment)
        snap_rels.append(factories.RelationshipFactory(
            source=assessment, destination=snapshot
        ))

    response = self.api.delete(snap_rels[0])
    self.assertEqual(response.status_code, 200)

    snapshot = all_models.Snapshot.query.get(snapshot_id)
    for ac_role in self.assignee_roles.keys():
      self.assert_propagated_role(
          "{}".format(ac_role), person_email, snapshot
      )

  def test_audit_roles_saving(self):
    """Test that snapshot unmapping will not affect audit"""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      snapshot = self._create_snapshots(audit, [factories.ControlFactory()])[0]
      for ac_role_id in self.assignee_roles.values():
        assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)
      snap_rel = factories.RelationshipFactory(
          source=assessment, destination=snapshot
      )

    response = self.api.delete(snap_rel)
    self.assertEqual(response.status_code, 200)

    db.session.add(audit)
    for ac_role in self.assignee_roles.keys():
      self.assert_propagated_role(
          "{}".format(ac_role), person_email, audit
      )

  def test_mapped_regulations_acl(self):
    """Test creation of acl roles for Regulations and Objective snapshots."""
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      for ac_role_id in self.assignee_roles.values():
        assessment.add_person_with_role_id(person, ac_role_id)
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
      objective = factories.ObjectiveFactory()
      regulation = factories.RegulationFactory()
      snapshots = self._create_snapshots(
          audit, [control, objective, regulation]
      )
      factories.RelationshipFactory(
          source=snapshots[0], destination=snapshots[1]
      )
      factories.RelationshipFactory(
          source=snapshots[2], destination=snapshots[0]
      )
      factories.RelationshipFactory(
          source=assessment, destination=snapshots[0]
      )

    for role in ["Assignees", "Creators", "Verifiers"]:
      for snapshot in snapshots:
        # Mapped Assignee roles should be created for all snapshots, not only
        # for control that related to assessment
        self.assert_propagated_role(role, person_email, snapshot)

  def test_assessment_when_get_model_work_correct(self):
    """Test get_model return right result in build_type_query for json"""
    with factories.single_commit():
      audit = factories.AuditFactory()

    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "Assessment",
            "context": None,
            "audit": {
                "id": audit.id,
                "type": "Audit"
            }
        }
    })

    self.assert201(response)

  def test_assessment_when_get_model_none(self):
    """Test get_model return None in build_type_query for json"""
    audit = factories.AuditFactory()

    with mock.patch('ggrc.models.get_model', return_value=None):
      response = self.api.post(all_models.Assessment, {
          "assessment": {
              "title": "Assessment",
              "context": None,
              "status": "In Progress",
              "modified_by_id": None,
              "audit": {
                  "id": audit.id,
                  "type": "Audit"
              }
          }
      })

    self.assert201(response)

  def test_assessment_with_multiple_mapped_persons(self):
    """Test cav on assessment with multiple mapped persons."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      persons = factories.PersonFactory(), factories.PersonFactory()
      expected_persons_ids = [person.id for person in persons]

      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          definition_id=assessment.id,
          attribute_type="Map:Person",
      )

      for person in persons:
        custom_attribute_value = factories.CustomAttributeValueFactory(
            custom_attribute=cad,
            attributable=assessment,
            attribute_value="Person",
        )
        custom_attribute_value.attribute_object = person

    get_response_json = self.api.get(all_models.Assessment,
                                     assessment.id).json["assessment"]
    persons_ids = [
        obj["id"] for cav in get_response_json["custom_attribute_values"]
        for obj in cav["attribute_objects"]
    ]

    self.assertEquals(persons_ids, expected_persons_ids)

  def test_assessment_after_cav_person_delete(self):
    """Test cav on assessment after cav delete"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(audit=audit)
      assessment_id = assessment.id
      person = factories.PersonFactory()

      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          definition_id=assessment.id,
          attribute_type="Map:Person",
      )

      cav = factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=assessment,
          attribute_value="Person",
      )
      cav.attribute_object = person

    cav_json = cav.log_json()
    cav_json["attribute_objects"] = None
    cav_json["attributeType"] = "person"
    self.api.put(assessment, {"custom_attribute_values": [cav_json]})

    assessment = all_models.Assessment.query.get(assessment_id)
    self.assertListEqual(assessment.custom_attribute_values, [])


@ddt.ddt
class TestAssessmentStatus(TestAssessmentBase):
  """Test change assessment status"""

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestAssessmentStatus, self).setUp()
    with factories.single_commit():
      person = factories.PersonFactory()
      assessment = factories.AssessmentFactory()
      assessment.add_person_with_role_name(person, "Creators")
    self.assessment = assessment
    self.assessment_id = assessment.id
    self.person = person
    self.person_id = person.id
    self.initial_state = assessment.status

  @ddt.data("In Review", "Verified", "Rework Needed")
  def test_missing_verifiers_status(self, new_status):
    """Test 400 while change assessment status to {} with missing verifiers"""
    response = self.api.put(self.assessment, {"status": new_status})
    self.assert400(response)
    self.assertEqual(
        response.json['message'],
        ggrc_errors.MISSING_ASSESSMENT_VERIFIERS
    )
    assessment = all_models.Assessment.query.get(self.assessment_id)
    self.assertEqual(assessment.status, self.initial_state)


@ddt.ddt
@base.with_memcache
class TestAssessmentUpdates(ggrc.TestCase):
  """ Test various actions on Assessment updates """

  def setUp(self):
    super(TestAssessmentUpdates, self).setUp()
    self.api = ggrc.api_helper.Api()
    self.generator = generator.ObjectGenerator()
    _, program = self.generator.generate_object(all_models.Program)
    program_id = program.id
    _, audit = self.generator.generate_object(
        all_models.Audit,
        {
            "title": "Assessment Updates Audit",
            "program": {"id": program_id},
            "status": "Planned"
        },
    )

    with freezegun.freeze_time("2015-04-01 17:13:15"):
      _, assessment = self.generator.generate_object(
          all_models.Assessment,
          {
              "title": "Assessment-Comment",
              "audit": {"id": audit.id, "type": "Audit"},
              "audit_title": audit.title,
              "people_value": [],
              "default_people": {
                  "verifiers": "Admin",
                  "assignees": "Admin",
              },
              "context": {"id": audit.context.id},
          }
      )

    self.assessment_id = assessment.id
    self.assessment = all_models.Assessment.query.get(self.assessment_id)

  # pylint: disable=invalid-name
  def test_updated_at_changes_after_comment(self):
    """Test updated_at date is changed after adding a comment to assessment"""
    with freezegun.freeze_time("2016-04-01 18:22:09"):
      self.generator.generate_comment(
          self.assessment,
          "Verifiers",
          "some comment",
          send_notification="true"
      )

      asmt = all_models.Assessment.query.get(self.assessment.id)
      self.assertEqual(asmt.updated_at,
                       datetime.datetime(2016, 4, 1, 18, 22, 9))

  def test_update_assessment_and_get_list(self):
    """Test get value for assessment cached value after update."""
    old_state = "In Progress"
    new_state = "In Review"
    with factories.single_commit():
      asmt = all_models.Assessment.query.filter(
          all_models.Assessment.id == self.assessment_id
      ).first()
      asmt.status = old_state
      self.update_assessment_verifiers(asmt, new_state)
    # required for populate cache
    content = self.api.client.get(
        "/api/assessments?id__in={}".format(self.assessment_id)
    )
    self.assertEqual(
        old_state,
        content.json['assessments_collection']['assessments'][0]['status']
    )
    self.api.put(all_models.Assessment.query.get(self.assessment_id),
                 {"status": new_state})
    content = self.api.client.get(
        "/api/assessments?id__in={}".format(self.assessment_id)
    )
    self.assertEqual(
        new_state,
        content.json['assessments_collection']['assessments'][0]['status']
    )

  @ddt.data(
      (None, "Control", "Plan - {}", "Plan - 0<br>Plan - 1<br>Plan - 2"),
      ("", "Control", "Plan - {}",
       "Plan - 0<br>Plan - 1<br>Plan - 2"),
      ("Asmnt plan", "Control", "Plan - {}",
       "Asmnt plan<br>Plan - 0<br>Plan - 1<br>Plan - 2"),
      ("Asmnt plan", "Market", "Plan - {}", "Asmnt plan"),
      (None, "Control", None, ""),
      ("", "Control", None, ""),
      ("Asmnt plan", "Control", None, "Asmnt plan"),
      (None, "Control", "", ""),
      ("", "Control", "", ""),
      ("Asmnt plan", "Control", "", "Asmnt plan"),
  )
  @ddt.unpack
  def test_assessment_proc_on_map(self, asmnt_plan, asmnt_type, test_plan,
                                  expected_plan):
    """Test if Snapshot test_plan added to Assessment after mapping"""
    # pylint: disable=too-many-locals
    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(
          audit=audit, assessment_type=asmnt_type, test_plan=asmnt_plan
      )
      factories.RelationshipFactory(source=audit, destination=assessment)
      controls = [
          factories.ControlFactory(
              test_plan=test_plan.format(i) if test_plan else test_plan
          )
          for i in range(3)
      ]
    snapshots = self._create_snapshots(audit, controls)

    relation = [{
        "relationship": {
            "context": {
                "context_id": None,
                "id": assessment.context_id,
                "type": "Context"
            },
            "destination": {
                "id": snapshot.id,
                "type": "Snapshot"
            },
            "source": {
                "id": assessment.id,
                "type": "Assessment"
            }
        }
    } for snapshot in snapshots]

    response = self.api.post(all_models.Relationship, relation)
    self.assertEqual(response.status_code, 200)

    asmnt = all_models.Assessment.query.get(assessment.id)
    self.assertEqual(asmnt.test_plan, expected_plan)
