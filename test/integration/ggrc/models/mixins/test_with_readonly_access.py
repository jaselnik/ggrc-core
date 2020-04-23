# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for WithReadOnlyAccess mixin"""

# pylint: disable=invalid-name,too-many-arguments,too-many-lines

import json

import ddt

from ggrc import views
from ggrc.models import get_model, all_models, mixins
from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc import factories
from integration.ggrc import query_helper
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


_NOT_SPECIFIED = '<NOT_SPECIFIED>'


@ddt.ddt
class TestWithReadOnlyAccessAPI(TestCase, query_helper.WithQueryApi):
  """Test WithReadOnlyAccess mixin"""

  def setUp(self):
    super(TestWithReadOnlyAccessAPI, self).setUp()
    self.object_generator = ObjectGenerator()
    self.object_generator.api.login_as_normal()

  @ddt.data(
      ('System', True),
      ('System', False),
      ('System', None),
      ('System', _NOT_SPECIFIED),
      ('System', "qwert"),
  )
  @ddt.unpack
  def test_readonly_ignored_on_post(self, obj_type, readonly):
    """Test flag readonly ignored on object {0} POST for body readonly={1}"""

    dct = dict()
    if readonly is not _NOT_SPECIFIED:
      dct['readonly'] = readonly
    resp, obj = self.object_generator.generate_object(
        get_model(obj_type),
        dct,
    )

    self.assertStatus(resp, 403)

  @ddt.data(
      ('System', True, True),
      ('System', False, False),
      ('System', None, False),
      ('System', _NOT_SPECIFIED, False),
  )
  @ddt.unpack
  def test_readonly_set_on_post_as_external(self, obj_type, readonly, result):
    """Test flag readonly on {0} POST for body readonly={1} as external user"""

    dct = dict()
    if readonly is not _NOT_SPECIFIED:
      dct['readonly'] = readonly

    with self.object_generator.api.as_external():
      resp, obj = self.object_generator.generate_object(
          get_model(obj_type),
          dct,
      )
      obj_id = obj.id

    self.assertStatus(resp, 201)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.readonly, result)

  @ddt.data(
      ('System', False, False, 403),
      ('System', False, True, 403),
      ('System', False, None, 403),
      ('System', False, _NOT_SPECIFIED, 403),
      ('System', False, "qwerty", 403),
      ('System', True, False, 403),
      ('System', True, True, 403),
      ('System', True, None, 403),
      ('System', True, _NOT_SPECIFIED, 403),
      ('System', True, "qwerty", 403),
  )
  @ddt.unpack
  def test_put(self, obj_type, current, new, exp_code):
    """Test {0} PUT readonly={2} for current readonly={1}"""

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=current)
      obj_id = obj.id

    data = {'title': 'b'}
    if new is not _NOT_SPECIFIED:
      data['readonly'] = new

    resp = self.object_generator.api.put(obj, data)

    self.assertStatus(resp, exp_code)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.readonly, current)

  @ddt.data(
      ('System', False, False, 200, False),
      ('System', False, True, 200, True),
      ('System', False, None, 200, False),
      ('System', False, _NOT_SPECIFIED, 200, False),
      ('System', True, False, 200, False),
      ('System', True, True, 200, True),
      ('System', True, None, 200, True),
      ('System', True, _NOT_SPECIFIED, 200, True),
  )
  @ddt.unpack
  def test_put_as_external(self, obj_type, current, new, exp_code,
                           exp_readonly):
    """Test {0} PUT readonly={2} for current readonly={1} for external user"""

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=current)
      obj_id = obj.id

    data = {'title': 'b'}
    if new is not _NOT_SPECIFIED:
      data['readonly'] = new

    with self.object_generator.api.as_external():
      obj = get_model(obj_type).query.get(obj_id)
      resp = self.object_generator.api.put(obj, data)

    self.assertStatus(resp, exp_code)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.readonly, exp_readonly)

  @ddt.data('System')
  def test_403_if_put_readonly_without_perms(self, obj_type):
    """Test {0} with readonly=True PUT returns 401 instead of 405

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """
    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    factory = factories.get_model_factory(obj_type)

    with factories.single_commit():
      # create Global Creator
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      # Create object
      obj = factory(title='a', readonly=True)
      obj_id = obj.id

    self.object_generator.api.set_user(all_models.Person.query.get(person_id))
    obj = get_model(obj_type).query.get(obj_id)
    resp = self.object_generator.api.put(obj, {'title': 'b'})

    self.assert403(resp)

  @ddt.data('System')
  def test_403_if_delete_readonly_without_perms(self, obj_type):
    """Test {0} with readonly=True DELETE returns 401

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    factory = factories.get_model_factory(obj_type)

    with factories.single_commit():
      # create Global Creator
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      # Create object
      obj = factory(title='a', readonly=True)
      obj_id = obj.id

    self.object_generator.api.set_user(all_models.Person.query.get(person_id))
    obj = get_model(obj_type).query.get(obj_id)
    resp = self.object_generator.api.delete(obj)

    self.assert403(resp)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertIsNotNone(obj)

  @ddt.data(
      ('System', False, 'Document', True, 201),
      ('System', False, 'Document', False, 201),
      ('System', True, 'Document', True, 405),
      ('System', True, 'Document', False, 405),
      ('System', False, 'Comment', True, 201),
      ('System', False, 'Comment', False, 201),
      ('System', True, 'Comment', True, 201),
      ('System', True, 'Comment', False, 201),
  )
  @ddt.unpack
  def test_relationship_post(self, obj_type, readonly, rel_obj_type, swap,
                             expected_code):
    """Test PUT relationship {0}.readonly={1}, related object type {2}"""

    factory = factories.get_model_factory(obj_type)
    rel_factory = factories.get_model_factory(rel_obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=readonly)
      rel_obj = rel_factory()

    if swap:
      source, destination = rel_obj, obj
    else:
      source, destination = obj, rel_obj

    resp, _ = self.object_generator.generate_relationship(
        source=source, destination=destination
    )

    self.assertStatus(resp, expected_code)

  @ddt.data(
      ('System', False, 'Document', True, 200),
      ('System', False, 'Document', False, 200),
      ('System', True, 'Document', True, 405),
      ('System', True, 'Document', False, 405),
      ('System', False, 'Comment', True, 200),
      ('System', False, 'Comment', False, 200),
      ('System', True, 'Comment', True, 200),
      ('System', True, 'Comment', False, 200),
  )
  @ddt.unpack
  def test_relationship_delete(self, obj_type, readonly, rel_obj_type, swap,
                               expected_code):
    """Test DELETE relationship {0}.readonly={1}, related object type {2}"""

    factory = factories.get_model_factory(obj_type)
    rel_factory = factories.get_model_factory(rel_obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=readonly)
      rel_obj = rel_factory()

      if swap:
        source, destination = rel_obj, obj
      else:
        source, destination = obj, rel_obj

      robj = factories.RelationshipFactory(source=source,
                                           destination=destination)

    resp = self.object_generator.api.delete(robj)

    self.assertStatus(resp, expected_code)

  @ddt.data(
      ("yes", "readonly system"),
      ("no", "non readonly system"),
  )
  @ddt.unpack
  def test_readonly_searchable(self, test_value, expected_title):
    """Test filtration by readonly attribute"""
    with factories.single_commit():
      factories.SystemFactory(title="readonly system", readonly=True)
      factories.SystemFactory(title="non readonly system")

    self.client.get("/login")
    actual_systems = self.simple_query(
        "System",
        expression=["readonly", "=", test_value]
    )
    self.assertEqual(
        [s.get("title") for s in actual_systems],
        [expected_title]
    )


@ddt.ddt
class TestWithReadOnlyAccessFolder(TestCase):
  """Test for "unmap_objects" view."""

  NOT_PRESENT = object()
  PATH_ADD_FOLDER = '/api/add_folder'
  PATH_REMOVE_FOLDER = '/api/remove_folder'

  FOLDERABLE_MODEL_NAMES = list(m.__name__ for m in all_models.all_models
                                if issubclass(m, mixins.Folderable) and
                                m not in (all_models.Directive,))

  def setUp(self):
    """setUp"""
    super(TestWithReadOnlyAccessFolder, self).setUp()
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

  @ddt.data(
      ('System', 'Creator', 403),
      ('System', 'Reader', 403),
      ('System', 'Editor', 405),
      ('System', 'Administrator', 405),
  )
  @ddt.unpack
  def test_readonly_add_folder_with_global_role(self, obj_type, role_name,
                                                expected_status):
    """Test add_folder read-only {0} by user with global role {1}"""

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name).one()

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj_id = factory(folder="a", readonly=True).id
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=person)
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        self.PATH_ADD_FOLDER, content_type="application/json",
        data=self._get_request_data(obj_type, obj_id, folder="b"))

    self.assertStatus(response, expected_status)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.folder, "a")

  @ddt.data(
      ('System', 'Creator', 403),
      ('System', 'Reader', 403),
      ('System', 'Editor', 405),
      ('System', 'Administrator', 405),
  )
  @ddt.unpack
  def test_readonly_remove_folder_with_global_role(self, obj_type, role_name,
                                                   expected_status):
    """Test remove_folder read-only {0} by user with global role {1}"""

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name).one()

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj_id = factory(folder="a", readonly=True).id
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=person)
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        self.PATH_REMOVE_FOLDER, content_type="application/json",
        data=self._get_request_data(obj_type, obj_id, folder="a"))

    self.assertStatus(response, expected_status)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.folder, "a")


@ddt.ddt
class TestWithReadOnlyAccessExport(TestCase):
  """Test for exporting objects with read-only access."""

  def setUp(self):
    """setUp"""
    super(TestWithReadOnlyAccessExport, self).setUp()
    self.api = api_helper.Api()
    self.client.get("/login")

  def test_export_system(self):
    """Test exporting of System objects."""
    factories.SystemFactory()

    search_request = [{
        "object_name": "System",
        "fields": "all",
        "filters": {
            "expression": {}
        }
    }]

    response = self.export_parsed_csv(search_request)
    self.assertEqual(len(response["System"]), 1)
    self.assertNotIn("Read-only", response["System"][0])
    self.assertNotIn("readonly", response["System"][0])

  def test_export_system_template(self):
    """Test exporting of System import template."""
    response = self.export_csv_template([{"object_name": "System"}])
    self.assertNotIn("Read-only", response.data)
    self.assertNotIn("readonly", response.data)

  def test_export_system_attributes(self):
    """Test that Read-only flag is not show on export page."""
    export_attributes = views.get_all_attributes_json()
    self.assertNotIn("Read-only", export_attributes)
    self.assertNotIn("readonly", export_attributes)
    self.assertNotIn("hidden", export_attributes)
