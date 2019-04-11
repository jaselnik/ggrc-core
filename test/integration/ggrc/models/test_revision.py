# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" Tests for ggrc.models.Revision """
from datetime import datetime

from freezegun import freeze_time
import ddt
import mock

import ggrc.models
from ggrc.models import all_models
import integration.ggrc.generator
from integration.ggrc import TestCase

from integration.ggrc.models import factories
from integration.ggrc import api_helper
from integration.ggrc import query_helper
from integration.ggrc.review import build_reviewer_acl


def _get_revisions(obj, field="resource"):
  return ggrc.models.Revision.query.filter_by(**{
      field + "_type": obj.__class__.__name__,
      field + "_id": obj.id
  }).all()


def _project_content(content):
  return {
      "source": {
          "type": content["source_type"],
          "id": content["source_id"],
      },
      "destination": {
          "type": content["destination_type"],
          "id": content["destination_id"],
      },
  }


@ddt.ddt
class TestRevisions(query_helper.WithQueryApi, TestCase):
  """ Tests for ggrc.models.Revision """

  @classmethod
  def setUpClass(cls):
    """Sets up objects common to all tests."""
    cls.gen = integration.ggrc.generator.ObjectGenerator()
    cls.api_helper = api_helper.Api()

  def setUp(self):
    super(TestRevisions, self).setUp()
    self.api_helper.client.get("/login")

  def test_revisions(self):
    """ Test revision creation for POST and PUT """
    cls = ggrc.models.DataAsset
    name = cls._inflector.table_singular  # pylint: disable=protected-access
    _, obj = self.gen.generate(cls, name, {name: {
        "title": "revisioned v1",
        "context": None,
    }})
    revisions = _get_revisions(obj)
    self.assertEqual(len(revisions), 1)

    _, obj = self.gen.modify(obj, name, {name: {
        "slug": obj.slug,
        "title": "revisioned v2",
        "context": None,
    }})
    revisions = _get_revisions(obj)
    expected = {("created", "revisioned v1"), ("modified", "revisioned v2")}
    actual = {(r.action, r.content["title"]) for r in revisions}
    self.assertEqual(actual, expected)

  def test_relevant_revisions(self):
    """ Test revision creation for mapping to an object """
    cls = ggrc.models.DataAsset
    name = cls._inflector.table_singular  # pylint: disable=protected-access

    _, obj1 = self.gen.generate(cls, name, {name: {
        "title": "connected 1",
        "context": None,
    }})

    _, obj2 = self.gen.generate(cls, name, {name: {
        "title": "connected 2",
        "context": None,
    }})

    rel_data = {
        "source": {"id": obj1.id, "type": cls.__name__},
        "destination": {"id": obj2.id, "type": cls.__name__},
        "context": None,
    }
    _, rel = self.gen.generate(ggrc.models.Relationship, "relationship", {
                               "relationship": rel_data})

    revisions_source = _get_revisions(obj1, "source")
    revisions_destination = _get_revisions(obj2, "destination")

    self.assertEqual(revisions_source, revisions_destination)
    self.assertEqual(len(revisions_source), 1)

    self.gen.api.delete(rel)

    revisions_source = _get_revisions(obj1, "source")
    revisions_destination = _get_revisions(obj2, "destination")

    self.assertEqual(revisions_source, revisions_destination)
    self.assertEqual(len(revisions_source), 2)

    expected_data = {
        "source": {
            "type": cls.__name__,
            "id": obj1.id,
        },
        "destination": {
            "type": cls.__name__,
            "id": obj2.id,
        },
    }
    expected = [(u"created", expected_data), ("deleted", expected_data)]

    actual = [(r.action, _project_content(r.content))
              for r in revisions_source]
    self.assertEqual(sorted(actual), sorted(expected))

  def test_content_length(self):
    """Test revision content length restrictions."""
    process = factories.ProcessFactory(
        title="a" * 200,
        description="b" * 65000,
        notes="c" * 65000,
    )
    revision = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == process.id,
        ggrc.models.Revision.resource_type == process.type,
    ).first()
    self.assertIsNotNone(revision)
    self.assertEqual(revision.content["title"], process.title)
    self.assertEqual(revision.content["description"], process.description)

  @ddt.data(True, False)
  def test_revision_after_del_cad(self, is_add_cav):
    """Test creating new revision after deleting CAD.

    In case of deleting CAD, new revision must be created for object,
    which had this CAD.
    """
    with factories.single_commit():
      control = factories.ControlFactory()

      cad = factories.CustomAttributeDefinitionFactory(
          title="test_name",
          definition_type="control",
      )
      cad_id = cad.id
      if is_add_cav:
        factories.CustomAttributeValueFactory(
            custom_attribute=cad,
            attributable=control,
            attribute_value="text",
        )

      revision_id = ggrc.models.Revision.query.filter(
          ggrc.models.Revision.resource_id == control.id,
          ggrc.models.Revision.resource_type == control.type,
      ).order_by(ggrc.models.Revision.id.desc()).first().id

    with self.api_helper.as_external():
      self.api_helper.delete(cad, cad_id)

    control = ggrc.models.Control.query.first()

    last_revision_id = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == control.id,
        ggrc.models.Revision.resource_type == control.type,
    ).order_by(ggrc.models.Revision.id.desc()).first().id

    self.assertGreater(last_revision_id, revision_id)

  @ddt.data(True, False)
  def test_change_modified_by(self, is_add_cav):
    """Test checked correct changing of modified_by_id field.

    User 1 create control, user 2 delete CAD. After the deleting CAD
    test checking that modified_by field contains user 2.
    """
    with factories.single_commit():
      control = factories.ControlFactory()
      cad = factories.CustomAttributeDefinitionFactory(
          title="test_cad",
          definition_type="control",
          attribute_type="Text",
      )
      control_id = control.id
      if is_add_cav:
        factories.CustomAttributeValueFactory(
            custom_attribute=cad,
            attributable=control,
            attribute_value="test")

    user = self.gen.generate_person(
        data={"name": "test_admin", "email": "external_app@example.com"},
        user_role="Administrator")[1]
    self.api_helper.set_user(user)
    self.client.get("/login")

    control_revisions = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == control_id,
        ggrc.models.Revision.resource_type == "Control",
    ).order_by(ggrc.models.Revision.id.desc()).all()
    ids_before_del = set(revision.id for revision in control_revisions)

    cad = ggrc.models.CustomAttributeDefinition.query.filter_by(
        title="test_cad").first()
    resp_delete = self.api_helper.delete(cad)
    self.assert200(resp_delete)
    cad = ggrc.models.CustomAttributeDefinition.query.filter_by(
        title="test_cad").first()
    self.assertIsNone(cad)

    control_revisions_after = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == control_id,
        ggrc.models.Revision.resource_type == "Control",
    ).order_by(ggrc.models.Revision.id.desc()).all()
    ids_after_del = set(revision.id for revision
                        in control_revisions_after)

    difference_revision_id = ids_after_del.difference(ids_before_del)

    last_revision = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == control_id,
        ggrc.models.Revision.resource_type == "Control",
    ).order_by(ggrc.models.Revision.id.desc()).first()

    self.assertSetEqual(difference_revision_id, {last_revision.id})

    expected_id = ggrc.models.Person.query.filter_by(
        name="test_admin").first().id

    self.assertEquals(last_revision.content["modified_by_id"], expected_id)
    self.assertEquals(last_revision.content["modified_by"]["id"], expected_id)

  def _test_revision_with_empty_cads(self,
                                     attribute_type,
                                     attribute_value,
                                     is_global):
    """Population cavs and cads depend on is_global flag and send params."""
    asmnt = factories.AssessmentFactory()
    asmnt_id = asmnt.id
    cad_params = {
        "title": "test_cad",
        "definition_type": "assessment",
        "attribute_type": attribute_type
    }
    if not is_global:
      cad_params["definition_id"] = asmnt_id
    with factories.single_commit():
      cad = factories.CustomAttributeDefinitionFactory(**cad_params)
    cad_id = cad.id
    revisions = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == asmnt_id,
        ggrc.models.Revision.resource_type == "Assessment",
    ).order_by(ggrc.models.Revision.id.desc()).all()
    self.assertEqual(1, len(revisions))
    revision = revisions[0]
    # pylint: disable=protected-access
    self.assertIn("custom_attribute_values", revision._content)
    self.assertIn("custom_attribute_definitions", revision._content)
    self.assertEqual([], revision._content["custom_attribute_values"])
    self.assertEqual([], revision._content["custom_attribute_definitions"])
    self.assertIn("custom_attribute_values", revision.content)
    self.assertEqual(
        [{
            'attributable_id': asmnt_id,
            'attributable_type': 'Assessment',
            'attribute_object': None,
            'attribute_value': attribute_value,
            'context_id': None,
            'custom_attribute_id': cad_id,
            'display_name': '',
            'type': 'CustomAttributeValue',
        }],
        revision.content["custom_attribute_values"])
    self.assertIn("custom_attribute_definitions", revision.content)
    cad = all_models.CustomAttributeDefinition.query.get(cad_id)
    self.assertEqual([cad.log_json()],
                     revision.content["custom_attribute_definitions"])

  @ddt.data(
      ("Text", ""),
      ("Rich Text", ""),
      ("Dropdown", ""),
      ("Checkbox", "0"),
      ("Date", ""),
      ("Map:Person", "Person"),
  )
  @ddt.unpack
  def test_revisions_with_empty_gcads(self, attribute_type, attribute_value):
    """Population cavs and global cads for type {0}."""
    self._test_revision_with_empty_cads(attribute_type, attribute_value, True)

  @ddt.data(
      ("Text", ""),
      ("Rich Text", ""),
      ("Dropdown", ""),
      ("Checkbox", "0"),
      ("Date", ""),
      ("Map:Person", "Person"),
  )
  @ddt.unpack
  def test_revisions_with_empty_lcads(self, attribute_type, attribute_value):
    """Population cavs and local cads for type {0}."""
    self._test_revision_with_empty_cads(attribute_type, attribute_value, False)

  @ddt.data("", u"0", u"", None, "0")
  @mock.patch(
      "ggrc.models.custom_attribute_value.CustomAttributeValue"
      "._validate_checkbox", return_value=True
  )
  def test_revisions_invalid_cavs(self, value, _):
    """Test filtering of Checkbox CAVs."""
    with factories.single_commit():
      asmnt = factories.AssessmentFactory()
      ca_def = factories.CustomAttributeDefinitionFactory(
          definition_id=asmnt.id,
          definition_type="assessment",
          title="CA",
          attribute_type="Checkbox",
      )

    self.gen.api.modify_object(
        asmnt, {
            "custom_attribute_values": [{
                "attributable_id": asmnt.id,
                "attributable_type": "assessment",
                "attribute_value": value,
                "custom_attribute_id": ca_def.id,
            }, ],
        },
    )
    revisions = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == asmnt.id,
        ggrc.models.Revision.resource_type == "Assessment",
    ).order_by(ggrc.models.Revision.id.desc()).all()
    content = revisions[0].content
    self.assertEqual(
        content["custom_attribute_values"][0]["attribute_value"], "0")

  def test_revisions_cavs_wo_cad(self):
    """Test filtering CAVs without definitions."""
    with factories.single_commit():
      asmnt = factories.AssessmentFactory()
      ca_def = factories.CustomAttributeDefinitionFactory(
          definition_id=asmnt.id,
          definition_type="assessment",
          title="CA",
          attribute_type="Text",
      )
      ca_def_id = ca_def.id

    self.gen.api.modify_object(
        asmnt, {
            "custom_attribute_values": [{
                "attributable_id": asmnt.id,
                "attributable_type": "assessment",
                "attribute_value": "abc",
                "custom_attribute_id": ca_def.id,
            }, ],
        },
    )
    ggrc.models.CustomAttributeDefinition.query.filter_by(
        id=ca_def_id
    ).delete()

    revisions = ggrc.models.Revision.query.filter(
        ggrc.models.Revision.resource_id == asmnt.id,
        ggrc.models.Revision.resource_type == "Assessment",
    ).order_by(ggrc.models.Revision.id.desc()).all()
    content = revisions[0].content
    self.assertEqual(content["custom_attribute_values"], [])

  def test_revision_review_stub(self):
    """ Test proper review stub population in revision content """
    program = factories.ProgramFactory()
    revisions = _get_revisions(program)
    self.assertEqual(len(revisions), 1)
    self.assertEqual(revisions[0].action, "created")

    resp = self.api_helper.post(
        all_models.Review,
        {
            "review": {
                "reviewable": {
                    "type": program.type,
                    "id": program.id,
                },
                "context": None,
                "notification_type": "email",
                "status": all_models.Review.STATES.REVIEWED,
                "access_control_list": build_reviewer_acl()
            },
        },
    )
    self.assertEqual(201, resp.status_code)
    self.assertIn("review", resp.json)
    resp_review = resp.json["review"]
    self.assertEqual(all_models.Review.STATES.REVIEWED,
                     resp_review["status"])

    revisions = _get_revisions(program)
    self.assertEqual(len(revisions), 2)
    self.assertEqual(revisions[0].action, "created")
    self.assertEqual(revisions[1].action, "modified")

    rev_content = revisions[1].content
    self.assertIsNotNone(rev_content)
    self.assertIn("review", rev_content)
    review = rev_content["review"]
    self.assertIsNotNone(review)

    expected = {
        "context_id": None,
        "href": "/api/reviews/{}".format(resp_review["id"]),
        "id": resp_review["id"],
        "type": resp_review["type"],
    }

    self.assertEqual(review, expected)

  def test_revision_ordering(self):
    """Test revision ordering by created_at with query api"""
    with factories.single_commit():
      # pylint: disable=expression-not-assigned
      [factories.ControlFactory() for i in range(10)]
      # pylint: enable=expression-not-assigned

    query = self._make_query_dict(
        "Revision", expression=("resource_type", "=", "Control"),
        order_by=[{"name": "created_at", "desc": True}]
    )

    self.client.get("/login")
    result = self._get_first_result_set(query, "Revision")
    count, values = result["count"], result["values"]

    datetime_format = "%Y-%m-%dT%H:%M:%S"
    for value in values:
      value["created_at"] = datetime.strptime(value["created_at"],
                                              datetime_format)
    self.assertTrue(
        all(values[i]["created_at"] >= values[i + 1]["created_at"]
            for i in range(count - 1))
    )

  def test_created_at_filtering(self):
    """Test revision could be filtered by created_at."""
    with freeze_time("2019-01-08 12:00:00"):
      control = factories.ControlFactory()
      control_id = control.id
      factories.RevisionFactory(obj=control)

    expected_ids = set()
    with freeze_time("2019-01-08 23:59:59"):
      rev = factories.RevisionFactory(obj=control)
      expected_ids.add(rev.id)

    self.client.get("/login")
    resp = self._get_first_result_set(
        {
            "object_name": "Revision",
            "type": "ids",
            "filters": {
                "expression": {
                    "op": {"name": "AND"},
                    "left": {
                        "op": {"name": "AND"},
                        "left": {
                            "op": {"name": "="},
                            "left": "resource_type",
                            "right": "Control"
                        },
                        "right": {
                            "op": {"name": "="},
                            "left": "resource_id",
                            "right": control_id
                        }
                    },
                    "right": {
                        "op": {"name": ">"},
                        "left": "created_at",
                        "right": "2019-01-08 12:00:00"
                    }
                }
            }
        },
        "Revision",
        "ids"
    )
    self.assertItemsEqual(resp, expected_ids)

  def test_populated_automapping(self):
    """Test automapping content in revision"""
    with factories.single_commit():
      program_a = factories.ProgramFactory()
      program_b = factories.ProgramFactory()
      factories.RelationshipFactory(source=program_b,
                                    destination=program_a)
      regulation_a = factories.RegulationFactory()

    program_a_id = program_a.id
    program_b_id = program_b.id
    regulation_a_id = regulation_a.id
    self.gen.generate_relationship(regulation_a, program_a)
    rel_1 = all_models.Relationship.query.filter_by(
        source_type="Regulation",
        source_id=regulation_a_id,
        destination_type="Program",
        destination_id=program_b_id
    ).first()
    rel_2 = all_models.Relationship.query.filter_by(
        source_type="Program",
        source_id=program_b_id,
        destination_type="Regulation",
        destination_id=regulation_a_id
    ).first()
    relationship = rel_1 or rel_2
    revision = all_models.Revision.query.filter_by(
        resource_type="Relationship",
        resource_id=relationship.id
    ).first()
    automapping = revision.content["automapping"]
    nodes = {automapping["source_type"]: automapping["source_id"],
             automapping["destination_type"]: automapping["destination_id"]}
    self.assertTrue(program_a_id == nodes["Program"])
    self.assertTrue(regulation_a_id == nodes["Regulation"])
