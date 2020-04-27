# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for integration tests for Relationship."""
import itertools
import json

import ddt

from ggrc import db
from ggrc.models import all_models

from integration.external_app import external_api_helper
from integration.ggrc import TestCase, READONLY_MAPPING_PAIRS, _SCOPING_MODELS
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@ddt.ddt
class TestRelationship(TestCase):
  """Integration test suite for Relationship."""
  # pylint: disable=invalid-name

  def setUp(self):
    """Create a Person, an Assessment, prepare a Relationship json."""
    super(TestRelationship, self).setUp()
    self.api = api_helper.Api()
    self.client.get("/login")
    self.object_generator = ObjectGenerator()
    self.person = factories.PersonFactory()
    self.assessment = factories.AssessmentFactory()

  HEADERS = {
      "Content-Type": "application/json",
      "X-requested-by": "GGRC",
  }
  REL_URL = "/api/relationships"

  @staticmethod
  def build_relationship_json(source, destination, is_external=False):
    """Builds relationship create request json."""
    return json.dumps([{
        "relationship": {
            "source": {"id": source.id, "type": source.type},
            "destination": {"id": destination.id, "type": destination.type},
            "context": {"id": None},
            "is_external": is_external
        }
    }])

  def test_local_user_create_external_relationship(self):
    """Test that local user can't create external relationships"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      comment = factories.CommentFactory()

    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(program, comment, is_external=True),
        headers=self.HEADERS)
    rel = all_models.Relationship.query.first()

    self.assert400(response)
    self.assertIsNone(rel)

  def test_changing_log_on_doc_change(self):
    """Changing object documents should generate new object revision."""
    url_link = u"www.foo.com"
    with factories.single_commit():
      control = factories.ControlFactory()
      url = factories.DocumentReferenceUrlFactory(link=url_link)

    def get_revisions():
      return all_models.Revision.query.filter(
          all_models.Revision.resource_id == control.id,
          all_models.Revision.resource_type == control.type,
      ).order_by(
          all_models.Revision.id.desc()
      ).all()

    # attach an url to a control
    revisions = get_revisions()
    count = len(revisions)
    response = self.client.post(
        self.REL_URL,
        data=self.build_relationship_json(control, url),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])

    # check if a revision was created and contains the attached url
    revisions = get_revisions()
    self.assertEqual(count + 1, len(revisions))
    url_list = revisions[0].content.get("documents_reference_url") or []
    self.assertEqual(1, len(url_list))
    self.assertIn("link", url_list[0])
    self.assertEqual(url_link, url_list[0]["link"])

    # now test whether a new revision is created when url is unmapped
    self.assert200(self.api.delete(relationship))

    revisions = get_revisions()
    self.assertEqual(count + 2, len(revisions))
    url_list = revisions[0].content.get("documents_reference_url") or []
    self.assertEqual(url_list, [])

  def test_relationship_disallowed_type(self):
    """Validation fails when source-destination are snapshottable."""
    audit = factories.AuditFactory()
    snapshottable = factories.ControlFactory()

    ctrl_revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == snapshottable.id,
        all_models.Revision.resource_type == snapshottable.type,
    ).first()
    snapshot = factories.SnapshotFactory(
        parent=audit,
        revision_id=ctrl_revision.id,
        child_type=snapshottable.type,
        child_id=snapshottable.id,
    )

    response = self.client.post(
        self.REL_URL,
        data=self.build_relationship_json(snapshot, snapshottable),
        headers=self.HEADERS
    )

    self.assert400(response)
    self.assertIn("Invalid source-destination types pair for Relationship",
                  response.data)

    response = self.client.post(
        self.REL_URL,
        data=self.build_relationship_json(snapshottable, snapshot),
        headers=self.HEADERS
    )

    self.assert400(response)
    self.assertIn("Invalid source-destination types pair for Relationship",
                  response.data)

  def test_relationship_validation(self):
    """Test validator that forbid creation of Relationship with the same object
    as source and destination"""
    response = self.client.post(
        self.REL_URL,
        data=self.build_relationship_json(self.assessment, self.assessment),
        headers=self.HEADERS)
    self.assert400(response)
    self.assertEqual(response.json[0][1],
                     "The mapping of object on itself is not possible")

  def test_reuse_relationship_on_post_swapped(self):
    """Test relationship is reused for 2nd POST with swapped src/dst"""
    with factories.single_commit():
      p1 = factories.ProgramFactory()
      p2 = factories.ProgramFactory()
      p1_id = p1.id
      p2_id = p2.id
      factories.RelationshipFactory(source=p1, destination=p2)

    resp, r2 = self.object_generator.generate_relationship(
        all_models.Program.query.get(p2_id),
        all_models.Program.query.get(p1_id)
    )

    self.assert200(resp)
    self.assertIsNone(r2)

  def test_reuse_relationship_on_post_not_swapped(self):
    """Test relationship is reused for 2nd POST with not swapped src/dst"""
    with factories.single_commit():
      p1 = factories.ProgramFactory()
      p2 = factories.ProgramFactory()
      p1_id = p1.id
      p2_id = p2.id
      factories.RelationshipFactory(source=p1, destination=p2)

    resp, r2 = self.object_generator.generate_relationship(
        all_models.Program.query.get(p1_id),
        all_models.Program.query.get(p2_id)
    )

    self.assert200(resp)
    self.assertIsNone(r2)

  def test_delete_related_relationship(self):
    """Test internal user delete related relationship on request"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      objective = factories.ObjectiveFactory()
      relationship1 = factories.RelationshipFactory(
          source=program, destination=objective, is_external=False
      )
      relationship1_id = relationship1.id
      relationship2 = factories.RelationshipFactory(
          source=objective, destination=program, is_external=False
      )
      relationship2_id = relationship2.id

    resp = self.api.delete(relationship1)
    self.assert200(resp)

    rel1 = all_models.Relationship.query.get(relationship1_id)
    rel2 = all_models.Relationship.query.get(relationship2_id)
    self.assertIsNone(rel1)
    self.assertIsNone(rel2)


@ddt.ddt
class TestExternalRelationship(TestCase):
  """Integration test suite for External Relationship."""
  # pylint: disable=invalid-name

  def setUp(self):
    """Init API helper"""
    super(TestExternalRelationship, self).setUp()
    self.object_generator = ObjectGenerator()
    self.api = api_helper.Api()
    self.ext_api = external_api_helper.ExternalApiClient()
    with factories.single_commit():
      editor_role = all_models.Role.query.filter(
          all_models.Role.name == "Editor").first()
      self.person_ext = factories.PersonFactory(
          email="external_app@example.com")
      self.person_ext_id = self.person_ext.id
      self.person = factories.PersonFactory(
          email="regular_user@example.com")
      self.person_id = self.person.id
      rbac_factories.UserRoleFactory(
          role=editor_role, person=self.person)

  HEADERS = {
      "Content-Type": "application/json",
      "X-requested-by": "External App",
      "X-ggrc-user": "{\"email\": \"external_app@example.com\"}",
      "X-appengine-inbound-appid": "test_external_app",
  }
  REL_URL = "/api/relationships"

  @staticmethod
  def build_relationship_json(source, destination, is_external=True):
    """Builds relationship create request json."""
    return json.dumps([{
        "relationship": {
            "source": {"id": source.id, "type": source.type},
            "destination": {"id": destination.id, "type": destination.type},
            "context": {"id": None},
            "is_external": is_external
        }
    }])

  @staticmethod
  def create_relationship(source, destination, is_external, user):
    """Creates relationship in database with given params."""
    return factories.RelationshipFactory(
        source=source,
        destination=destination,
        is_external=is_external,
        modified_by_id=user.id,
    )

  def test_create_ext_user_ext_relationship(self):
    """Validation external app user creates external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, True),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])
    self.assertEqual(relationship.source_type, "Product")
    self.assertEqual(relationship.source_id, product.id)
    self.assertEqual(relationship.destination_type, "System")
    self.assertEqual(relationship.destination_id, system.id)
    self.assertTrue(relationship.is_external)
    self.assertEqual(relationship.modified_by_id, self.person_ext.id)
    self.assertIsNone(relationship.parent_id)
    self.assertIsNone(relationship.automapping_id)
    self.assertIsNone(relationship.context_id)

  def test_create_ext_user_reg_relationship(self):
    """Validation external app user creates regular relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ObjectiveFactory()
      system = factories.SystemFactory()
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, False),
        headers=self.HEADERS)
    self.assert400(response)
    self.assertEqual(
        response.json[0],
        [400,
         "You do not have the necessary permissions to "
         "create regular relationships.", ])

  def test_update_ext_user_ext_relationship(self):
    """Validation external app user updates external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      issue = factories.IssueFactory()
      system = factories.SystemFactory()

    self.create_relationship(issue, system, True, self.person_ext)
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(issue, system, True),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])
    self.assertEqual(relationship.source_type, "Issue")
    self.assertEqual(relationship.source_id, issue.id)
    self.assertEqual(relationship.destination_type, "System")
    self.assertEqual(relationship.destination_id, system.id)
    self.assertTrue(relationship.is_external)
    self.assertEqual(relationship.modified_by_id, self.person_ext.id)
    self.assertIsNone(relationship.parent_id)
    self.assertIsNone(relationship.automapping_id)
    self.assertIsNone(relationship.context_id)

  def test_update_ext_user_reg_relationship(self):
    """External app user can update regular relationship."""
    with factories.single_commit():
      issue = factories.IssueFactory()
      system = factories.SystemFactory()
      self.create_relationship(issue, system, False, self.person)
      issue_id = issue.id
      system_id = system.id

    self.api.set_user(self.person_ext)
    issue = all_models.Issue.query.get(issue_id)
    system = all_models.System.query.get(system_id)
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(issue, system, True),
        headers=self.HEADERS)
    self.assert200(response)
    self.assertEqual(
        response.json[0][1]["relationship"]["is_external"], False)

  def test_delete_ext_user_ext_relationship(self):
    """Validation external app user deletes external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      objective = factories.IssueFactory()
      system = factories.SystemFactory()
      rel = self.create_relationship(objective, system, True, self.person_ext)

    response = self.api.delete(rel)
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel.id)
    self.assertIsNone(relationship)

  def test_delete_ext_user_reg_relationship(self):
    """External app user can delete regular relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      objective = factories.IssueFactory()
      system = factories.SystemFactory()

    rel = self.create_relationship(objective, system, False, self.person_ext)
    response = self.api.delete(rel)
    self.assert200(response)

  def test_update_reg_user_ext_relationship(self):
    """Validation regular app user updates external relationship."""
    with factories.single_commit():
      issue = factories.IssueFactory()
      system = factories.SystemFactory()
      self.create_relationship(issue, system, True, self.person_ext)
      issue_id = issue.id
      system_id = system.id

    self.api.set_user(self.person)
    issue = all_models.Issue.query.get(issue_id)
    system = all_models.System.query.get(system_id)
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(issue, system, False),
        headers=self.HEADERS)
    self.assert200(response)

  def test_delete_reg_user_ext_relationship(self):
    """Validation regular user deletes external relationship."""
    with factories.single_commit():
      issue = factories.IssueFactory()
      system = factories.SystemFactory()
      self.create_relationship(issue, system, True, self.person_ext)

    self.api.set_user(self.person)
    rel = all_models.Relationship.query.first()
    response = self.api.delete(rel)
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel.id)
    self.assertIsNone(relationship)

  @ddt.data(*READONLY_MAPPING_PAIRS)
  @ddt.unpack
  def test_local_delete_relationship_scoping_directive(self, model1, model2):
    """Test deletion of relationship between {0.__name__} and {1.__name__}"""

    # Set up relationships
    factory1 = factories.get_model_factory(model1.__name__)
    factory2 = factories.get_model_factory(model2.__name__)
    with factories.single_commit():
      obj1 = factory1()
      obj2 = factory2()
      rel = factories.RelationshipFactory(source=obj1, destination=obj2,
                                          is_external=True)
      rel_id = rel.id

    # check that relationship cannot be deleted by regular user
    self.api.set_user(all_models.Person.query.get(self.person_id))
    relationship = all_models.Relationship.query.get(rel_id)
    response = self.api.delete(relationship)
    self.assert400(response)

  @ddt.data(*itertools.product(_SCOPING_MODELS, (all_models.Issue, )))
  @ddt.unpack
  def test_local_delete_relationship_if_orphan(self, model1, model2):
    """Test deletion of orphan relationship {0.__name__} - {1.__name__}."""
    factory1 = factories.get_model_factory(model1.__name__)
    factory2 = factories.get_model_factory(model2.__name__)
    with factories.single_commit():
      obj1 = factory1()
      obj2 = factory2()
      rel = factories.RelationshipFactory(source=obj1, destination=obj2,
                                          is_external=True)
      rel_id = rel.id

    self.api.set_user(all_models.Person.query.get(self.person_id))
    obj_to_delete = model2.query.first()
    response = self.api.delete(obj_to_delete, obj_to_delete.id)
    self.assert200(response)

    rel_q = all_models.Relationship.query.filter_by(id=rel_id)
    self.assertFalse(db.session.query(rel_q.exists()).scalar())

  @ddt.data(*READONLY_MAPPING_PAIRS)
  @ddt.unpack
  def test_local_create_relationship_scoping_directive(self, model1, model2):
    """Test creation of relationship between {0.__name__} and {1.__name__}"""
    # Set up relationships
    factory1 = factories.get_model_factory(model1.__name__)
    factory2 = factories.get_model_factory(model2.__name__)
    with factories.single_commit():
      obj1 = factory1()
      obj2 = factory2()

      self.object_generator.api.set_user(
          all_models.Person.query.get(self.person_id))

      response, _ = self.object_generator.generate_relationship(
          obj1, obj2, is_external=True)

    self.assert400(response)

  @ddt.data(*READONLY_MAPPING_PAIRS)
  @ddt.unpack
  def test_ext_create_delete_relationship_scoping_directive(
      self, model1, model2
  ):
    """Test ext user and relationship between {0.__name__} and {1.__name__}"""

    # Set up relationships
    factory1 = factories.get_model_factory(model1.__name__)
    factory2 = factories.get_model_factory(model2.__name__)
    with factories.single_commit():
      obj1 = factory1()
      obj2 = factory2()
      rel = factories.RelationshipFactory(source=obj1, destination=obj2)
      rel_id = rel.id

    # check that external relationship can be deleted by external user
    self.api.set_user(all_models.Person.query.get(self.person_ext_id))
    relationship = all_models.Relationship.query.get(rel_id)
    response = self.api.delete(relationship)
    self.assert200(response)
