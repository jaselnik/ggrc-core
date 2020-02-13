# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Tests for PUT and POST requests for objects with custom attributes

These tests include:
- Creating an object with custom attributes (POST request).
- Editing existing custom attributes on an object.
- Adding custom attributes to existing object.

"""
import json

import ddt

from ggrc import utils
from ggrc import models
from ggrc.models import all_models
from ggrc.models.mixins import customattributable

from integration.ggrc.api_helper import Api
from integration.external_app import external_api_helper
from integration.ggrc.services import TestCase
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


class RegulationTestCase(TestCase):
  """Test case for Regulation post and put requests."""

  def setUp(self):
    super(RegulationTestCase, self).setUp()
    self.generator = ObjectGenerator()
    self.client.get("/login")
    self.ext_api = external_api_helper.ExternalApiClient()

  @staticmethod
  def _regulation_payload(cad, person_id):
    """

    Args:
      cad: an CustomAttributeDefinition instance
      person_id: an int() ID of Person instance
    Returns:
      list() with Regulation payload
    """
    return [{
        "regulation": {
            "id": 1,
            "kind": "Regulation",
            "owners": [],
            "custom_attribute_definitions":[
                {"id": cad.id},
            ],
            "custom_attribute_values": [{
                "attribute_value": "new value",
                "custom_attribute_id": cad.id,
            }],
            "custom_attributes": {
                cad.id: "old value",
            },
            "contact": {
                "id": person_id,
                "href": "/api/people/{}".format(person_id),
                "type": "Person"
            },
            "title": "simple product",
            "description": "",
            "secondary_contact": None,
            "notes": "",
            "url": "",
            "documents_reference_url": "",
            "slug": "",
            "context": None,
            "external_id": 1,
            "external_slug": "reg1",
        },
    }]

  def _put(self, url, data, extra_headers=None):
    """Perform a put request."""
    headers = {'X-Requested-By': 'Unit Tests'}
    headers.update(extra_headers)
    return self.client.put(
        url,
        content_type='application/json',
        data=utils.as_json(data),
        headers=headers,
    )

  def _post(self, data):
    """Perform a post request."""
    return self.client.post(
        "/api/regulations",
        content_type='application/json',
        data=utils.as_json(data),
        headers={'X-Requested-By': 'Unit Tests'},
    )


class GCADirectiveTestCase(RegulationTestCase):
  """Test case with GCAs payload preparation and testing."""
  @staticmethod
  def _get_text_payload(definition_type):
    """Gets payload for text GCA.

    Args:
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    return {
        "title": "GCA Text",
        "attribute_type": "Text",
        "definition_type": definition_type,
        "mandatory": False,
        "helptext": "GCA Text attribute",
        "placeholder": "Input text",
        "context": None,
        "external_id": 1,
        "external_name": "random_string_123123",
        "external_type": "CustomAttributeDefinition",
    }

  @staticmethod
  def _get_rich_text_payload(definition_type):
    """Gets payload for rich text GCA.

    Args:
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    return {
        "title": "GCA Rich Text",
        "attribute_type": "Rich Text",
        "definition_type": definition_type,
        "mandatory": False,
        "helptext": "GCA Text attribute",
        "placeholder": "Input text",
        "context": None,
        "external_id": 1,
        "external_name": "random_html_123123",
        "external_type": "CustomAttributeDefinition",
    }

  @staticmethod
  def _get_date_payload(definition_type):
    """Gets payload for date GCA.

    Args:
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    return {
        "title": "GCA Date",
        "attribute_type": "Date",
        "definition_type": definition_type,
        "mandatory": False,
        "helptext": "GCA Date attribute",
        "context": None,
        "external_id": 1,
        "external_name": "random_date_123123",
        "external_type": "CustomAttributeDefinition",
    }

  @staticmethod
  def _get_dropdown_payload(definition_type):
    """Gets payload for dropdown GCA.

    Args:
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    return {
        "title": "GCA Dropdown",
        "attribute_type": "Dropdown",
        "definition_type": definition_type,
        "mandatory": False,
        "helptext": "GCA Dropdown attribute",
        "context": None,
        "external_id": 1,
        "external_name": "random_dropdown_123123",
        "multi_choice_options": "1,3,2",
        "external_type": "CustomAttributeDefinition",
    }

  @staticmethod
  def _get_multiselect_payload(definition_type):
    """Gets payload for multiselect GCA.

    Args:
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    return {
        "title": "GCA Multiselect",
        "attribute_type": "Multiselect",
        "definition_type": definition_type,
        "mandatory": False,
        "helptext": "GCA Multiselect attribute",
        "context": None,
        "external_id": 1,
        "external_name": "random_multistring_123123",
        "multi_choice_options": "1,3,2",
        "external_type": "CustomAttributeDefinition",
    }

  @classmethod
  def _get_payload(cls, attribute_type, definition_type):
    """Gets payload for GCA by attribute type.

    Args:
      attribute_type: String representation of attribute type.
      definition_type: String representation of definition type.
    Returns:
      Dictionary with attribute configuration.
    """
    payload_handlers = {
        "Text": cls._get_text_payload,
        "Rich Text": cls._get_rich_text_payload,
        "Date": cls._get_date_payload,
        "Dropdown": cls._get_dropdown_payload,
        "Multiselect": cls._get_multiselect_payload,
    }

    return payload_handlers[attribute_type](definition_type)

  def _run_text_asserts(self, external_cad, attribute_payload):
    """Runs CAD text/rich asserts.

    Args:
      external_cad: CAD for validation.
      attribute_payload: Dictionary with attribute configuration.
    """
    self.assertEqual(
        external_cad.title,
        attribute_payload["title"]
    )
    self.assertEqual(
        external_cad.definition_type,
        attribute_payload["definition_type"]
    )
    self.assertEqual(
        external_cad.attribute_type,
        attribute_payload["attribute_type"]
    )
    self.assertEqual(
        external_cad.mandatory,
        attribute_payload["mandatory"]
    )
    self.assertEqual(
        external_cad.helptext,
        attribute_payload["helptext"]
    )
    self.assertEqual(
        external_cad.placeholder,
        attribute_payload["placeholder"]
    )
    self.assertEqual(
        external_cad.external_name,
        attribute_payload["external_name"]
    )

  def _run_date_asserts(self, external_cad, attribute_payload):
    """Runs CAD date asserts.

    Args:
      external_cad: CAD for validation.
      attribute_payload: Dictionary with attribute configuration.
    """
    self.assertEqual(
        external_cad.title,
        attribute_payload["title"]
    )
    self.assertEqual(
        external_cad.definition_type,
        attribute_payload["definition_type"]
    )
    self.assertEqual(
        external_cad.attribute_type,
        attribute_payload["attribute_type"]
    )
    self.assertEqual(
        external_cad.mandatory,
        attribute_payload["mandatory"]
    )
    self.assertEqual(
        external_cad.helptext,
        attribute_payload["helptext"]
    )
    self.assertEqual(
        external_cad.external_name,
        attribute_payload["external_name"]
    )

  def _run_select_asserts(self, external_cad, attribute_payload):
    """Runs CAD dropdown/multiselect asserts.

    Args:
      external_cad: CAD for validation.
      attribute_payload: Dictionary with attribute configuration.
    """
    self.assertEqual(
        external_cad.title,
        attribute_payload["title"]
    )
    self.assertEqual(
        external_cad.definition_type,
        attribute_payload["definition_type"]
    )
    self.assertEqual(
        external_cad.attribute_type,
        attribute_payload["attribute_type"]
    )
    self.assertEqual(
        external_cad.mandatory,
        attribute_payload["mandatory"]
    )
    self.assertEqual(
        external_cad.helptext,
        attribute_payload["helptext"]
    )
    self.assertEqual(
        external_cad.multi_choice_options,
        attribute_payload["multi_choice_options"]
    )
    self.assertEqual(
        external_cad.external_name,
        attribute_payload["external_name"]
    )

  def _run_cad_asserts(self, attribute_type, external_cad, attribute_payload):
    """Runs CAD asserts by attribute type.

    Args:
      external_cad: CAD for validation.
      attribute_type: String representation of attribute type.
      attribute_payload: Dictionary with attribute configuration.
    """
    asserts = {
        "Text": self._run_text_asserts,
        "Rich Text": self._run_text_asserts,
        "Date": self._run_date_asserts,
        "Dropdown": self._run_select_asserts,
        "Multiselect": self._run_select_asserts,
    }
    asserts[attribute_type](external_cad, attribute_payload)


GCA_SYNC_TEST_DATA = [
    (model, attr_type)
    for attr_type in ["Text", "Rich Text", "Date", "Dropdown", "Multiselect"]
    for model in all_models.get_external_models()
]


@ddt.ddt
class TestGlobalCustomAttributes(RegulationTestCase):
  """Tests for API updates for custom attribute values."""

  def test_custom_attribute_post(self):
    """Test post object with custom attributes."""
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="regulation",
        attribute_type="Text",
        title="normal text",
    )
    pid = models.Person.query.first().id

    regulation_data = self._regulation_payload(cad, pid)

    response = self.ext_api.post(all_models.Regulation, data=regulation_data)
    ca_json = response.json[0][1]["regulation"]["custom_attribute_values"][0]
    self.assertIn("attributable_id", ca_json)
    self.assertIn("attributable_type", ca_json)
    self.assertIn("attribute_value", ca_json)
    self.assertIn("id", ca_json)
    self.assertEqual(ca_json["attribute_value"], "new value")

    regulation = models.Regulation.eager_query().first()
    self.assertEqual(len(regulation.custom_attribute_values), 1)
    self.assertEqual(regulation.custom_attribute_values[0].attribute_value,
                     "new value")

  @ddt.data(
      ("control", "Control title"),
      ("risk", "Risk title"),
      ("Standard", "Standard title"),
      ("Regulation", "Regulation title"),
  )
  @ddt.unpack
  def test_create_from_ggrc(self, definition_type, title):
    """Test create definition not allowed for GGRC."""
    api = Api()
    payload = [
        {
            "custom_attribute_definition": {
                "attribute_type": "Text",
                "context": {"id": None},
                "definition_type": definition_type,
                "helptext": "Some text",
                "mandatory": False,
                "modal_title": "Modal title",
                "placeholder": "Placeholder",
                "title": title
            }
        }
    ]
    response = api.post(all_models.CustomAttributeDefinition, payload)
    self.assertEqual(response.status_code, 405)

  def test_custom_attribute_put_add(self):
    """Test edits with adding new CA values."""
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="regulation",
        attribute_type="Text",
        title="normal text",
    )
    pid = models.Person.query.first().id
    regulation_data = self._regulation_payload(cad, pid)
    response = self.ext_api.post(all_models.Regulation, data=regulation_data)

    self.assert200(response)

    regulation_data[0]["regulation"]["custom_attribute_values"] = [{
        "attribute_value":
        "added value",
        "custom_attribute_id":
        cad.id,
    }]
    response = self.ext_api.put(
        obj="regulation",
        obj_id=regulation_data[0]["regulation"]["id"],
        data=regulation_data[0],
    )

    self.assert200(response)

    regulation = response.json["regulation"]
    ca_json = regulation["custom_attribute_values"][0]

    self.assertEqual(len(regulation["custom_attribute_values"]), 1)
    self.assertIn("attributable_id", ca_json)
    self.assertIn("attributable_type", ca_json)
    self.assertIn("attribute_value", ca_json)
    self.assertIn("id", ca_json)
    self.assertEqual(ca_json["attribute_value"], "added value")

    regulation = models.Regulation.eager_query().first()
    self.assertEqual(len(regulation.custom_attribute_values), 1)
    self.assertEqual(regulation.custom_attribute_values[0].attribute_value,
                     "added value")

    regulation_data[0]["regulation"]["custom_attribute_values"] = [{
        "attribute_value":
        "edited value",
        "custom_attribute_id":
        cad.id,
    }]

    response = self.ext_api.put(
        obj="regulation",
        obj_id=regulation_data[0]["regulation"]["id"],
        data=regulation_data[0],
    )

    regulation = response.json["regulation"]
    ca_json = regulation["custom_attribute_values"][0]
    self.assertIn("attributable_id", ca_json)
    self.assertIn("attributable_type", ca_json)
    self.assertIn("attribute_value", ca_json)
    self.assertIn("id", ca_json)
    self.assertEqual(ca_json["attribute_value"], "edited value")

  def test_custom_attribute_get(self):
    """Check if get returns the whole CA value and not just the stub."""
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="regulation",
        attribute_type="Text",
        title="normal text",
    )
    pid = models.Person.query.first().id

    regulation_data = self._regulation_payload(cad, pid)

    response = self.ext_api.post(all_models.Regulation, data=regulation_data)
    regulation_url = response.json[0][1]["regulation"]["selfLink"]
    get_response = self.client.get(regulation_url)
    regulation = get_response.json["regulation"]
    self.assertIn("custom_attribute_values", regulation)
    self.assertEqual(len(regulation["custom_attribute_values"]), 1)
    cav = regulation["custom_attribute_values"][0]
    self.assertIn("custom_attribute_id", cav)
    self.assertIn("attribute_value", cav)
    self.assertIn("id", cav)

  @ddt.data(
      (" abc ", "abc"),
      ("    abc  abc ", "abc abc"),
      ("abc", "abc"),
  )
  @ddt.unpack
  def test_cad_title_strip(self, title, validated_title):
    """Test CAD title strip on validation."""
    with factories.single_commit():
      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="objective",
          attribute_type=all_models.CustomAttributeDefinition.ValidTypes.TEXT,
          title=title,
      )
    cad_resp = self.generator.api.get(cad, cad.id)
    self.assert200(cad_resp)
    self.assertEquals(cad_resp.json['custom_attribute_definition']['title'],
                      validated_title)

  def test_cad_title_strip_unique(self):
    """Test CAD title stripped should be unique."""
    factories.CustomAttributeDefinitionFactory(
        definition_type="objective",
        attribute_type=all_models.CustomAttributeDefinition.ValidTypes.TEXT,
        title="abc",
    )
    with self.assertRaises(ValueError):
      factories.CustomAttributeDefinitionFactory(
          definition_type="objective",
          attribute_type=all_models.CustomAttributeDefinition.ValidTypes.TEXT,
          title=" abc ",
      )

  @ddt.data(
      (all_models.CustomAttributeDefinition.ValidTypes.TEXT, ""),
      (all_models.CustomAttributeDefinition.ValidTypes.RICH_TEXT, ""),
      (all_models.CustomAttributeDefinition.ValidTypes.DROPDOWN, ""),
      (all_models.CustomAttributeDefinition.ValidTypes.CHECKBOX, "0"),
      (all_models.CustomAttributeDefinition.ValidTypes.DATE, ""),
  )
  @ddt.unpack
  def test_get_cad_default(self, cad_type, default_value):
    """Check default_value for cad via object and direct cad api."""
    with factories.single_commit():
      objective = factories.ObjectiveFactory()
      cad = factories.CustomAttributeDefinitionFactory(
          definition_type="objective",
          attribute_type=cad_type,
      )
    cad_id = cad.id
    objective_id = objective.id
    objective_resp = self.generator.api.get(objective, objective_id)
    cad_resp = self.generator.api.get(cad, cad_id)
    self.assert200(cad_resp)
    self.assert200(objective_resp)
    self.assertIn("custom_attribute_definitions",
                  objective_resp.json["objective"])
    _cads = objective_resp.json["objective"]["custom_attribute_definitions"]
    self.assertEqual(1, len(_cads))
    cad_json = _cads[0]
    self.assertEqual(cad_id, cad_json["id"])
    self.assertIn("default_value", cad_json)
    self.assertEqual(default_value, cad_json["default_value"])
    self.assertIn("custom_attribute_definition", cad_resp.json)
    self.assertIn("default_value",
                  cad_resp.json["custom_attribute_definition"])
    self.assertEqual(
        default_value,
        cad_resp.json["custom_attribute_definition"]["default_value"])

  @ddt.data((True, "1"), (True, "true"), (True, "TRUE"), (False, "0"),
            (False, "false"), (False, "FALSE"))
  @ddt.unpack
  def test_filter_by_mandatory(self, flag_value, filter_value):
    """Filter CADs by mandatory flag if it's {0} and filter_value is {1}."""
    with factories.single_commit():
      cads = {
          f: factories.CustomAttributeDefinitionFactory(
              mandatory=f, definition_type="objective")
          for f in [True, False]
      }
    resp = self.generator.api.get_query(
        all_models.CustomAttributeDefinition,
        "ids={}&mandatory={}".format(",".join(
            [str(c.id) for c in cads.values()]), filter_value),
    )
    self.assert200(resp)
    cad_collection = resp.json["custom_attribute_definitions_collection"]
    resp_cad_ids = [
        i["id"] for i in cad_collection["custom_attribute_definitions"]
    ]
    self.assertEqual([cads[flag_value].id], resp_cad_ids)

  CAD_MODELS = [
      m for m in all_models.all_models
      if issubclass(m, customattributable.CustomAttributable)
  ]

  @ddt.data(*CAD_MODELS)
  def test_filter_by_definition_type(self, definition_model):
    """Filter {0.__name__} CADs by definition_type."""

    with factories.single_commit():
      cads = {
          model: factories.CustomAttributeDefinitionFactory(
              definition_type=model._inflector.table_singular)
          for model in self.CAD_MODELS
      }
    filter_params = "ids={}&definition_type={}".format(
        ",".join([str(c.id) for c in cads.values()]),
        definition_model._inflector.table_singular,
    )
    resp = self.generator.api.get_query(all_models.CustomAttributeDefinition,
                                        filter_params)
    self.assert200(resp)
    cad_collection = resp.json["custom_attribute_definitions_collection"]
    resp_cad_ids = [
        i["id"] for i in cad_collection["custom_attribute_definitions"]
    ]
    self.assertEqual([cads[definition_model].id], resp_cad_ids)

  @ddt.data(
      ("title", "new_title", "Text", None, False),
      ("attribute_type", "Rich Text", "Text", None, False),
      ("helptext", "new helptext", "Text", None, True),
      ("placeholder", "new placeholder", "Text", None, True),
      ("mandatory", True, "Text", None, True),
      ("multi_choice_options", "new,multi,choice,options",
       "Dropdown", "old,multi,choice,options", False),
      ("multi_choice_options", "new,multi,choice,options",
       "Multiselect", "old,multi,choice,options", False),
  )
  @ddt.unpack
  def test_attribute_update(self, attr_name, new_attr_value,
                            attribute_type, multi_choice_options, is_editable):
    """Test editability of {0} which is {2}"""
    # pylint: disable=too-many-arguments
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="program",
        attribute_type=attribute_type,
        multi_choice_options=multi_choice_options,
    )
    old_attr_value = getattr(cad, attr_name)
    response = self.client.get(
        "/api/custom_attribute_definitions/{}".format(cad.id)
    )
    headers, data = response.headers, response.json
    data["custom_attribute_definition"].update({attr_name: new_attr_value})

    response = self._put(
        "/api/custom_attribute_definitions/{}".format(cad.id),
        data,
        extra_headers={
            'If-Unmodified-Since': headers["Last-Modified"],
            'If-Match': headers["Etag"],
        }
    )
    self.assert200(response)

    cad = all_models.CustomAttributeDefinition.query.get(cad.id)
    is_changed = old_attr_value != getattr(cad, attr_name)
    self.assertEquals(is_changed, is_editable)


class TestOldApiCompatibility(RegulationTestCase):
  """Test Legacy CA values API.

  These tests check that the old way of setting custom attribute values still
  works and that If both ways are used, the legacy code is ignored.
  """

  def test_custom_attribute_post_both(self):
    """Test post with both custom attribute api options.

    This tests tries to set a custom attribute on the new and the old way at
    once. The old option should be ignored and the new value should be set.
    """
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="regulation",
        attribute_type="Text",
        title="normal text",
    )
    pid = models.Person.query.first().id

    regulation_data = self._regulation_payload(cad, pid)

    response = self.ext_api.post(obj="Regulation", data=regulation_data)
    ca_json = response.json[0][1]["regulation"]["custom_attribute_values"][0]
    self.assertEqual(ca_json["attribute_value"], "new value")

    regulation = models.Regulation.eager_query().first()
    self.assertEqual(len(regulation.custom_attribute_values), 1)
    self.assertEqual(regulation.custom_attribute_values[0].attribute_value,
                     "new value")

  def test_custom_attribute_post_old(self):
    """Test post with old style custom attribute values.

    This tests that the legacy way of setting custom attribute values still
    works.
    """
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="regulation",
        attribute_type="Text",
        title="normal text",
    )
    pid = models.Person.query.first().id
    regulation_data = self._regulation_payload(cad, pid)
    response = self.ext_api.post(all_models.Regulation, data=regulation_data)

    self.assert200(response)

    ca_json = response.json[0][1]["regulation"]["custom_attribute_values"][0]
    self.assertEqual(ca_json["attribute_value"], "new value")

    product = models.Regulation.eager_query().first()
    self.assertEqual(len(product.custom_attribute_values), 1)
    self.assertEqual(product.custom_attribute_values[0].attribute_value,
                     "new value")


@ddt.ddt
class TestInternalGCASyncObjects(GCADirectiveTestCase):
  """Tests for GCA model for sync models."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestInternalGCASyncObjects, self).setUp()
    self.api = Api()

  @ddt.data(*GCA_SYNC_TEST_DATA)
  @ddt.unpack
  def test_create_custom_attribute_405(self, object_model, attribute_type):
    """Test unable create external CAD via C API."""
    # pylint: disable=invalid-name
    definition_type = object_model._inflector.table_singular
    attribute_payload = self._get_payload(
        attribute_type,
        definition_type,
    )
    payload = [
        {
            "custom_attribute_definition": attribute_payload,
        },
    ]

    response = self.api.post(
        all_models.CustomAttributeDefinition,
        data=payload
    )

    self.assert405(response)
    cad_count = all_models.CustomAttributeDefinition.query.count()
    self.assertEqual(cad_count, 0)

  @ddt.data(*GCA_SYNC_TEST_DATA)
  @ddt.unpack
  def test_update_custom_attribute_405(self, object_model, attribute_type):
    """Test unable update external CAD via C API."""
    # pylint: disable=invalid-name
    definition_type = object_model._inflector.table_singular
    internal_cad = factories.CustomAttributeDefinitionFactory(
        title="GCA test",
        definition_type=definition_type,
        attribute_type=attribute_type,
        multi_choice_options="1,3,2,4,5",
    )
    attribute_payload = self._get_payload(
        attribute_type,
        definition_type,
    )
    payload = {
        "custom_attribute_definition": attribute_payload,
    }
    response = self.api.put(internal_cad, payload)
    self.assert405(response)

  @ddt.data(*GCA_SYNC_TEST_DATA)
  @ddt.unpack
  def test_get_custom_attribute(self, object_model, attribute_type):
    """Test for get external CAD validation."""
    definition_type = object_model._inflector.table_singular
    attribute_payload = self._get_payload(
        attribute_type,
        definition_type,
    )
    external_cad = factories.CustomAttributeDefinitionFactory(
        **attribute_payload
    )
    response = self.api.get(
        all_models.CustomAttributeDefinition,
        external_cad.id,
    )

    self.assertEqual(response.status_code, 200)
    response_json = json.loads(response.data)
    external_cad = all_models.CustomAttributeDefinition.query.one()
    self._run_cad_asserts(
        attribute_type,
        external_cad,
        response_json["custom_attribute_definition"]
    )
