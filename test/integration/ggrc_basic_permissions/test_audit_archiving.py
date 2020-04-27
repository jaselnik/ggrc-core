# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Archived Audit."""

from ddt import data, ddt, unpack
from ggrc.app import db
from ggrc.models import all_models
from ggrc.models.inflector import get_model
from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


def _create_obj_dict(obj, audit_id, context_id, assessment_id=None):
  """Create POST dicts for various object types."""
  table_singular = obj._inflector.table_singular
  dicts = {
      "issue": {
          "title": "Issue Title " + factories.random_str(),
          "context": {
              "id": context_id,
              "type": "Context"
          },
          "audit": {
              "id": audit_id,
              "type": "Audit"
          },
          "due_date": "10/10/2019"
      },
      "assessment": {
          "title": "Assessment Title",
          "context": {
              "id": context_id,
              "type": "Context"
          },
          "audit": {
              "id": audit_id,
              "type": "Audit"
          }
      },
      "assessment_template": {
          "title": "Assessment Template Title",
          "template_object_type": "Control",
          "default_people": {
              "verifiers": "Auditors",
              "assignees": "Audit Lead"
          },
          "context": {
              "id": context_id,
              "type": "Context"
          },
          "audit": {
              "id": audit_id,
              "type": "Audit"
          }
      },
      "relationship": {
          "context": {
              "id": context_id,
              "type": "Context"
          },
          "source": {
              "id": assessment_id,
              "type": "Assessment"
          },
          "destination": {
              "id": audit_id,
              "type": "Audit"
          }
      }
  }
  return {
      table_singular: dicts[table_singular]
  }


class TestAuditArchivingBase(TestCase):
  """Base class for testing archived audits."""
  # pylint: disable=too-many-instance-attributes
  def setUp(self):
    """Generates objects needed by the tests"""
    super(TestAuditArchivingBase, self).setUp()
    self.api = Api()
    self.client.get("/login")


@ddt
class TestAuditArchiving(TestAuditArchivingBase):
  """Tests Archived Audits

  Tests the following cases:

  1. Audit can only be archived by Global Admin or Program Manager
  2. Audit can only be unarchived by Global Admin or Program Manager
  """

  @data(
      ('Administrator', '', 200, False, 'archive'),
      ('Editor', '', 403, False, 'archive'),
      ('Reader', '', 403, False, 'archive'),
      ('Creator', '', 403, False, 'archive'),
      ('Creator', 'Program Managers', 200, False, 'archive'),
      ('Creator', 'Program Editors', 403, False, 'archive'),
      ('Creator', 'Program Readers', 403, False, 'archive'),
      ('Administrator', '', 200, True, 'unarchive'),
      ('Editor', '', 403, True, 'unarchive'),
      ('Reader', '', 403, True, 'unarchive'),
      ('Creator', '', 403, True, 'unarchive'),
      ('Creator', 'Program Managers', 200, True, 'unarchive'),
      ('Creator', 'Program Editors', 403, True, 'unarchive'),
      ('Creator', 'Program Readers', 403, True, 'unarchive')
  )
  @unpack
  # pylint: disable-msg=too-many-arguments
  def test_archived_state(self, rolename, object_role, status,
                          start_state, end_state):
    """Test if {0}-{1} can {4} an audit: expected {2}."""
    with factories.single_commit():
      audit = factories.AuditFactory(archived=start_state)
      audit_id = audit.id
      program = audit.program
      factories.RelationshipFactory(source=program, destination=audit)
      user = self.create_user_with_role(rolename)
      if object_role:
        program.add_person_with_role_name(user, object_role)

    audit = all_models.Audit.query.get(audit_id)
    self.api.set_user(user)
    audit_json = {
        "archived": not start_state
    }
    response = self.api.put(audit, audit_json)
    assert response.status_code == status, \
        "{} put returned {} instead of {}".format(
            rolename, response.status, status)
    if status != 200:
      # if editing is allowed check if edit was correctly saved
      return

    assert response.json["audit"].get("archived", None) is not start_state, \
        "Audit has not been {}d correctly {}".format(
        end_state, response.json["audit"])


@ddt
class TestArchivedAudit(TestAuditArchivingBase):
  """Tests Archived Audits

  Tests the following cases:

  1. Once archived the audit cannot be edited by anyone
  2. Once archived the objects with the audit context cannot be edited
     by anyone
  3. Once archived no new objects can be created in the audit context
  4. Once archived no mappings can be created in the audit context
  """

  @data(
      ('Administrator', '', 200, False),
      ('Editor', '', 200, False),
      ('Reader', '', 403, False),
      ('Creator', '', 403, False),
      ('Creator', 'Program Managers', 200, False),
      ('Creator', 'Program Editors', 200, False),
      ('Creator', 'Program Readers', 403, False),
      ('Administrator', '', 403, True),
      ('Editor', '', 403, True),
      ('Reader', '', 403, True),
      ('Creator', '', 403, True),
      ('Creator', 'Program Managers', 403, True),
      ('Creator', 'Program Editors', 403, True),
      ('Creator', 'Program Readers', 403, True)
  )
  @unpack
  def test_audit_editing(self, rolename, object_role, status, archived):
    """Test if {0}-{1} can edit an audit with archived {3}: expected {2}"""
    with factories.single_commit():
      audit = factories.AuditFactory(archived=archived)
      audit_id = audit.id
      program = audit.program
      factories.RelationshipFactory(source=program, destination=audit)
      user = self.create_user_with_role(rolename)
      if object_role:
        program.add_person_with_role_name(user, object_role)
    audit = all_models.Audit.query.get(audit_id)
    self.api.set_user(user)
    audit_json = {
        "description": "New"
    }
    response = self.api.put(audit, audit_json)
    assert response.status_code == status, \
        "{} put returned {} instead of {} for archived is {}".format(
            rolename, response.status, status, archived)
    if status != 200:
      # if editing is allowed check if edit was correctly saved
      return

    assert response.json["audit"].get("description", None) == "New", \
        "Audit has not been updated correctly {}".format(
        response.json["audit"])

  @data(
      ('Administrator', '', 200, False, 'Issue'),
      ('Editor', '', 200, False, 'Issue'),
      ('Reader', '', 403, False, 'Issue'),
      ('Creator', '', 403, False, 'Issue'),
      ('Creator', 'Program Managers', 200, False, 'Issue'),
      ('Creator', 'Program Editors', 200, False, 'Issue'),
      ('Creator', 'Program Readers', 403, False, 'Issue'),
      ('Administrator', '', 200, False, 'Assessment'),
      ('Editor', '', 200, False, 'Assessment'),
      ('Reader', '', 403, False, 'Assessment'),
      ('Creator', '', 403, False, 'Assessment'),
      ('Creator', 'Program Managers', 200, False, 'Assessment'),
      ('Creator', 'Program Editors', 200, False, 'Assessment'),
      ('Creator', 'Program Readers', 403, False, 'Assessment'),
      ('Administrator', '', 200, False, 'AssessmentTemplate'),
      ('Editor', '', 200, False, 'AssessmentTemplate'),
      ('Reader', '', 403, False, 'AssessmentTemplate'),
      ('Creator', '', 403, False, 'AssessmentTemplate'),
      ('Creator', 'Program Managers', 200, False, 'AssessmentTemplate'),
      ('Creator', 'Program Editors', 200, False, 'AssessmentTemplate'),
      ('Creator', 'Program Readers', 403, False, 'AssessmentTemplate'),
      ('Administrator', '', 200, True, 'Issue'),
      ('Editor', '', 200, True, 'Issue'),
      ('Reader', '', 403, True, 'Issue'),
      ('Creator', '', 403, True, 'Issue'),
      ('Creator', 'Program Managers', 200, True, 'Issue'),
      ('Creator', 'Program Editors', 200, True, 'Issue'),
      ('Creator', 'Program Readers', 403, True, 'Issue'),
      ('Administrator', '', 403, True, 'Assessment'),
      ('Editor', '', 403, True, 'Assessment'),
      ('Reader', '', 403, True, 'Assessment'),
      ('Creator', '', 403, True, 'Assessment'),
      ('Creator', 'Program Managers', 403, True, 'Assessment'),
      ('Creator', 'Program Editors', 403, True, 'Assessment'),
      ('Creator', 'Program Readers', 403, True, 'Assessment'),
      ('Administrator', '', 403, True, 'AssessmentTemplate'),
      ('Editor', '', 403, True, 'AssessmentTemplate'),
      ('Reader', '', 403, True, 'AssessmentTemplate'),
      ('Creator', '', 403, True, 'AssessmentTemplate'),
      ('Creator', 'Program Managers', 403, True, 'AssessmentTemplate'),
      ('Creator', 'Program Editors', 403, True, 'AssessmentTemplate'),
      ('Creator', 'Program Readers', 403, True, 'AssessmentTemplate'),
  )
  @unpack
  def test_audit_context_editing(self, rolename, object_role,
                                 status, archived, objects):
    # pylint: disable=too-many-arguments
    """Test if {0}-{1} can edit objects in the audit context:{2} -{4}"""
    with factories.single_commit():
      audit = factories.AuditFactory(archived=archived)
      program = audit.program
      factories.RelationshipFactory(source=program, destination=audit)
      user = self.create_user_with_role(rolename)
      if object_role:
        program.add_person_with_role_name(user, object_role)
      if objects == "Assessment":
        local_model = factories.AssessmentFactory(audit=audit)
      elif objects == "AssessmentTemplate":
        local_model = factories.AssessmentTemplateFactory(
            context=audit.context)
      else:
        local_model = factories.IssueFactory()

      factories.RelationshipFactory(source=audit, destination=local_model)
    local_model = db.session.query(get_model(objects)).filter().one()
    self.api.set_user(user)
    title = factories.random_str().strip().encode('utf-8')
    json = {
        "title": title,
    }
    if objects == "issue":
      json["due_date"] = "10/10/2019"
    response = self.api.put(local_model, json)
    self.assertStatus(
        response, status,
        "{} put returned {} instead of {} for {}".format(
            rolename, response.status, status, objects
        ),
    )

    if status != 200:
      # if editing is allowed check if edit was correctly saved
      return
    table_singular = local_model._inflector.table_singular
    self.assertEqual(
        response.json[table_singular].get("title", None), title,
        "{} has not been updated correctly {} != {}".format(
            objects, response.json[table_singular]['title'], title,
        ),
    )

  @data(
      ('Administrator', '', 200, False),
      ('Editor', '', 200, False),
      ('Reader', '', 403, False),
      ('Creator', '', 403, False),
      ('Creator', 'Program Managers', 200, False),
      ('Creator', 'Program Editors', 200, False),
      ('Creator', 'Program Readers', 403, False),
      ('Administrator', '', 403, True),
      ('Editor', '', 403, True),
      ('Reader', '', 403, True),
      ('Creator', '', 403, True),
      ('Creator', 'Program Managers', 403, True),
      ('Creator', 'Program Editors', 403, True),
      ('Creator', 'Program Readers', 403, True)
  )
  @unpack
  def test_audit_snapshot_editing(self, rolename, object_role,
                                  status, archived):
    """Test if {0}-{1} can edit objects in the audit context: {1}-snapshot"""
    with factories.single_commit():
      audit = factories.AuditFactory(archived=archived)
      program = audit.program
      factories.RelationshipFactory(source=program, destination=audit)
      user = self.create_user_with_role(rolename)
      if object_role:
        program.add_person_with_role_name(user, object_role)

      objective = factories.ObjectiveFactory(title="objective")
      factories.RelationshipFactory(source=program, destination=objective)

      revision = all_models.Revision.query.filter(
          all_models.Revision.resource_type == 'Objective').first()
      rev_id = revision.id

      # Create snapshot objects:
      snapshot = factories.SnapshotFactory(
          child_id=revision.resource_id,
          child_type=revision.resource_type,
          parent=audit,
          revision=revision,
          context=audit.context,
      )
      snapshot_id = snapshot.id
      factories.RelationshipFactory(
          source=audit,
          destination=snapshot,
      )

      # Updating Objective and creating a new Revision.
      objective.status = "Active"
      factories.RevisionFactory(
          obj=objective,
          action="modified",
          modified_by_id=user.id,
          content=objective.log_json(),
      )

    self.api.set_user(user)
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    response = self.api.put(
        snapshot,
        {
            "update_revision": "latest",
        },
    )

    assert response.status_code == status, \
        "{} put returned {} instead of {} for {}".format(
            rolename, response.status, status, 'snapshot')
    if status != 200:
      # if editing is allowed check if edit was correctly saved
      return
    assert response.json['snapshot'].get("revision_id", None) > rev_id, \
        "snapshot has not been updated to the latest revision {}".format(
        response.json['snapshot'])


@ddt
class TestArchivedAuditObjectCreation(TestCase):
  """Test creation permissions in audit"""

  def setUp(self):
    """Prepare data needed to run the tests"""
    TestCase.clear_data()
    self.api = Api()
    self.client.get("/login")
    self.archived_audit = factories.AuditFactory(
        archived=True
    )
    self.archived_audit.context = factories.ContextFactory(
        name="Audit context",
        related_object=self.archived_audit,
    )
    self.audit = factories.AuditFactory()
    self.assessment = factories.AssessmentFactory()

  @data(
      (all_models.Assessment, 403),
      (all_models.AssessmentTemplate, 403),
      (all_models.Issue, 201),
      (all_models.Relationship, 403),
  )
  @unpack
  def test_object_creation(self, obj, archived_status):
    """Test object creation in audit and archived audit"""
    audit = self.audit.id, self.audit.context.id
    archived_audit = self.archived_audit.id, self.archived_audit.context.id
    assessment_id = self.assessment.id
    response = self.api.post(
        obj, _create_obj_dict(obj, audit[0], audit[1], assessment_id))
    assert response.status_code == 201, \
        "201 not returned for {} on audit, received {} instead".format(
            obj._inflector.model_singular, response.status_code)

    response = self.api.post(obj, _create_obj_dict(
        obj, archived_audit[0], archived_audit[1], assessment_id))
    assert response.status_code == archived_status, \
        "403 not raised for {} on archived audit, received {} instead".format(
            obj._inflector.model_singular, response.status_code)
