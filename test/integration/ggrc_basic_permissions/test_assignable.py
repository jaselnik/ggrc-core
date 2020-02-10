# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Test Assignable RBAC
"""

from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import Generator
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


class TestReader(TestCase):
  """Test Assignable RBAC"""

  def setUp(self):
    super(TestReader, self).setUp()
    self.audit_id = factories.AuditFactory().id
    self.generator = Generator()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.init_users()
    self.init_assignable()

  def init_users(self):
    """ Init users needed by the test cases """
    users = [("creator", "Creator"), ("reader", "Reader"),
             ("editor", "Editor"), ("admin", "Administrator")]
    self.users = {}
    for (name, role) in users:
      _, user = self.object_generator.generate_person(
          data={"name": name}, user_role=role)
      self.users[name] = user

  def init_assignable(self):
    """Creates the assignable object used by all the tests"""
    self.api.set_user(self.users["editor"])
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "Assessment",
            "context": None,
            "audit": {
                "id": self.audit_id,
                "type": "Audit"
            }
        }
    })
    obj_id = response.json.get("assessment").get("id")
    self.assertEqual(response.status_code, 201, "Error setting up Assessment")
    self.obj_json = response.json
    self.obj = all_models.Assessment.query.get(obj_id)

  def _add_creator(self, asmnt, user):
    """Helper method for creating assignees on an object"""
    acr = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Assessment",
        all_models.AccessControlRole.name == "Creators",
    ).first()
    return self.api.put(asmnt, {
        "access_control_list": [acl_helper.get_acl_json(acr.id, user.id)]
    })

  def test_basic_with_no_assignee(self):
    """Editor creates an Assessment, but doesn't assign Reader/Creator as
       assignee. Reader should have Read access, Creator should have no access
    """

    # Reader should have read access, but shouldn't be allowed to edit or
    # create another assingee
    self.api.set_user(self.users["reader"])
    response = self.api.get(all_models.Assessment, self.obj.id)
    self.assertEqual(response.status_code, 200)
    response = self.api.put(self.obj, self.obj_json)
    self.assertEqual(response.status_code, 403)
    response = self._add_creator(self.obj, self.users["reader"])
    self.assertEqual(response.status_code, 403)

    # Creator should have no access. We skip the put request because we can't
    # get the object etag.
    self.api.set_user(self.users["creator"])
    response = self.api.get(all_models.Assessment, self.obj.id)
    self.assertEqual(response.status_code, 403)
    response = self._add_creator(self.obj, self.users["reader"])
    self.assertEqual(response.status_code, 403)

  def test_basic_with_assignee(self):
    """Test if Reader/Creator have CRUD access once they become assignees"""

    # Admin adds reader as an assignee
    self.api.set_user(self.users["admin"])
    response = self._add_creator(self.obj, self.users["reader"])
    self.assertEqual(response.status_code, 200)

    # Reader is now allowed to update the object
    self.api.set_user(self.users["reader"])
    response = self.api.get(all_models.Assessment, self.obj.id)
    self.assertEqual(response.status_code, 200)
    response = self.api.put(self.obj, response.json)
    self.assertEqual(response.status_code, 200)

    # Reader adds creator as an assignee
    response = self._add_creator(self.obj, self.users["creator"])
    self.assertEqual(response.status_code, 200)

    # Creator now has CRUD access
    self.api.set_user(self.users["creator"])
    response = self.api.get(all_models.Assessment, self.obj.id)
    self.assertEqual(response.status_code, 200)
    response = self.api.put(self.obj, response.json)

    # Creator should even be allowed to add new assignees
    response = self._add_creator(self.obj, self.users["admin"])
    self.assertEqual(response.status_code, 200)

  def test_read_of_mapped_objects(self):
    """Test if assignees get Read access on all mapped objects"""

    # Editor creates a System object and maps it to the assignable object
    self.api.set_user(self.users["editor"])
    response = self.api.post(all_models.Issue, {
        "issue": {
            "title": "System",
            "context": None,
            "due_date": "2020-2-12",
        }
    })
    issue_id = response.json.get("issue").get("id")
    system = all_models.Issue.query.get(issue_id)
    self.api.post(all_models.Relationship, {
        "relationship": {"source": {
            "id": self.obj.id,
            "type": "Assessment"
        }, "destination": {
            "id": issue_id,
            "type": "Issue"
        }, "context": None},
    })

    # Since creator is not an assignee she should not have access to any of the
    # two objects
    self.api.set_user(self.users["creator"])
    response = self.api.get(all_models.Assessment, self.obj.id)
    self.assertEqual(response.status_code, 403)
    response = self.api.get(all_models.Issue, issue_id)
    self.assertEqual(response.status_code, 403)

    # Editor adds creator as an assignee
    self.api.set_user(self.users["editor"])
    response = self._add_creator(self.obj, self.users["creator"])
    self.assertEqual(response.status_code, 200)

    # Creator should now have read access on the mapped object
    self.api.set_user(self.users["creator"])
    response = self.api.get(all_models.Issue, issue_id)
    self.assertEqual(response.status_code, 403)

    # But he should still not be allowed to update
    response = self.api.put(system, response.json)
    self.assertEqual(response.status_code, 403)
