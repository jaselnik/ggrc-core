# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Test views related to folder add/remove"""

import json

import ddt

from ggrc.models import all_models, mixins

from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@ddt.ddt
class TestFolderViews(TestCase):
  """Test for "unmap_objects" view."""

  NOT_PRESENT = object()
  PATH_ADD_FOLDER = '/api/add_folder'
  PATH_REMOVE_FOLDER = '/api/remove_folder'

  FOLDERABLE_MODEL_NAMES = list(m.__name__ for m in all_models.all_models
                                if issubclass(m, mixins.Folderable) and
                                m not in (all_models.Directive,
                                          all_models.ExternalDirective,
                                          all_models.SystemOrProcess))

  def setUp(self):
    """setUp"""
    super(TestFolderViews, self).setUp()
    self.api = api_helper.Api()

  def _get_request_data(self, obj_type=NOT_PRESENT, obj_id=NOT_PRESENT,
                        folder=NOT_PRESENT):
    """Prepare request dict"""
    dct = dict()

    if obj_type is not self.NOT_PRESENT:
      dct['object_type'] = obj_type

    if obj_id is not self.NOT_PRESENT:
      dct['object_id'] = obj_id

    if folder is not self.NOT_PRESENT:
      dct['folder'] = folder

    return json.dumps(dct)

  @ddt.data(PATH_ADD_FOLDER, PATH_REMOVE_FOLDER)
  def test_anon_user(self, url):
    """Test anon user for {0}"""

    with factories.single_commit():
      obj_id = factories.ProductFactory().id

    self.api.client.get("/logout")

    response = self.api.client.post(
        url, content_type="application/json",
        data=self._get_request_data('Product', obj_id, 'abc'))

    self.assert401(response)

  @ddt.data(PATH_ADD_FOLDER, PATH_REMOVE_FOLDER)
  def test_external_user(self, url):
    """Test external user access for {0}"""

    with factories.single_commit():
      obj_id = factories.ProductFactory().id

    self.api.login_as_external()

    response = self.api.client.post(
        url, content_type="application/json",
        data=self._get_request_data('Product', obj_id, 'abc'))

    self.assert403(response)

  @ddt.data(PATH_ADD_FOLDER, PATH_REMOVE_FOLDER)
  def test_not_found(self, url):
    """Test on non-existing object for {0}"""

    with factories.single_commit():
      obj_id = factories.ProductFactory().id

    self.api.login_as_normal()

    response = self.api.client.post(
        url, content_type="application/json",
        data=self._get_request_data('Product', obj_id + 1, 'abc'))

    self.assert404(response)

  @ddt.data(
      (PATH_ADD_FOLDER, "application/json", "", "a", 200),
      (PATH_REMOVE_FOLDER, "application/json", "a", "a", 200),
      (PATH_ADD_FOLDER, "plain/text", "", "a", 415),
      (PATH_REMOVE_FOLDER, "plain/text", "a", "a", 415),
  )
  @ddt.unpack
  def test_mimetype(self, url, mimetype, folder, new_folder, expected_code):
    """Test mimetype for '{0}' '{1}' '{2}' '{3}"""
    # pylint: disable=too-many-arguments

    with factories.single_commit():
      obj_id = factories.ProductFactory(folder=folder).id

    self.api.login_as_normal()

    response = self.api.client.post(
        url, content_type=mimetype,
        data=self._get_request_data('Product', obj_id, new_folder))

    self.assertStatus(response, expected_code)

  @ddt.data(
      (PATH_ADD_FOLDER, True, True, "a", 200),
      (PATH_REMOVE_FOLDER, True, True, "Z", 200),
      (PATH_ADD_FOLDER, False, True, "a", 400),
      (PATH_REMOVE_FOLDER, False, True, "a", 400),
      (PATH_ADD_FOLDER, True, False, "a", 400),
      (PATH_REMOVE_FOLDER, True, False, "a", 400),
  )
  @ddt.unpack
  def test_none(self, url, set_obj_id, set_obj_type, new_folder,
                expected_code):
    """Test None for '{0}' '{1}' '{2}' '{3}'"""
    # pylint: disable=too-many-arguments

    with factories.single_commit():
      obj_id = factories.ProductFactory(folder="Z").id

    self.api.login_as_normal()

    request_data = self._get_request_data(
        obj_type='Product' if set_obj_type else None,
        obj_id=obj_id if set_obj_id else None,
        folder=new_folder,
    )

    response = self.api.client.post(
        url, content_type="application/json",
        data=request_data)

    self.assertStatus(response, expected_code)

  @ddt.data(
      ("", True, True, "a", 200, 2),
      ("", False, True, "a", 400, 1),
      ("", True, False, "a", 400, 1),
      ("", True, True, NOT_PRESENT, 400, 1),
      ("", True, True, None, 400, 1),
      ("a", True, True, "a", 200, 1),
      ("a", True, True, "", 400, 1),
  )
  @ddt.unpack
  def test_add_folder(self, curr_folder, set_obj_type,
                      set_obj_id, new_folder, expected_code, expected_rev_cnt):
    """Test add_folder('{0}', '{1}', '{2}', '{3}')"""
    # pylint: disable=too-many-arguments

    obj_list = list()
    with factories.single_commit():
      for model_name in self.FOLDERABLE_MODEL_NAMES:
        obj_id = factories.get_model_factory(model_name)(folder=curr_folder).id
        obj_list.append((model_name, obj_id))

    self.api.login_as_normal()

    for obj_type, obj_id in obj_list:
      request_data = self._get_request_data(
          obj_type=obj_type if set_obj_type else self.NOT_PRESENT,
          obj_id=obj_id if set_obj_id else self.NOT_PRESENT,
          folder=new_folder,
      )

      response = self.api.client.post(
          self.PATH_ADD_FOLDER, content_type="application/json",
          data=request_data)

      self.assertStatus(response, expected_code)

      count = all_models.Revision.query.filter(
          all_models.Revision.resource_type == obj_type,
          all_models.Revision.resource_id == obj_id
      ).count()

      self.assertEqual(count, expected_rev_cnt)

  @ddt.data(
      ("a", True, True, "a", 200, 2),
      ("a", False, True, "a", 400, 1),
      ("a", True, False, "a", 400, 1),
      ("a", True, True, NOT_PRESENT, 400, 1),
      ("a", True, True, None, 400, 1),
      ("a", True, True, "", 400, 1),
      ("", True, True, "", 400, 1),
      ("", True, True, "a", 400, 1),
  )
  @ddt.unpack
  def test_remove_folder(self, curr_folder, set_obj_type,
                         set_obj_id, new_folder, expected_code,
                         expected_rev_cnt):
    """Test remove_folder('{0}', '{1}', '{2}', '{3}')"""
    # pylint: disable=too-many-arguments

    obj_list = list()
    with factories.single_commit():
      for model_name in self.FOLDERABLE_MODEL_NAMES:
        obj_id = factories.get_model_factory(model_name)(folder=curr_folder).id
        obj_list.append((model_name, obj_id))

    self.api.login_as_normal()

    for obj_type, obj_id in obj_list:
      request_data = self._get_request_data(
          obj_type=obj_type if set_obj_type else self.NOT_PRESENT,
          obj_id=obj_id if set_obj_id else self.NOT_PRESENT,
          folder=new_folder,
      )

      response = self.api.client.post(
          self.PATH_REMOVE_FOLDER, content_type="application/json",
          data=request_data)

      self.assertStatus(response, expected_code)

      count = all_models.Revision.query.filter(
          all_models.Revision.resource_type == obj_type,
          all_models.Revision.resource_id == obj_id
      ).count()

      self.assertEqual(count, expected_rev_cnt)

  @ddt.data(
      (PATH_ADD_FOLDER, 'Creator', 403),
      (PATH_REMOVE_FOLDER, 'Creator', 403),
      (PATH_ADD_FOLDER, 'Reader', 403),
      (PATH_REMOVE_FOLDER, 'Reader', 403),
      (PATH_ADD_FOLDER, 'Editor', 200),
      (PATH_REMOVE_FOLDER, 'Editor', 200),
  )
  @ddt.unpack
  def test_global_role(self, url, role_name, expected_status):
    """Test {0} for user with global role {1}"""

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name).one()

    with factories.single_commit():
      obj_id = factories.ProductFactory(folder="a").id
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=person)
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        url, content_type="application/json",
        data=self._get_request_data('Product', obj_id, folder="a"))

    self.assertStatus(response, expected_status)

  @ddt.data(
      (PATH_ADD_FOLDER, 'Custom_Reader', 1, 0, 0, 403),
      (PATH_REMOVE_FOLDER, 'Custom_Reader', 1, 0, 0, 403),
      (PATH_ADD_FOLDER, 'Custom_Editor', 1, 1, 1, 200),
      (PATH_REMOVE_FOLDER, 'Custom_Editor', 1, 1, 1, 200),
  )
  @ddt.unpack
  def test_custom_role(self, url, role_name, role_read, role_update,
                       role_delete, expected_status):
    """Test {0} for user with custom role {1}"""
    # pylint: disable=too-many-arguments

    role_creator = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    factories.AccessControlRoleFactory(
        name=role_name, object_type="Product",
        read=role_read, update=role_update, delete=role_delete
    )

    with factories.single_commit():
      obj = factories.ProductFactory(folder="a")
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_creator, person=person)
      factories.AccessControlPersonFactory(
          ac_list=obj.acr_name_acl_map[role_name],
          person=person,
      )
      obj_id = obj.id
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        url, content_type="application/json",
        data=self._get_request_data('Product', obj_id, folder="a"))

    self.assertStatus(response, expected_status)
