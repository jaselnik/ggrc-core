# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test audit RBAC."""
import copy
import ddt

from appengine import base

from ggrc import db
from ggrc.models import all_models
from ggrc.models.assessment_template import VerificationWorkflow
from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


@ddt.ddt
class TestAuditRBAC(TestCase):
  """Test audit RBAC"""

  def setUp(self):
    """Generates objects needed by the tests"""
    super(TestAuditRBAC, self).setUp()

    self.api = Api()
    self.client.get("/login")

  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 200),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 200),
      ("Reader", "Program Readers", 200),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_read_access_to_audit(self, rolename,
                                object_role, expected_status_code):
    """Test if {0} with {1} role, has read access to an audit.
    All users except ("Creator", "", 403) should have read access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      program = db.session.query(all_models.Program).one()
      factories.RelationshipFactory(source=program, destination=audit)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    audit = all_models.Audit.query.get(audit_id)
    self.api.set_user(user)
    status_code = self.api.get(audit.__class__, audit_id).status_code
    self.assertEqual(status_code, expected_status_code)

  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 200),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 200),
      ("Reader", "Program Readers", 200),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_read_access_to_assessment(self, rolename,
                                     object_role, expected_status_code):
    """Test if {0} with {1} role, has read access to an assessment.
    All users except ("Creator", "", 403) should have read access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      assessment_id = assessment.id
      program = db.session.query(all_models.Program).one()
      audit = db.session.query(all_models.Audit).one()
      factories.RelationshipFactory(source=program, destination=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    assessment = all_models.Assessment.query.get(assessment_id)
    self.api.set_user(user)
    status_code = self.api.get(assessment.__class__, assessment_id).status_code
    self.assertEqual(status_code, expected_status_code)

  # pylint: disable=invalid-name
  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 200),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 200),
      ("Reader", "Program Readers", 200),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_read_access_to_mapped_issue(self, rolename,
                                       object_role, expected_status_code):
    """Test if {0} with {1} role, has read access to mapped issue.
    All users except ("Creator", "", 403) should have read access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      program = db.session.query(all_models.Program).one()
      issue = factories.IssueFactory()
      issue_id = issue.id
      factories.RelationshipFactory(source=program, destination=audit)
      factories.RelationshipFactory(source=audit, destination=issue)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    audit = all_models.Audit.query.get(audit_id)
    issue = audit.related_objects(_types=["Issue"]).pop()
    self.api.set_user(user)
    status_code = self.api.get(issue.__class__, issue_id).status_code
    self.assertEqual(status_code, expected_status_code)

  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 403),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 403),
      ("Reader", "Program Readers", 403),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_update_access_on_audit(self, rolename,
                                  object_role, expected_status_code):
    """Test if {0} with {1} role, has update access to an audit.

    All users except:
    ("Creator", "", 403),
    ("Creator", "Program Readers", 403),
    ("Reader", "", 403),
    ("Reader", "Program Readers", 403)
    should have update access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      program = db.session.query(all_models.Program).one()
      factories.RelationshipFactory(source=program, destination=audit)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    audit = all_models.Audit.query.get(audit_id)
    self.api.set_user(user)
    response = self.api.get(audit.__class__, audit_id)
    status_code = response.status_code
    if response.status_code == 200:
      status_code = self.api.put(audit, response.json).status_code
    self.assertEqual(status_code, expected_status_code)

  # pylint: disable=invalid-name
  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 403),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 403),
      ("Reader", "Program Readers", 403),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_update_access_on_assessment(self, rolename,
                                       object_role, expected_status_code):
    """Test if {0} with {1} role, has update access to an assessment.

    All users except:
    ("Creator", "", 403),
    ("Creator", "Program Readers", 403),
    ("Reader", "", 403),
    ("Reader", "Program Readers", 403)
    should have update access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      assessment_id = assessment.id
      program = db.session.query(all_models.Program).one()
      audit = db.session.query(all_models.Audit).one()
      factories.RelationshipFactory(source=program, destination=audit)
      factories.RelationshipFactory(source=audit, destination=assessment)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    assessment = all_models.Assessment.query.get(assessment_id)
    self.api.set_user(user)
    response = self.api.get(assessment.__class__, assessment_id)
    status_code = response.status_code
    if response.status_code == 200:
      status_code = self.api.put(assessment, response.json).status_code
    self.assertEqual(status_code, expected_status_code)

  # pylint: disable=invalid-name
  @ddt.data(
      ("Administrator", "", 200),
      ("Creator", "", 403),
      ("Reader", "", 403),
      ("Editor", "", 200),
      ("Administrator", "Program Managers", 200),
      ("Creator", "Program Managers", 200),
      ("Reader", "Program Managers", 200),
      ("Editor", "Program Managers", 200),
      ("Administrator", "Program Editors", 200),
      ("Creator", "Program Editors", 200),
      ("Reader", "Program Editors", 200),
      ("Editor", "Program Editors", 200),
      ("Administrator", "Program Readers", 200),
      ("Creator", "Program Readers", 403),
      ("Reader", "Program Readers", 403),
      ("Editor", "Program Readers", 200),
  )
  @ddt.unpack
  def test_update_access_on_mapped_issue(self, rolename,
                                         object_role, expected_status_code):
    """Test if {0} with {1} role, has update access to a mapped issue.

    All users except:
    ("Creator", "", 403),
    ("Creator", "Program Readers", 403),
    ("Reader", "", 403),
    ("Reader", "Program Readers", 403)
    should have update access."""

    user = self.create_user_with_role(rolename)
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      program = db.session.query(all_models.Program).one()
      issue = factories.IssueFactory()
      issue_id = issue.id
      factories.RelationshipFactory(source=program, destination=audit)
      factories.RelationshipFactory(source=audit, destination=issue)

    if object_role:
      program.add_person_with_role_name(user, object_role)
      db.session.commit()

    audit = all_models.Audit.query.get(audit_id)
    issue = audit.related_objects(_types=["Issue"]).pop()
    self.api.set_user(user)
    response = self.api.get(issue.__class__, issue_id)
    status_code = response.status_code
    if response.status_code == 200:
      status_code = self.api.put(issue, response.json).status_code
    self.assertEqual(status_code, expected_status_code)


@base.with_memcache
class TestPermissionsOnAssessmentTemplate(TestCase):
  """ Test check permissions for ProgramEditor on

  get and post assessment_temaplte action"""

  @classmethod
  def _get_assessment_template_base(cls, title, audit):
    return {
        "title": title,
        "_NON_RELEVANT_OBJ_TYPES": {},
        "_objectTypes": {},
        "audit": {"id": audit.id},
        "audit_title": audit.title,
        "people_value": [],
        "default_people": {
            "assignees": "Admin",
            "verifiers": "Admin",
        },
        "context": {"id": audit.context.id},
        "verification_workflow": VerificationWorkflow.STANDARD,
    }

  def setUp(self):
    super(TestPermissionsOnAssessmentTemplate, self).setUp()
    self.api = Api()
    editor = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.name == "Program Editors"
    ).one()
    self.generator = ObjectGenerator()
    _, self.editor = self.generator.generate_person(
        user_role="Creator"
    )
    _, program = self.generator.generate_object(all_models.Program, {
        "access_control_list": [
            acl_helper.get_acl_json(editor.id,
                                    self.editor.id)
        ]
    })
    program_id = program.id
    _, audit = self.generator.generate_object(
        all_models.Audit,
        {
            "title": "Assessment Template test Audit",
            "program": {"id": program_id},
            "status": "Planned"
        },
    )
    audit_id = audit.id

    generated_at = self.generator.generate_object(
        all_models.AssessmentTemplate,
        self._get_assessment_template_base("Template", audit)
    )
    self.assessment_template_resp, assessment_template = generated_at
    assessment_template_id = assessment_template.id
    self.api.set_user(self.editor)
    self.perms_data = self.api.client.get("/permissions").json
    self.audit = all_models.Audit.query.get(audit_id)
    self.assessment_template = all_models.AssessmentTemplate.query.get(
        assessment_template_id)

  def test_post_action(self):
    """Test create action on AssessmentTemplate created by api"""
    data = [{
        "assessment_template": self._get_assessment_template_base(
            "123",
            self.audit
        )
    }]
    self.api.set_user(self.editor)
    resp = self.api.post(all_models.AssessmentTemplate, data)
    self.assert200(resp)

  def test_get_action(self):
    """Test read action on AssessmentTemplate created by api"""
    resp = self.api.get(all_models.AssessmentTemplate,
                        self.assessment_template.id)
    self.assert200(resp)

  def test_put_action(self):
    """Test update action on AssessmentTemplate created by api"""
    to_update = copy.deepcopy(self.assessment_template_resp.json)
    new_title = "new_{}".format(self.assessment_template.title)
    to_update['assessment_template']['title'] = new_title
    resp = self.api.put(self.assessment_template, to_update)
    self.assert200(resp)
    assessment_tmpl = all_models.AssessmentTemplate.query.get(
        self.assessment_template.id
    )
    self.assertEqual(new_title, assessment_tmpl.title)

  def test_delete_action(self):
    """Test delete action on AssessmentTemplate created by api"""
    resp = self.api.delete(self.assessment_template)
    self.assert200(resp)
    self.assertFalse(all_models.AssessmentTemplate.query.filter(
        all_models.AssessmentTemplate == self.assessment_template.id).all())


@base.with_memcache
class TestPermissionsOnAssessmentRelatedAssignables(TestCase):
  """Test check Reader permissions for Assessment related assignables

  Global Reader once assigned to Assessment as Assignee, should have
  permissions to read/update/delete URLs(Documents) related to this Assessment
  """

  def setUp(self):
    super(TestPermissionsOnAssessmentRelatedAssignables, self).setUp()
    self.api = Api()
    self.generator = ObjectGenerator()

    _, self.reader = self.generator.generate_person(
        user_role="Reader"
    )
    audit = factories.AuditFactory()
    assessment = factories.AssessmentFactory(audit=audit)
    factories.AccessControlPersonFactory(
        ac_list=assessment.acr_name_acl_map["Assignees"],
        person=self.reader,
    )
    factories.RelationshipFactory(source=audit, destination=assessment)
    evidence = factories.EvidenceUrlFactory()
    evidence_id = evidence.id
    evid_rel = factories.RelationshipFactory(source=assessment,
                                             destination=evidence)
    evid_rel_id = evid_rel.id

    self.api.set_user(self.reader)
    self.evidence = all_models.Evidence.query.get(evidence_id)
    self.evid_relationship = all_models.Relationship.query.get(evid_rel_id)

  def test_delete_action(self):
    """Test permissions for delete action on Evidence

    Allow only Global Admin to delete Documents.
    """
    resp = self.api.delete(self.evidence)
    self.assert200(resp)
    self.assertEquals(len(all_models.Evidence.query.filter(
        all_models.Evidence.id == self.evidence.id).all()), 0)
