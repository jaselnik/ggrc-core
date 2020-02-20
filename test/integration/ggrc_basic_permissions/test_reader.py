# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Test Reader role
"""
import ddt

from ggrc import db
from ggrc.models import get_model
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import factories
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import ObjectGenerator


@ddt.ddt
class TestReader(TestCase):
  """Test reader role."""

  def setUp(self):
    super(TestReader, self).setUp()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.init_users()

  def init_users(self):
    """ Init users needed by the test cases """
    users = [("reader", "Reader"),
             ("admin", "Administrator"),
             ("creator", "Creator")]
    self.users = {}
    for (name, role) in users:
      _, user = self.object_generator.generate_person(
          data={"name": name}, user_role=role)
      self.users[name] = user

    self.users["external"] = self.object_generator.generate_person(
        data={"email": "external_app@example.com"})[1]

  def test_admin_page_access(self):
    """Only admin can use admin requirement"""
    for role, code in (("reader", 403), ("admin", 200)):
      self.api.set_user(self.users[role])
      self.assertEqual(self.api.client.get("/admin").status_code, code)

  def test_reader_can_crud(self):
    """ Test Basic create/read,update/delete operations """
    self.api.set_user(self.users["reader"])
    all_errors = []
    base_models = set(["Regulation", "Standard", "Document"])

    for model_singular in base_models:
      try:
        model = get_model(model_singular)
        table_singular = model._inflector.table_singular
        table_plural = model._inflector.table_plural
        # Test POST creation
        response, _ = self.object_generator.generate_object(
            model,
            data={
                table_singular: {
                    "title": model_singular,
                    "context": None,
                    "documents_reference_url": "ref",
                    "link": "https://example.com",  # only for Document
                    "contact": {
                        "type": "Person",
                        "id": self.users["reader"].id,
                    }
                },
            }
        )

        if response.status_code != 201:
          all_errors.append("{} post creation failed {} {}".format(
              model_singular, response.status, response.data))
          continue

        obj_id = response.json.get(table_singular).get("id")

        # Test GET when owner
        response = self.api.get(model, obj_id)
        if response.status_code != 200:
          all_errors.append("{} can't GET object {}".format(
              model_singular, response.status))
          continue

        # Test GET collection when owner
        response = self.api.get_collection(model, obj_id)
        collection = response.json.get(
            "{}_collection".format(table_plural)).get(table_plural)
        if not collection:
          all_errors.append(
              "{} cannot retrieve object even if owner (collection)".format(
                  model_singular))
          continue
      except:
        all_errors.append("{} exception thrown".format(model_singular))
        raise
    self.assertEqual(all_errors, [])

  def test_reader_search(self):
    """ Test if reader can see the correct object while using search api """
    with factories.single_commit():
      factories.RegulationFactory()
      factories.PolicyFactory()

    self.api.set_user(self.users["reader"])

    response, _ = self.api.search("Regulation,Policy")
    self.assert200(response)
    # Global Reader has read access to all objects.
    entries = response.json["results"]["entries"]
    self.assertEqual(2, len(entries))

    response, _ = self.api.search("Regulation,Policy", counts=True)
    self.assert200(response)
    # Global Reader has read access only to all objects.
    counts = response.json["results"]["counts"]
    self.assertEqual(1, counts.get("Regulation", 1))
    self.assertEqual(1, counts.get("Policy", 1))

  def _get_count(self, obj):
    """ Return the number of counts for the given object from search """
    response, _ = self.api.search(obj, counts=True)
    return response.json["results"]["counts"].get(obj)

  def test_reader_should_see_users(self):
    """ Test if creator can see all the users in the system """
    self.api.set_user(self.users['admin'])
    admin_count = self._get_count("Person")
    self.api.set_user(self.users['reader'])
    reader_count = self._get_count("Person")
    self.assertEqual(admin_count, reader_count)

  def test_relationships_access(self):
    """Check if reader can access relationship objects"""
    self.api.set_user(self.users['admin'])
    _, first_regulation = self.object_generator.generate_object(
        all_models.Regulation,
        data={"regulation": {"title": "Test regulation", "context": None}}
    )
    _, second_regulation = self.object_generator.generate_object(
        all_models.Regulation,
        data={"regulation": {"title": "Test regulation 2", "context": None}}
    )
    response, rel = self.object_generator.generate_relationship(
        first_regulation, second_regulation
    )
    self.assertStatus(response, 201)
    self.api.set_user(self.users['reader'])
    response = self.api.get_collection(all_models.Relationship, rel.id)
    self.assert200(response)
    num = len(response.json["relationships_collection"]["relationships"])
    self.assertEqual(num, 1)

  def test_creation_of_mappings(self):
    """Check if reader can't create mappings"""
    self.object_generator.api.set_user(self.users["external"])
    _, control = self.object_generator.generate_object(
        all_models.Control,
        data={"control": {"title": "Test Control", "context": None}}
    )

    self.object_generator.api.set_user(self.users['reader'])
    _, program = self.object_generator.generate_object(
        all_models.Program,
        data={"program": {"title": "Test Program", "context": None}}
    )

    response, _ = self.object_generator.generate_relationship(
        control, program, program.context
    )
    self.assert403(response)

  @ddt.data("creator", "reader")
  def test_unmap_people(self, user_role):
    """Test that global reader/creator can't unmap people from program"""
    user = self.users[user_role]
    with factories.single_commit():
      program = factories.ProgramFactory()
      mapped_person = factories.ObjectPersonFactory(
          personable=program, person=user, context=program.context
      )
    self.api.set_user(user)
    db.session.add(mapped_person)
    response = self.api.delete(mapped_person)
    self.assert403(response)

  def test_read_evidence_revision(self):
    """Global Read can read Evidence revision content"""
    user = self.users["reader"]
    link = "google.com"
    evidence = factories.EvidenceUrlFactory(link=link)
    evidence_id = evidence.id
    self.api.set_user(user)
    resp = self.api.client.get(
        "/api/revisions?resource_type={}&resource_id={}".format(evidence.type,
                                                                evidence_id))
    rev_content = resp.json["revisions_collection"]["revisions"][0]["content"]
    self.assertTrue(rev_content)
    self.assertEquals(link, rev_content["link"])
