# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control Role"""
from collections import OrderedDict, defaultdict

import ddt

from ggrc.access_control.role import AccessControlRole
from ggrc.converters import errors
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models.factories import random_str
from integration.ggrc.models import factories
from integration.ggrc.generator import ObjectGenerator

ROLE_NAME = "ACR for mandatory test"
MANDATORY_ROLE_RESPONSE = {
    "Program": {"row_warnings": {errors.OWNER_MISSING.format(
        line=3, column_name=ROLE_NAME)}}}
NON_MANDATORY_ROLE_RESPONSE = {}


@ddt.ddt
class TestAccessControlRole(TestCase):
  """TestAccessControlRole"""

  def setUp(self):
    self.clear_data()
    super(TestAccessControlRole, self).setUp()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.people = {}
    for name in ["Creator", "Reader", "Editor"]:
      _, user = self.object_generator.generate_person(
          data={"name": name}, user_role=name)
      self.people[name] = user

  def _post_role(self, name=None, object_type="Control"):
    """Helper function for POSTing roles"""
    if name is None:
      name = random_str(prefix="Access Control Role - ")
    return self.api.post(AccessControlRole, {
        "access_control_role": {
            "name": name,
            "object_type": object_type,
            "context": None,
            "read": True
        },
    })

  def test_create_after_objects(self):
    """Test eager creation of ACLs on existing objects with new ACR."""
    program_id = factories.ProgramFactory().id
    role_name = "New Custom Role"
    self._post_role(name=role_name, object_type="Program")
    program = all_models.Program.query.get(program_id)
    self.assertIn(role_name, program.acr_name_acl_map.keys())
    self.assertIsNotNone(program.acr_name_acl_map[role_name])

  def test_create(self):
    """Test Access Control Role creation"""
    response = self._post_role(object_type="Program")
    assert response.status_code == 201, \
        "Failed to create a new access control role, response was {}".format(
            response.status)

    id_ = response.json['access_control_role']['id']
    role = AccessControlRole.query.filter(AccessControlRole.id == id_).first()
    assert role.read == 1, \
        "Read permission not correctly saved {}".format(role.read)
    assert role.update == 1, \
        "Update permission not correctly saved {}".format(role.update)
    assert role.delete == 1, \
        "Update permission not correctly saved {}".format(role.delete)

  @ddt.data(
      {"mandatory": True, "exp_response": MANDATORY_ROLE_RESPONSE},
      {"mandatory": False, "exp_response": NON_MANDATORY_ROLE_RESPONSE},
  )
  @ddt.unpack
  def test_mandatory_delete(self, mandatory, exp_response):
    """Test set empty field via import if acr mandatory is {mandatory}"""
    role = factories.AccessControlRoleFactory(
        name=ROLE_NAME,
        object_type="Program",
        mandatory=mandatory,
    )
    with factories.single_commit():
      user = factories.PersonFactory()
      program = factories.ProgramFactory()
      role_id = role.id
      factories.AccessControlPersonFactory(
          ac_list=program.acr_name_acl_map[ROLE_NAME],
          person=user,
      )
    response = self.import_data(OrderedDict([
        ("object_type", "Program"),
        ("Code*", program.slug),
        (ROLE_NAME, "--"),
    ]))
    self._check_csv_response(response, exp_response)
    db_data = defaultdict(set)
    program = all_models.Program.query.get(program.id)
    for person, acl in program.access_control_list:
      db_data[acl.ac_role_id].add(person.id)
    if mandatory:
      cur_user = all_models.Person.query.filter_by(
          email="user@example.com").first()
      self.assertEqual(set([cur_user.id]), db_data[role_id])
    else:
      self.assertFalse(db_data[role_id])

  def test_only_admin_can_post(self):
    """Only admin users should be able to POST access control roles"""
    for name in ("Creator", "Reader", "Editor"):
      person = self.people.get(name)
      self.api.set_user(person)
      response = self._post_role()
      assert response.status_code == 403, \
          "Non admins should get forbidden error when POSTing role. {}".format(
              response.status)

  @ddt.data(
      ("name", "New ACR"),
      ("read", False),
      ("mandatory", False),
      ("non_editable", False),
  )
  @ddt.unpack
  def test_modify_non_editable_role(self, field_name, field_value):
    """Test if user can modify non-editable role"""
    # Primary Contacts role of Control is non-editable
    ac_role = AccessControlRole.query.filter_by(
        object_type="Control",
        name="Control Operators",
    ).first()

    response = self.api.put(ac_role, {field_name: field_value})
    assert response.status_code == 403, \
        "Forbidden error should be thrown when non-editable " \
        "role {} updated.".format(ac_role.name)

  def test_delete_non_editable_role(self):
    """Test if user can delete non-editable role"""
    # Primary Contacts role of Control is non-editable
    ac_role = AccessControlRole.query.filter_by(
        object_type="Control",
        name="Control Operators",
    ).first()

    response = self.api.delete(ac_role)
    assert response.status_code == 403, \
        "Forbidden error should be thrown when non-editable " \
        "role {} deleted.".format(ac_role.name)

  @ddt.data("Control")
  def test_create_from_ggrcq(self, object_type):
    """Test that create action only for GGRCQ."""
    with self.api.as_external():
      response = self._post_role(object_type=object_type)
      self.assertEqual(response.status_code, 201)

  @ddt.data("Control")
  def test_modify_from_ggrcq(self, object_type):
    """Test that modify action only for GGRCQ."""
    with factories.single_commit():
      acr_id = factories.AccessControlRoleFactory(object_type=object_type).id

    with self.api.as_external():
      acr = all_models.AccessControlRole.query.get(acr_id)
      response = self.api.put(acr, {"name": "new acr"})
      self.assertEqual(response.status_code, 200)

  @ddt.data("Control")
  def test_delete_from_ggrcq(self, object_type):
    """Test that modify action only for GGRCQ."""
    with factories.single_commit():
      acr_id = factories.AccessControlRoleFactory(object_type=object_type).id

    with self.api.as_external():
      acr = all_models.AccessControlRole.query.get(acr_id)
      response = self.api.delete(acr)
      self.assertEqual(response.status_code, 200)

  @ddt.data(
      {"name": "Test 1", "update": False, "read": False, "delete": True},
      {"name": "Test 2", "update": True, "read": False, "delete": False},
      {"name": "Test 3", "update": True, "read": False, "delete": True},
  )
  @ddt.unpack
  def test_create_with_wrong_options(self, name, update, read, delete):
    """ Test if user create ACR with wrong options."""
    options = [{
        'access_control_role':
            {
                'modal_title': 'Add Custom Role to type Regulation',
                'object_type': 'Regulation',
                'parent_type': 'Regulation',
                'context': {'id': None},
                'delete': delete,
                'update': update,
                'read': read,
                'name': name
            }
    }]
    response = self.api.post(AccessControlRole, options)
    self.assert400(response)
