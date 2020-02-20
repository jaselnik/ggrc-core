# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for snapshot model."""

import ddt

from ggrc.models import all_models
from ggrc.snapshotter import rules as snapshotter_rules
from integration import ggrc as integration_ggrc
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc import generator


def get_snapshottable_models():
  """Return the set of snapshottable models."""
  return {getattr(all_models, stype) for stype in snapshotter_rules.Types.all}


@ddt.ddt
class TestSnapshotContent(integration_ggrc.TestCase):
  """Basic tests for snapshot's content."""

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
      "attribute_object_id_nn",
      "last_submitted_by_id",
      "last_verified_by_id",

      # revisions require complete data for documents,
      # while api returns only basic data in stubs
      "documents_reference_url",
      "documents_file",

      # computed attributes are not stored in revisions and should be ignored.
      "attributes",
      "last_assessment_date",
  }

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestSnapshotContent, self).setUp()
    self.client.get("/login")

  def _get_object(self, obj):
    """Get JSON representation of passed object."""
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

  @ddt.data(*get_snapshottable_models())
  def test_snapshot_content(self, model):
    """Test the content of stored revisions for {0.__name__}

    The content in the revision (that is set by log_json) must match closely to
    what the api returns for a get request. This ensures that when a model is
    created from a snapshot on the frontend, it will have all the needed
    fields.
    """
    with factories.single_commit():
      factories.get_model_factory(model.__name__)()

    obj = model.eager_query().first()
    generated_json = self._clean_json(obj.log_json())
    expected_json = self._clean_json(self._get_object(obj))
    self.assertEqual(expected_json, generated_json)


class TestSnapshot(integration_ggrc.TestCase):
  """Basic tests snapshots"""

  def setUp(self):  # pylint: disable=missing-docstring
    super(TestSnapshot, self).setUp()
    self.api = api_helper.Api()
    self.generator = generator.ObjectGenerator()

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

  # pylint: disable=invalid-name
  def test_identity_revision_after_adding_comment(self):
    """Test checks identity of revisions after adding comment"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      standard = factories.StandardFactory()

    snapshot = self._create_snapshots(audit, [standard])[0]
    snapshot_id = snapshot.id
    self.generator.generate_comment(standard, "", "some comment")

    response = self.api.get(snapshot.__class__, snapshot_id)
    self.assertStatus(response, 200)
    self.assertTrue(response.json['snapshot']['is_identical_revision'])

  def test_is_identical_revision(self):
    """Test checks correctly work of is_identical_revision flag"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      standard = factories.StandardFactory()
      standard_id = standard.id

    snapshot = self._create_snapshots(audit, [standard])[0]
    snapshot_id = snapshot.id
    standard = all_models.Standard.query.get(standard_id)
    self.api.put(standard, {"title": "Test standard 1"})
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assertFalse(snapshot.is_identical_revision)
