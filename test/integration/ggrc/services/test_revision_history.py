# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for revision history api."""

import random
import json

import ddt
import sqlalchemy as sa

from ggrc.models import all_models
from ggrc import db

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories

from appengine import base


@ddt.ddt
@base.with_memcache
class TestRevisionHistory(TestCase):
  """Test checks permissions for revision history."""

  def setUp(self):
    super(TestRevisionHistory, self).setUp()
    self.api = Api()
    roles = {r.name: r for r in all_models.Role.query.all()}

    with factories.single_commit():
      factories.AccessControlRoleFactory(
          name="ACL_Reader",
          object_type="Control",
          update=0,
      )
      factories.AccessControlRoleFactory(
          name="ACL_Editor",
          object_type="Control"
      ),

    with factories.single_commit():
      self.control = factories.ControlFactory()
      self.program = factories.ProgramFactory()
      self.program.context.related_object = self.program
      self.relationship = factories.RelationshipFactory(
          source=self.program,
          destination=self.control,
          context=self.program.context,
      )
      self.people = {
          "Creator": factories.PersonFactory(),
          "Reader": factories.PersonFactory(),
          "Editor": factories.PersonFactory(),
          "Administrator": factories.PersonFactory(),
          "ACL_Reader": factories.PersonFactory(),
          "ACL_Editor": factories.PersonFactory(),
          "Program Editors": factories.PersonFactory(),
          "Program Managers": factories.PersonFactory(),
          "Program Readers": factories.PersonFactory(),
      }
      for role_name in ["Creator", "Reader", "Editor", "Administrator"]:
        rbac_factories.UserRoleFactory(role=roles[role_name],
                                       person=self.people[role_name])
      for role_name in ["Program Editors",
                        "Program Managers",
                        "Program Readers"]:
        person = self.people[role_name]
        rbac_factories.UserRoleFactory(role=roles["Creator"], person=person)
        factories.AccessControlPersonFactory(
            ac_list=self.program.acr_name_acl_map[role_name],
            person=self.people[role_name],
        )
    with factories.single_commit():
      for role_name in ["ACL_Reader", "ACL_Editor"]:
        rbac_factories.UserRoleFactory(role=roles["Creator"],
                                       person=self.people[role_name])
        factories.AccessControlPersonFactory(
            ac_list=self.control.acr_name_acl_map[role_name],
            person=self.people[role_name],
        )

  @ddt.data(
      ("Creator", True),
      ("Reader", False),
      ("Editor", False),
      ("ACL_Reader", False),
      ("ACL_Editor", False),
      ("Administrator", False),
      ("Program Editors", False),
      ("Program Managers", False),
      ("Program Readers", False),
  )
  @ddt.unpack
  def test_get(self, role_name, empty):
    """Test get revision history for {0}."""
    control_id = self.control.id
    query = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control_id,
        all_models.Revision.resource_type == self.control.type,
    )
    if empty:
      ids = []
    else:
      ids = [i.id for i in query]
    self.api.set_user(self.people[role_name])
    self.client.get("/login")
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type=Control&resource_id={}".format(control_id)
    )
    self.assertEqual(
        ids,
        [i["id"] for i in resp.json["revisions_collection"]["revisions"]])

  def update_revisions(self, obj):
    """Assert revision diff between api and calculated in test.."""
    query = all_models.Revision.query.filter(
        all_models.Revision.resource_id == obj.id,
        all_models.Revision.resource_type == obj.type,
    ).order_by(
        sa.desc(all_models.Revision.updated_at)
    )
    diffs = [(i.id, json.loads(json.dumps(i.diff_with_current())))
             for i in query]
    for i in range(3):
      resp = self.api.client.get(
          "/api/revisions"
          "?__sort=-updated_at"
          "&resource_type={}"
          "&resource_id={}"
          "&_={}".format(
              obj.type,
              obj.id,
              random.randint(1100000000, 1153513123412)
          )
      )
      resp_diffs = [(i["id"], i["diff_with_current"])
                    for i in resp.json["revisions_collection"]["revisions"]]
      self.assertDictEqual(dict(diffs), dict(resp_diffs))
    self.assertFalse(any(resp_diffs[0][1].values()))

  def test_control_memcache(self):
    """Test get updated control revisions."""
    control_id = self.control.id
    self.api.put(self.control, {"title": "new_title"})
    self.control = all_models.Control.eager_query().get(control_id)
    self.update_revisions(self.control)
    db.session.expire_all()
    self.control = all_models.Control.eager_query().get(control_id)
    self.api.put(self.control, {"description": "new test description BLA"})
    self.control = all_models.Control.eager_query().get(control_id)
    self.update_revisions(self.control)
    self.api.put(self.control, {"description": "bla bla bla"})
    self.control = all_models.Control.eager_query().get(control_id)
    self.update_revisions(self.control)

  def test_risk_memcache(self):
    """Test get updated risk revisions."""
    risk = factories.RiskFactory()
    risk_id = risk.id
    self.api.put(risk, {"title": "new_title"})
    self.update_revisions(risk)
    db.session.expire_all()
    risk = all_models.Risk.eager_query().get(risk_id)
    self.api.put(risk, {"description": "new test description BLA"})
    risk = all_models.Risk.eager_query().get(risk_id)
    self.update_revisions(risk)
    risk = all_models.Risk.eager_query().get(risk_id)
    self.api.put(risk, {"description": "BLA bla bla"})
    risk = all_models.Risk.eager_query().get(risk_id)
    self.update_revisions(risk)

  def test_change_log(self):
    """Test Change log where CAV attribute_object_id is str in revision
     content"""
    person = factories.PersonFactory()
    cad = factories.CustomAttributeDefinitionFactory(
        definition_type="control",
        definition_id=None,
        attribute_type="Map:Person",
        title="Global Person CA",
    )
    factories.CustomAttributeValueFactory(
        attributable=self.control,
        custom_attribute=cad,
        attribute_value=person.type,
        attribute_object_id=str(person.id),
    )
    self.api.put(self.control, {"title": "new_title"})
    control = all_models.Control.eager_query().get(self.control.id)
    self.update_revisions(control)

  @ddt.data(True, False)
  def test_get_mandatory_acrs(self, mandatory):
    """ACR and mandatory meta info if mandatory flag is {0}."""
    control_id = self.control.id
    acr = factories.AccessControlRoleFactory(name="test_name",
                                             object_type=self.control.type,
                                             mandatory=mandatory)
    acr_id = acr.id
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type=Control&resource_id={}".format(control_id)
    )
    collection = resp.json["revisions_collection"]["revisions"]
    self.assertTrue(collection)
    self.assertIn("meta", collection[0])
    self.assertIn("mandatory", collection[0]["meta"])
    self.assertIn("access_control_roles", collection[0]["meta"]["mandatory"])
    mandatory_acrs = collection[0]["meta"]["mandatory"]["access_control_roles"]
    self.assertEqual(mandatory, acr_id in mandatory_acrs)

  @ddt.data(True, False)
  def test_get_mandatory_cads(self, mandatory):
    """CAD and mandatory meta info if mandatory flag is {0}."""
    control_id = self.control.id
    cad = factories.CustomAttributeDefinitionFactory(
        title="test_name",
        definition_type="control",
        mandatory=mandatory)
    cad_id = cad.id
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type=Control&resource_id={}".format(control_id)
    )
    collection = resp.json["revisions_collection"]["revisions"]
    self.assertTrue(collection)
    self.assertIn("meta", collection[0])
    self.assertIn("mandatory", collection[0]["meta"])
    mandatory_meta = collection[0]["meta"]["mandatory"]
    self.assertIn("custom_attribute_definitions", mandatory_meta)
    mandatory_cads = mandatory_meta["custom_attribute_definitions"]
    self.assertEqual(mandatory, cad_id in mandatory_cads)

  @ddt.data(
      {"factory": factories.ControlFactory,
       "fields": ['test_plan', 'status', 'notes',
                  'description', 'title', 'slug', 'folder']},
      {"factory": factories.RiskFactory,
       "fields": ['test_plan', 'status', 'description', 'external_id',
                  'notes', 'title', 'slug', 'folder']},
  )
  @ddt.unpack
  def test_get_mandatory_fields(self, factory, fields):
    """Fields mandatory meta info for {factory._meta.model}."""
    instance = factory()
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type={}&resource_id={}".format(instance.type, instance.id)
    )
    collection = resp.json["revisions_collection"]["revisions"]
    self.assertTrue(collection)
    self.assertIn("meta", collection[0])
    self.assertIn("mandatory", collection[0]["meta"])
    mandatory_meta = collection[0]["meta"]["mandatory"]
    self.assertIn("fields", mandatory_meta)
    self.assertItemsEqual(fields, mandatory_meta["fields"])

  @ddt.data(
      {"factory": factories.ControlFactory, "fields": []},
      {"factory": factories.RiskFactory, "fields": []},
      {"factory": factories.AssessmentFactory, "fields": []},
  )
  @ddt.unpack
  def test_mandatory_mapping_list(self, factory, fields):
    """Mapping List mandatory meta info for {factory._meta.model}."""
    instance = factory()
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type={}&resource_id={}".format(instance.type, instance.id)
    )
    collection = resp.json["revisions_collection"]["revisions"]
    self.assertTrue(collection)
    self.assertIn("meta", collection[0])
    self.assertIn("mandatory", collection[0]["meta"])
    mandatory_meta = collection[0]["meta"]["mandatory"]
    self.assertIn("mapping_list_fields", mandatory_meta)
    self.assertEqual(fields, mandatory_meta["mapping_list_fields"])

  @ddt.data(
      {"factory": factories.ControlFactory, "fields": []},
      {"factory": factories.RiskFactory, "fields": []},
      {"factory": factories.AssessmentFactory, "fields": ["audit"]},
  )
  @ddt.unpack
  def test_mandatory_mappings(self, factory, fields):
    """Mapping fields mandatory meta info for {factory._meta.model}."""
    instance = factory()
    resp = self.api.client.get(
        "/api/revisions"
        "?resource_type={}&resource_id={}".format(instance.type, instance.id)
    )
    collection = resp.json["revisions_collection"]["revisions"]
    self.assertTrue(collection)
    self.assertIn("meta", collection[0])
    self.assertIn("mandatory", collection[0]["meta"])
    mandatory_meta = collection[0]["meta"]["mandatory"]
    self.assertIn("mapping_fields", mandatory_meta)
    self.assertEqual(fields, mandatory_meta["mapping_fields"])
