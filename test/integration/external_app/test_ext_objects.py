# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for external objects models."""

import collections
from itertools import product

import ddt

from ggrc.converters import errors
from ggrc.models import all_models
from ggrc.models import comment
from ggrc.models.mixins import synchronizable
from integration.external_app import external_api_helper
from integration.ggrc import api_helper
from integration.ggrc import factories
from integration import ggrc as integration_ggrc

# pylint: disable=invalid-name


CAD = all_models.CustomAttributeDefinition
CR = all_models.AccessControlRole


@ddt.ddt
class TestBaseExternalObjects(integration_ggrc.TestCase):
  """Base class for testing externalization for all objects."""

  OBJECTS = [
      all_models.Contract,
      all_models.Objective,
      all_models.Policy,
      all_models.Requirement,
      all_models.Threat,
  ] + all_models.get_scope_models()

  @staticmethod
  def _make_test_models_payload(model):
    """
        Prepare payload for {0.__name__} model.
    """
    data = {
        model._inflector.table_singular: {
            "title": "new_{}".format(model.__name__),
            "description": "lorem ipsum",
            "notes": "Tests notes for scoped",
            "context": None,
            "external_id": 11111,
            "external_slug": "11111",
            "created_at": "2019-01-11",
        }}
    return data

  @staticmethod
  def _make_test_object_review_payload(obj, reviewer):
    """
        Prepare review payload for `object` with given `reviewer`.
    """
    review_model = all_models.Review
    reviewer_role_id = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.name == "Reviewers",
        all_models.AccessControlRole.object_type == "Review",
    ).one().id

    data = {
        "review": {
            "reviewable": {
                "type": obj.type,
                "id": obj.id,
            },
            "access_control_list": [{
                "ac_role_id": reviewer_role_id,
                "person": {
                    "type": reviewer.type,
                    "id": reviewer.id,
                },
            }],
            "context": None,
            "status": review_model.STATES.UNREVIEWED,
            "notification_type": review_model.NotificationTypes.EMAIL_TYPE,
            "email_message": "",
        }}
    return data

  @staticmethod
  def _make_test_models_cad_payload(model):
    """
        Prepare payload for {0.__name__}'s CAD model.
    """
    data = {
        "custom_attribute_definition": {
            "title": "new_CAD_{}".format(model.__name__),
            "attribute_type": "Text",
            "definition_type": model._inflector.table_singular,
            "mandatory": False,
            "helptext": "GCA Text",
            "placeholder": "",
            "context": None,
        },
    }
    return data

  @staticmethod
  def _make_test_models_acr_payload(model):
    """
        Prepare payload for {0.__name__}'s ACR model.
    """
    data = {
        "access_control_role": {
            "name": "new_Custom_Role_{}".format(model.__name__),
            "object_type": model.__name__,
            "context": None,
        },
    }
    return data

  def _create_test_model_instance(self, model):
    """
        Create {0.__name__} instance for tests.
    """
    model_factory = factories.get_model_factory(model.__name__)
    model_singular = model._inflector.table_singular
    data = self._make_test_models_payload(model)[model_singular]
    model_inst = model_factory(**data)
    return model_inst

  def _validate_acl_counts(self, model, object_id, expected_count):
    """Checks ACL counts for certain object.

    Args:
      model (db.Model): An instance of model object.
      object_id (int): An integer value of object ID.
      expected_count (int): An integer value of expected ACL count.

    Raises:
      AssertionError: expected ACL count does not match actual one.
    """
    acrs = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == model.__name__,
        all_models.AccessControlRole.name.in_(
            ["Secondary Contacts", "Primary Contacts", "Admin"])
    ).all()
    acrs = [acr.id for acr in acrs]

    acl_count = all_models.AccessControlList.query.filter(
        all_models.AccessControlList.object_id == object_id,
        all_models.AccessControlList.object_type == model.__name__,
        all_models.AccessControlList.ac_role_id.in_(acrs)
    ).count()

    self.assertEquals(expected_count, acl_count)

  @ddt.data(*OBJECTS)
  def test_objects_have_external_attrs(self, model):
    """
        Test that '{0.__name__}' table has external_id/slug columns.
    """
    self.assertTrue(issubclass(model, synchronizable.Synchronizable))
    table_columns_data = model.__table__.columns._data  # noqa pylint: disable=protected-access

    self.assertIn('external_id', table_columns_data)
    self.assertIn('external_slug', table_columns_data)
    self.assertIn('created_by_id', table_columns_data)

  @ddt.data(*OBJECTS)
  def test_objects_are_ext_commentable(self, model):
    """Test that '{0.__name__}' model is ExternalCommentable."""
    self.assertTrue(issubclass(model, comment.ExternalCommentable))


@ddt.ddt
class TestExternalAppObjects(TestBaseExternalObjects):
  """Class for tests objects with external client."""

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestExternalAppObjects, self).setUp()
    self.api = external_api_helper.ExternalApiClient()

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_create_allowed(self, model):
    """
        Test POST method for {0.__name__} is allowed for external API.
    """
    data = self._make_test_models_payload(model)

    response = self.api.post(model, data=data)

    self.assert201(response)
    obj_count = model.query.count()
    self.assertEqual(1, obj_count)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_create_with_acl(self, model):
    """
        Test POST external {0.__name__} with ACL for external API.
    """
    data = self._make_test_models_payload(model)
    acl = {
        "access_control_list": {
            "Primary Contacts": [
                {"email": "test1@exp.com", "name": "Test 1"},
            ],
            "Secondary Contacts": [
                {"email": "test2@exp.com", "name": "Test 2"},
            ],
            "Admin": [
                {"email": "test3@exp.com", "name": "Test 3"},
            ]}
    }
    data.update(acl)

    response = self.api.post(model, data=data)

    self.assert201(response)
    object_id = response.json[model._inflector.table_singular]["id"]
    self._validate_acl_counts(model, object_id, expected_count=3)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_get_allowed(self, model):
    """
        Test GET method for {0.__name__} is allowed for external API.
    """
    ext_obj = self._create_test_model_instance(model)

    response = self.api.get(model, obj_id=ext_obj.id)

    self.assert200(response)
    self.assertEqual(response.json[model._inflector.table_singular]["title"],
                     "new_{}".format(model.__name__))

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_put_allowed(self, model):
    """
        Test PUT method for {0.__name__} is allowed for external API.
    """

    ext_obj = self._create_test_model_instance(model)
    data = {
        "title": "TEST_{}".format(model.__name__)
    }

    response = self.api.put(ext_obj, obj_id=ext_obj.id, data=data)

    self.assert200(response)
    ext_obj = model.query.get(ext_obj.id)
    self.assertEqual(ext_obj.title, data["title"])

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_put_with_acl(self, model):
    """
        Test PUT external {0.__name__} with ACL for external API.
    """
    ext_obj = self._create_test_model_instance(model)
    data = {
        "access_control_list": {
            "Primary Contacts": [
                {"email": "test1@exp.com", "name": "Test 1"},
            ],
            "Secondary Contacts": [
                {"email": "test2@exp.com", "name": "Test 2"},
            ],
            "Admin": [
                {"email": "test3@exp.com", "name": "Test 3"},
            ]}
    }

    response = self.api.put(ext_obj, obj_id=ext_obj.id, data=data)

    self.assert200(response)
    self._validate_acl_counts(model, ext_obj.id, expected_count=3)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_exernal_object_review_deprecated(self, model):
    """
        Test Review for {0.__name__} is deprecated for external API.
    """
    with factories.single_commit():
      ext_obj = self._create_test_model_instance(model)
      reviewer = factories.PersonFactory()

    data = self._make_test_object_review_payload(ext_obj, reviewer)
    expected_response = "Trying to create review for external model."

    response = self.api.post(all_models.Review, data=data)

    self.assert400(response)
    self.assertEqual(
        expected_response,
        response.json,
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_cad_create_allowed(self, model):
    """
        Test POST CAD for {0.__name__} is allowed for external API.
    """
    data = self._make_test_models_cad_payload(model)
    definition_type = model._inflector.table_singular
    cads_count_before = CAD.query.filter_by(
        definition_type=definition_type,
    ).count()

    response = self.api.post(CAD, data=data)

    self.assert201(response)
    self.assertEqual(
        cads_count_before + 1,
        CAD.query.filter_by(definition_type=definition_type).count(),
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_external_object_cad_update_allowed(self, model):
    """
        Test PUT CAD for {0.__name__} is allowed for external API.
    """
    definition_type = model._inflector.table_singular
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type=definition_type,
    )
    data = {
        "title": "NEW CAD TITLE",
    }

    response = self.api.put(cad, obj_id=cad.id, data=data)

    self.assert200(response)
    cad = CAD.query.get(cad.id)
    self.assertEqual(data["title"], cad.title)

  @ddt.data(*product(TestBaseExternalObjects.OBJECTS,
                     (all_models.Control, all_models.Risk)))
  @ddt.unpack
  def test_external_mapping(self, model_1, model_2):
    """
        Test map {0.__name__} and {1.__name__} from external service
    """
    with factories.single_commit():
      dest = factories.get_model_factory(model_1.__name__)()
      dest_id = dest.id
      source = factories.get_model_factory(model_2.__name__)()
      source_id = source.id
    data = {
        "relationship": {
            "source": {"id": source_id, "type": source.type},
            "destination": {"id": dest_id, "type": dest.type},
            "is_external": True
        }
    }
    response = self.api.post(all_models.Relationship, data=data)
    self.assert201(response)

    rels_count = all_models.Relationship.query.filter_by(
        source_type=source.type,
        source_id=source_id,
        destination_type=dest.type,
        destination_id=dest_id
    ).count()
    self.assertEqual(rels_count, 1)

  @ddt.data(*product(TestBaseExternalObjects.OBJECTS,
                     (all_models.Control, all_models.Risk)))
  @ddt.unpack
  def test_external_unmap(self, model_1, model_2):
    """
        Test unmap {0.__name__} and {1.__name__} from external service
    """
    with factories.single_commit():
      dest = factories.get_model_factory(model_1.__name__)()
      dest_id = dest.id
      source = factories.get_model_factory(model_2.__name__)()
      source_id = source.id
    data = {
        "relationship": {
            "source": {"id": source_id, "type": source.type},
            "destination": {"id": dest_id, "type": dest.type},
            "is_external": True
        }
    }
    response = self.api.post(all_models.Relationship, data=data)
    self.assert201(response)

    source = model_2.query.get(source_id)
    dest = model_1.query.get(dest_id)

    response = self.api.unmap(source, dest)
    self.assert200(response)

    rels_count = all_models.Relationship.query.count()
    self.assertEqual(rels_count, 0)


@ddt.ddt
class TestInternalAppObjects(TestBaseExternalObjects):
  """Class for tests objects with internal client"""

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestInternalAppObjects, self).setUp()
    self.api = api_helper.Api()

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_import_deprecated(self, model):
    """
        Test that import of {0.__name__} model is deprecated.
    """
    excepted_resp = {
        model._inflector.title_singular: {
            "row_errors": {
                errors.EXTERNAL_MODEL_IMPORT_RESTRICTION.format(
                    line=3,
                    external_model_name=model.__name__),
            },
        },
    }
    response = self.import_data(collections.OrderedDict([
        ("object_type", model.__name__),
        ("Code*", ""),
        ("Title", "Test title")
    ]))

    self._check_csv_response(response, excepted_resp)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_download_import_template(self, model):
    """
        Test that download import template of {0.__name__} is deprecated.
    """
    objects = [{
        "object_name": model.__name__,
    }]

    self.client.get("/login")
    response = self.export_csv_template(objects)

    self.assert403(response)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_export_allowed(self, model):
    """
        Test that export of {0.__name__} model is allowed for internal API.
    """
    ext_obj = self._create_test_model_instance(model)
    ext_obj_slug = ext_obj.slug

    self.client.get("/login")
    response = self.export_csv([{
        "object_name": ext_obj.type,
        "filters": {
            "expression": {
                "left": "id",
                "op": {"name": "="},
                "right": ext_obj.id,
            },
        },
    }])

    self.assert200(response)
    self.assertIn(ext_obj_slug, response.data)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_post_deprecated(self, model):
    """
        Test POST method for {0.__name__} is deprecated for internal API.
    """
    response = self.api.post(model, {"title": "new-title"})

    self.assert403(response)
    self.assertEqual(0, model.query.count())

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_put_deprecated(self, model):
    """
        Test PUT method for {0.__name__} is deprecated for internal API.
    """
    ext_obj = self._create_test_model_instance(model)
    response = self.api.put(ext_obj, {"title": "new-title"})

    self.assert403(response)
    self.assertEqual("new_{}".format(model.__name__),
                     model.query.first().title)

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_delete_deprecated(self, model):
    """
        Test DELETE method for {0.__name__} is deprecated for internal API.
    """
    ext_obj = self._create_test_model_instance(model)
    response = self.api.delete(ext_obj, id_=ext_obj.id)

    self.assert403(response)
    self.assertEqual(1, model.query.count())

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_get_allowed(self, model):
    """
        Test GET method for {0.__name__} is allowed for internal API.
    """
    ext_obj = self._create_test_model_instance(model)
    response = self.api.get(ext_obj, id_=ext_obj.id)

    self.assert200(response)
    self.assertEqual(response.json[model._inflector.table_singular]["title"],
                     "new_{}".format(model.__name__))

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_review_deprecated(self, model):
    """
        Test Review for {0.__name__} is deprecated for internal API.
    """
    with factories.single_commit():
      ext_obj = self._create_test_model_instance(model)
      reviewer = factories.PersonFactory()

    data = self._make_test_object_review_payload(ext_obj, reviewer)
    expected_response = "Trying to create review for external model."

    response = self.api.post(all_models.Review, data=data)
    self.assert400(response)
    self.assertEqual(
        expected_response,
        response.json,
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cad_create_deprecated(self, model):
    """
        Test POST CAD for {0.__name__} is deprecated for internal API.
    """
    data = self._make_test_models_cad_payload(model)
    definition_type = model._inflector.table_singular
    cads_count_before = CAD.query.filter_by(
        definition_type=definition_type,
    ).count()

    response = self.api.post(CAD, data=data)

    self.assert403(response)
    self.assertEqual(
        cads_count_before,
        CAD.query.filter_by(definition_type=definition_type).count(),
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cad_update_deprecated(self, model):
    """
        Test PUT CAD for {0.__name__} is deprecated for internal API.
    """
    definition_type = model._inflector.table_singular
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type=definition_type,
    )
    cad_initial_title = cad.title
    cad_id = cad.id

    response = self.api.put(cad, {"title": "NEW CAD TITLE"})

    self.assert403(response)
    self.assertEqual(
        cad_initial_title,
        CAD.query.get(cad_id).title,
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cad_delete_deprecated(self, model):
    """
        Test DELETE CAD for {0.__name__} is deprecated for internal API.
    """
    definition_type = model._inflector.table_singular
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type=definition_type,
    )
    cad_id = cad.id

    response = self.api.delete(cad, id_=cad.id)

    self.assert403(response)
    self.assertIsNotNone(
        CAD.query.filter_by(id=cad_id).first(),
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cr_create_deprecated(self, model):
    """
      Test POST Custom Role for {0.__name__} is deprecated for internal API.
    """
    data = self._make_test_models_acr_payload(model)
    object_type = model.__name__
    crs_count_before = CR.query.filter_by(
        object_type=object_type,
    ).count()

    response = self.api.post(CR, data=data)

    self.assert403(response)
    self.assertEqual(
        crs_count_before,
        CR.query.filter_by(object_type=object_type).count(),
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cr_update_deprecated(self, model):
    """
      Test PUT Custom Role for {0.__name__} is deprecated for internal API.
    """
    object_type = model.__name__
    cr = factories.AccessControlRoleFactory(
        object_type=object_type,
        non_editable=False,
    )
    cr_initial_name = cr.name
    cr_id = cr.id

    response = self.api.put(cr, {"name": "NEW CR TITLE"})

    self.assert403(response)
    self.assertEqual(
        cr_initial_name,
        CR.query.get(cr_id).name,
    )

  @ddt.data(*TestBaseExternalObjects.OBJECTS)
  def test_internal_object_cr_delete_deprecated(self, model):
    """
      Test DELETE Custom Role for {0.__name__} is deprecated for internal API.
    """
    object_type = model.__name__
    cr = factories.AccessControlRoleFactory(
        object_type=object_type,
        non_editable=False,
    )
    cr_id = cr.id

    response = self.api.delete(cr, id_=cr.id)

    self.assert403(response)
    self.assertIsNotNone(
        CR.query.filter_by(id=cr_id).first(),
    )

  @ddt.data(*product(TestBaseExternalObjects.OBJECTS,
                     TestBaseExternalObjects.OBJECTS))
  @ddt.unpack
  def test_objects_mapping_deprecation(self, model1, model2):
    """
        Test mapping between {0.__name__} and {1.__name__} is deprecated
    """
    if (model1 not in all_models.get_scope_models() or
       model2 not in all_models.get_scope_models()):
      expected_msg = (
          u"You do not have the necessary permissions to map and unmap "
          u"Threat, Requirement, Policy, Objective or Contact to scoping "
          u"objects, risks, controls, standards and regulations in this "
          u"application."
          u"Please contact your administrator if you have any questions."
      )
    else:
      expected_msg = (
          "You do not have the necessary permissions to map and "
          "unmap scoping objects to scoping objects, risks, "
          "controls, standards and regulations in this application."
          "Please contact your administrator if you have any "
          "questions."
      )

    with factories.single_commit():
      scope_model_1 = factories.get_model_factory(model1.__name__)()
      scope_model_2 = factories.get_model_factory(model2.__name__)()

    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {
                "id": scope_model_1.id,
                "type": scope_model_1.type,
            },
            "destination": {
                "id": scope_model_2.id,
                "type": scope_model_2.type
            },
            "context": None
        },
    })

    self.assertStatus(response, 400)
    self.assertIn(expected_msg, response.data)
