# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for With Custom Restrictions mixin"""

import collections
import ddt

from flask import g

from ggrc import db
from ggrc.models import all_models
from ggrc.models import assessment_template

from integration.ggrc import TestCase
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories
from integration.ggrc.query_helper import WithQueryApi


VerificationWorkflow = assessment_template.VerificationWorkflow


# pylint: disable=invalid-name
@ddt.ddt
class TestWithCustomRestrictions(TestCase, WithQueryApi):
  """Test cases for With Custom Restrictions mixin"""

  def setUp(self):
    super(TestWithCustomRestrictions, self).setUp()
    self.client.get("/login")
    self.api = Api()

  @staticmethod
  def assign_person(object_, role_name, person_id):
    """Assign person to object with specified role."""
    # pylint: disable=protected-access
    acr = all_models.AccessControlRole.query.filter_by(
        name=role_name,
        object_type=object_.type,
    ).first()
    for ac_list in object_._access_control_list:
      if ac_list.ac_role.name == acr.name and acr.object_type == object_.type:
        factories.AccessControlPersonFactory(
            person_id=person_id,
            ac_list=ac_list,
        )
        return
    raise Exception("Unable to assign role")

  @staticmethod
  def generate_person():
    """Generate person and assign global Creator role"""
    person = factories.PersonFactory()
    reader_role = all_models.Role.query.filter(
        all_models.Role.name == "Reader").first()
    rbac_factories.UserRoleFactory(role=reader_role, person=person)
    return person

  def set_current_person(self, user):
    """Set user as current for Flask app"""
    user_id = user.id
    self.api.set_user(user)
    user = all_models.Person.query.get(user_id)
    setattr(g, '_current_user', user)

  @ddt.data(
      ('Assignees', True),
      ('Creators', False),
      ('Verifiers', False),
      ("Primary Contacts", False),
      ("Secondary Contacts", False)
  )
  @ddt.unpack
  def test_assignee_has_restricted_access(self, role_name, restricted_access):
    # pylint: disable=protected-access
    """Test Assignee role restricted access to fields for Assessment
    with sox302"""
    with factories.single_commit():
      assmnt = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      person = self.generate_person()
      self.assign_person(assmnt, role_name, person.id)
    assmnt_id = assmnt.id
    self.set_current_person(person)
    assmnt = all_models.Assessment.query.get(assmnt_id)
    self.assertEqual(assmnt._is_sox_restricted(), restricted_access)

  @ddt.data("Audit Captains", "Auditors")
  def test_propagated_audit_roles(self, audit_role):
    """
    Test user sox302 permissions for Assessment with roles in Audit
    and Assessment
    """
    user = self.generate_person()
    audit = factories.AuditFactory()
    self.assign_person(audit, audit_role, user.id)

    assessment = factories.AssessmentFactory(
        audit=audit,
        verification_workflow=VerificationWorkflow.SOX302,
    )
    self.assign_person(assessment, "Assignees", user.id)
    factories.RelationshipFactory(source=audit, destination=assessment)

    self.assertFalse(assessment.is_user_role_restricted(user))

  @ddt.data("Program Managers", "Program Editors")
  def test_propagated_program_roles(self, program_role):
    """
    Test user sox302 permissions for Assessment with roles in Program
    and Assessment
    """
    user = self.generate_person()

    program = factories.ProgramFactory()
    self.assign_person(program, program_role, user.id)

    audit = factories.AuditFactory(program=program)
    factories.RelationshipFactory(source=audit, destination=program)

    assessment = factories.AssessmentFactory(
        audit=audit,
        verification_workflow=VerificationWorkflow.SOX302,
    )
    self.assign_person(assessment, "Assignees", user.id)
    factories.RelationshipFactory(source=audit, destination=assessment)

    self.assertFalse(assessment.is_user_role_restricted(user))

  @ddt.data(
      (
          True,
          ['access_control_list',
           'description',
           'title',
           'labels',
           'test_plan',
           'assessment_type',
           'slug',
           'notes',
           'start_date',
           'design',
           'operationally',
           'reminderType',
           'issue_tracker',
           'map: Snapshot',
           'map: Issue'],
      ),
      (
          False,
          [],
      ),
  )
  @ddt.unpack
  def test_get_302_sox_assmt(self, is_sox_restricted, ro_fields):
    """Test get sox302 assessment by api call returns proper values"""
    verification_workflow = VerificationWorkflow.SOX302 \
        if is_sox_restricted else VerificationWorkflow.STANDARD

    with factories.single_commit():
      user = self.generate_person()
      assessment = factories.AssessmentFactory(
          verification_workflow=verification_workflow,
      )

    self.assign_person(assessment, "Assignees", user.id)
    assmnt_id = assessment.id
    self.set_current_person(user)
    response = self.api.get(all_models.Assessment, assmnt_id)

    self.assert200(response)
    res = response.json['assessment']
    self.assertEqual(is_sox_restricted, res['_is_sox_restricted'])
    self.assertEqual(ro_fields, res['_readonly_fields'])

  @ddt.data(
      ('Issue', {}),
  )
  @ddt.unpack
  def test_post_readonly_relationship(self, restricted_model, factory_args):
    """Test post mapping to readonly object is forbidden"""
    with factories.single_commit():
      user = self.generate_person()
      restricted_obj = factories.get_model_factory(
          restricted_model)(**factory_args)
      self.assign_person(restricted_obj, "Admin", user.id)
      obj_id, obj_type = restricted_obj.id, restricted_obj.type
      assessment = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      self.assign_person(assessment, "Assignees", user.id)
    assessment_id = assessment.id

    self.set_current_person(user)
    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": assessment_id, "type": "Assessment"},
            "destination": {"id": obj_id, "type": obj_type},
            "context": None
        },
    })

    self.assert403(response)
    self.assertEqual(response.json, 'Mapping of this objects is not allowed')

  def test_put_snapshot_mapping(self):
    """Test put mapping to Snapshot object is forbidden"""
    with factories.single_commit():
      user = self.generate_person()
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(
          audit=audit,
          verification_workflow=VerificationWorkflow.SOX302,
      )
      assmnt_id = assessment.id
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
      self.assign_person(assessment, "Assignees", user.id)

    snapshot_id = self._create_snapshots(audit, [control])[0].id
    self.set_current_person(user)

    response = self.api.put(all_models.Assessment.query.get(assmnt_id),
                            {"actions": {"add_related": [
                                {
                                    "id": snapshot_id,
                                    "type": "Snapshot",
                                }
                            ]}})

    self.assert403(response)
    self.assertEqual(response.json['message'], 'Mapping of this objects is not'
                                               ' allowed')

  def test_post_issue_not_mapped(self):
    """Test posted issue not mapped automatically"""
    with factories.single_commit():
      user = self.generate_person()
      assessment = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      self.assign_person(assessment, "Assignees", user.id)
    assessment_id = assessment.id
    self.set_current_person(user)
    response = self.api.post(all_models.Issue, data={
        "issue": {
            "title": "TestDueDate",
            "context": None,
            "due_date": "06/14/2018",
            "assessment": {
                "id": assessment_id,
                "type": "Assessment",
            },
        }
    })

    self.assert403(response)
    self.assertEqual(response.json, 'Mapping of this objects is not allowed')

  @ddt.data({'description': 'New description'},
            {'title': 'New title'},
            {'test_plan': 'New test plan'},
            {'assessment_type': 'New assessment type'},
            {'slug': 'updated slug'},
            {'notes': 'some notes'},
            {'start_date': '2010-10-10'},
            {'design': 'new design'},
            {'operationally': 'updated operationally'},
            {'reminderType': 'new type'},
            {'issue_tracker': {"enabled": True}})
  def test_update_restricted_assessment(self, payload):
    """Test user sox302 permissions to update restricted Assessment"""
    with factories.single_commit():
      user = self.generate_person()
      assessment = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      assmnt_id = assessment.id
      self.assign_person(assessment, "Assignees", user.id)

    self.set_current_person(user)
    response = self.api.put(all_models.Assessment.query.get(assmnt_id),
                            payload)

    self.assert403(response)
    self.assertEqual(response.json['message'], 'Some fields in the object is '
                                               'in a read-only mode for '
                                               'Assignees')

  def test_import_sox302_assmt_ro_field(self):
    """Test user sox302 update read only fields via import"""
    exp_errors = {
        'Assessment': {
            'row_warnings': {"Line 3: The system is in a read-only mode and "
                             "is dedicated for SOX needs. The following "
                             "columns will be ignored: 'title'."},
        }
    }
    with factories.single_commit():
      user = self.generate_person()
      assessment = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      person_id = user.id
      assmnt_slug = assessment.slug
      self.assign_person(assessment, "Assignees", person_id)

    self.set_current_person(user)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assmnt_slug),
        ("Title", "TestTitle"),
    ]), person=all_models.Person.query.get(person_id))

    self._check_csv_response(response, exp_errors)

  def test_import_sox302_assmt_mapping_issue(self):
    """Test user sox302 update restricted mappings"""

    error_msg = ("Line 3: You don't have permission "
                 "to update mappings for Issue: {slug}.")

    with factories.single_commit():
      user = self.generate_person()
      assessment = factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.SOX302,
      )
      assmnt_slug = assessment.slug
      person_id = user.id
      self.assign_person(assessment, "Assignees", person_id)
      issue = factories.IssueFactory()
      issue_slug = issue.slug

    self.set_current_person(user)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assmnt_slug),
        ("map: Issue", issue_slug),
    ]), person=all_models.Person.query.get(person_id))

    exp_errors = {
        'Assessment': {
            'row_warnings': {
                error_msg.format(slug=issue_slug.lower())
            },
        }
    }
    self._check_csv_response(response, exp_errors)

  def test_import_sox302_assmt_mapping_snapshot(self):
    """Test user sox302 update restricted mappings"""
    error_msg = ("Line 3: You don't have permission "
                 "to update mappings for Control: {slug}.")

    with factories.single_commit():
      audit = factories.AuditFactory()
      assessment = factories.AssessmentFactory(
          audit=audit,
          verification_workflow=VerificationWorkflow.SOX302,
      )
      user = self.generate_person()
      factories.RelationshipFactory(source=audit, destination=assessment)
      control = factories.ControlFactory()
      person_id = user.id
      self.assign_person(assessment, "Assignees", person_id)

    assmnt_slug = assessment.slug
    cntrl_slug = control.slug

    self._create_snapshots(audit, [control])
    db.session.commit()
    self.set_current_person(user)
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", assmnt_slug),
        ("map:Control versions", cntrl_slug),
    ]), person=all_models.Person.query.get(person_id))
    exp_errors = {
        'Assessment': {
            'row_warnings': {error_msg.format(slug=cntrl_slug.lower())},
        }
    }
    self._check_csv_response(response, exp_errors)
