# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for snapshot model."""

from ggrc.app import app
from ggrc.models import all_models
from ggrc.snapshotter.rules import Types
from integration.ggrc import TestCase, Api
from integration.ggrc.models import factories


def get_snapshottable_models():
  return {getattr(all_models, stype) for stype in Types.all}


class TestSnapshotQueryApi(TestCase):
  """Basic tests for /query api."""

  IGNORE_KEYS = {
      # currently not working fields:
      "audit_duration",
      "audit_duration_id",

      "audit_frequency",
      "audit_frequency_id",

      "directive",
      "directive_id",

      "kind",
      "kind_id",

      "means",

      "meta_kind",

      "network_zone",
      "network_zone_id",

      "verify_frequency",
      "verify_frequency_id",

      # special fields not needed for snapshots.
      "display_name",
      "preconditions_failed",
      "type",
      "workflow_state",

      "selfLink",
      "viewLink",


      # relationships and mappings
      "audits",
      "controls",
      "object_people",
      "objects",
      "people",
      "related_destinations",
      "related_sources",
      "risks",
      "task_group_tasks",
      "task_groups",

      "children",
      "parent",
      "parent_id",

      # we don't need context for snapshots since they are all under an audit.
      "context",
      "context_id",

      # obsolete fields that will be removed
      "custom_attributes",

      # following fields have been handled in fields without _id prefix. That
      # means that "contact" fields should exists and have correct values.
      "contact_id",
      "secondary_contact_id",

      "created_by_id",
      "modified_by_id",

      "attribute_object_id",
      "last_submitted_by_id",
      "last_verified_by_id",
      "last_compliance_reviewed_by_id",
      "last_owner_reviewed_by_id",

      # revisions require complete data for documents,
      # while api returns only basic data in stubs
      "documents_reference_url",
      "documents_file",

      # computed attributes are not stored in revisions and should be ignored.
      "attributes",
      "last_assessment_date",

      "access_control_list",  # TODO: remove this line (GGRC-2402)
  }

  def setUp(self):
    """Set up test cases for all tests."""
    super(TestSnapshotQueryApi, self).setUp()
    self._create_cas()
    self._create_external_object()
    self.import_file("all_snapshottable_objects.csv")

  def _create_cas(self):
    """Create custom attribute definitions."""
    self._ca_objects = {}
    ca_model_names = [
        "facility",
        "control",
        "market",
        "requirement",
        "threat",
        "access_group",
        "data_asset"
    ]
    ca_args = [
        {"title": "CA text", "attribute_type": "Text"},
        {"title": "CA rich text", "attribute_type": "Rich Text"},
        {"title": "CA date", "attribute_type": "Date"},
        {"title": "CA checkbox", "attribute_type": "Checkbox"},
        {"title": "CA person", "attribute_type": "Map:Person"},
        {"title": "CA dropdown", "attribute_type": "Dropdown",
         "multi_choice_options": "one,two,three,four,five"},
    ]
    for type_ in ca_model_names:
      with app.app_context():
        for args in ca_args:
          factories.CustomAttributeDefinitionFactory(
              definition_type=type_,
              **args
          )

  @staticmethod
  def _create_external_object():
    """Populate external model object that could not be imported."""
    with factories.single_commit():
      ca_person = factories.PersonFactory(email="user4@example.com")
      objects = [
          factories.ControlFactory(directive=None),
          factories.RiskFactory()
      ]

      ca_definitions = {
          cad.title: cad
          for object in objects
          for cad in object.get_custom_attribute_definitions([
              "CA text",
              "CA rich text",
              "CA date",
              "CA checkbox",
              "CA person",
              "CA dropdown"
          ])
      }
      ca_values = {
          "CA text": "Control ca text",
          "CA rich text": "control<br><br>\nrich text",
          "CA date": "22/02/2022",
          "CA checkbox": "yes",
          "CA person": ca_person,
          "CA dropdown": "one"
      }

      for title, value in ca_values.items():
        for obj in objects:
          factories.CustomAttributeValueFactory(
              custom_attribute=ca_definitions[title],
              attributable=obj,
              attribute_value=value
          )

  def test_revision_content(self):
    """Test that revision contains all content needed."""

    facility_revision = all_models.Revision.query.filter(
        all_models.Revision.resource_type == "Facility").order_by(
        all_models.Revision.id.desc()).first()

    self.assertIn("custom_attribute_values", facility_revision.content)
    self.assertNotEqual(facility_revision.content[
                        "custom_attribute_values"], [])

  def _get_object(self, obj):
    return self.client.get(
        "/api/{}/{}".format(obj._inflector.table_plural, obj.id)  # noqa # pylint: disable=protected-access
    ).json[obj._inflector.table_singular]  # noqa # pylint: disable=protected-access

  def _clean_json(self, content):
    """Remove ignored items from JSON content.

    This function removes all ignored items from dicts, changes dates to
    isoformat changes values to int or unicode, so that the end result is a
    dict that can be compared with the JSON dict that was received from the
    server.

    Args:
      content: object that we want to clean, it can be a dict list or a value.

    Returns:
      content with all values cleaned up
    """
    if isinstance(content, list):
      return sorted(self._clean_json(value) for value in content)

    if hasattr(content, 'isoformat'):
      return unicode(content.isoformat())

    if isinstance(content, int):
      # We convert all numbers to the same type so that the diff of a failed
      # test looks nicer. This conversion does not affect the test results just
      # the output.
      return long(content)

    if not isinstance(content, dict):
      return content

    clean = {}
    for key, value in content.items():
      if key not in self.IGNORE_KEYS:
        clean[str(key)] = self._clean_json(value)

    return clean

  def test_snapshot_content(self):
    """Test the content of stored revisions

    The content in the revision (that is set by log_json) must match closely to
    what the api returns for a get request. This ensures that when a model is
    created from a snapshot on the frontend, it will have all the needed
    fields.
    """
    self.client.get("/login")
    test_models = get_snapshottable_models()
    for model in test_models:
      obj = model.eager_query().first()
      generated_json = self._clean_json(obj.log_json())
      expected_json = self._clean_json(self._get_object(obj))
      self.assertEqual(expected_json, generated_json)


class TestSnapshot(TestCase):
  """Basic tests snapshots"""

  def setUp(self):
    super(TestSnapshot, self).setUp()
    self.api = Api()

  def test_search_by_reference_url(self):
    """Test search audit related snapshots of control type by reference_url"""

    expected_ref_url = "xxx"
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit_id = audit.id
      doc1 = factories.DocumentReferenceUrlFactory(link=expected_ref_url,
                                                   title=expected_ref_url)
      doc_id1 = doc1.id
      doc2 = factories.DocumentReferenceUrlFactory(link="yyy", title="yyy")
      doc_id2 = doc2.id
      control = factories.ControlFactory()
      control_id = control.id

    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": control_id, "type": control.type},
            "destination": {"id": doc_id1, "type": doc1.type},
            "context": None
        },
    })
    self.assertStatus(response, 201)
    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": control_id, "type": control.type},
            "destination": {"id": doc_id2, "type": doc2.type},
            "context": None
        },
    })
    self.assertStatus(response, 201)
    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": control_id, "type": control.type},
            "destination": {"id": audit_id, "type": audit.type},
            "context": None
        },
    })
    self.assertStatus(response, 201)
    query_request_data = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": {
                    "left": "child_type",
                    "op": {"name": "="},
                    "right": "Control"
                },
                "op": {"name": "AND"},
                "right": {
                    "left": {
                        "object_name": "Audit",
                        "op": {"name": "relevant"},
                        "ids": [audit_id]
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "left": {
                            "left": "Reference URL",
                            "op": {"name": "~"},
                            "right": expected_ref_url
                        },
                        "op": {"name": "AND"},
                        "right": {
                            "left": "Status",
                            "op": {"name": "IN"},
                            "right": ["Active", "Draft", "Deprecated"]
                        }
                    }
                }
            }
        },
    }]
    response = self.api.send_request(
        self.api.client.post,
        data=query_request_data,
        api_link="/query"
    )
    self.assert200(response)
    self.assertEquals(1, response.json[0]["Snapshot"]["count"])
