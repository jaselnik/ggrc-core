# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Test Program Creator role
"""
import json

import ddt

from ggrc.models import get_model
from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


@ddt.ddt
class TestCreator(TestCase):
  """ TestCreator """

  def setUp(self):
    super(TestCreator, self).setUp()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.init_users()

  def init_users(self):
    """ Init users needed by the test cases """

    users = [("creator", "Creator"), ("admin", "Administrator")]
    self.users = {}
    for (name, role) in users:
      _, user = self.object_generator.generate_person(
          data={"name": name}, user_role=role)
      self.users[name] = user

  def test_admin_page_access(self):
    """Permissions to admin page."""
    for role, code in (("creator", 403), ("admin", 200)):
      self.api.set_user(self.users[role])
      self.assertEqual(self.api.client.get("/admin").status_code, code)

  def test_creator_can_crud(self):
    """ Test Basic create/read,update/delete operations """
    self.api.set_user(self.users["creator"])
    creator_id = self.users["creator"].id
    audit_id = factories.AuditFactory().id
    all_errors = []
    base_models = {"Regulation", "Standard", "Document"}

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
                    # ignored except for Document
                    "link": "https://example.com",
                    "contact": {
                        "type": "Person",
                        "id": creator_id
                    },
                    # this is ignored on everything but Issues
                    "audit": {
                        "id": audit_id,
                        "type": "Audit",
                    }
                },
            }
        )

        if response.status_code != 201:
          all_errors.append("{} post creation failed {} {}".format(
              model_singular, response.status, response.data))
          continue

        # Test GET when not owner
        obj_id = response.json.get(table_singular).get("id")
        response = self.api.get(model, obj_id)
        if response.status_code != 403:  # we are not onwers yet
          all_errors.append(
              "{} can retrieve object if not owner".format(model_singular))
          continue
        response = self.api.get_collection(model, obj_id)
        collection = response.json.get(
            "{}_collection".format(table_plural)).get(table_plural)
        if collection:
          all_errors.append(
              "{} can retrieve object if not owner (collection)"
              .format(model_singular))
          continue

        # Test GET when owner
        acr = all_models.AccessControlRole.query.filter_by(
            object_type=model_singular,
            name="Admin"
        ).one()
        acl = all_models.AccessControlList.query.filter_by(
            object_id=obj_id,
            object_type=model_singular,
            ac_role=acr,
        ).one()
        factories.AccessControlPersonFactory(
            ac_list=acl,
            person_id=creator_id,
        )

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
              "{} cannot retrieve object even if owner (collection)"
              .format(model_singular))
          continue
      except:
        all_errors.append("{} exception thrown".format(model_singular))
        raise
    self.assertEqual(all_errors, [])

  def test_creator_search(self):
    """Test if creator can see the correct object while using the search api"""
    with factories.single_commit():
      factories.RegulationFactory()
      policy = factories.PolicyFactory()
      policy.add_person_with_role_name(
          self.users["creator"],
          "Admin",
      )

    self.api.set_user(self.users["creator"])

    response, _ = self.api.search("Regulation,Policy")
    self.assert200(response)
    # Global Creator has read access only to Policy object.
    entries = response.json["results"]["entries"]
    self.assertEqual(1, len(entries))
    self.assertEqual("Policy", entries[0]["type"])

    response, _ = self.api.search("Regulation,Policy", counts=True)
    self.assert200(response)
    # Global Creator has read access only to Policy object.
    counts = response.json["results"]["counts"]
    self.assertEqual(1, counts.get("Policy", 1))
    self.assertEqual(0, counts.get("Regulation", 0))

  def _get_count(self, obj):
    """ Return the number of counts for the given object from search """
    response, _ = self.api.search(obj, counts=True)
    return response.json["results"]["counts"].get(obj)

  def test_creator_should_see_users(self):
    """ Test if creator can see all the users in the system """
    self.api.set_user(self.users['admin'])
    admin_count = self._get_count("Person")
    self.api.set_user(self.users['creator'])
    creator_count = self._get_count("Person")
    self.assertEqual(admin_count, creator_count)

  def test_relationships_access(self):
    """Check if creator cannot access relationship objects"""
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
    relationship_id = rel.id
    self.assertEqual(response.status_code, 201)
    self.api.set_user(self.users['creator'])
    response = self.api.get_collection(all_models.Relationship,
                                       relationship_id)
    self.assertEqual(response.status_code, 200)
    num = len(response.json["relationships_collection"]["relationships"])
    self.assertEqual(num, 0)

  def test_revision_access(self):
    """Check if creator can access the right revision objects."""

    def check(obj_type, obj_id, expected):
      """Check that how many revisions of an object current user can see."""
      response = self.api.get_query(
          all_models.Revision,
          "resource_type={}&resource_id={}".format(obj_type, obj_id)
      )
      self.assert200(response)
      self.assertEqual(
          expected,
          len(response.json['revisions_collection']['revisions']),
      )

    with factories.single_commit():
      requirement_1 = factories.RequirementFactory()
      requirement_1.add_person_with_role_name(
          self.users["admin"],
          "Admin",
      )
      requirement_2 = factories.RequirementFactory()
      requirement_2.add_person_with_role_name(
          self.users["creator"],
          "Admin",
      )
      requirement_2_acl = requirement_2.access_control_list[0].acl_item
      factories.RevisionFactory(
          obj=requirement_2_acl,
          content=requirement_2_acl.log_json(),
      )

    requirement_1_id = requirement_1.id
    requirement_2_id = requirement_2.id
    requirement_2_acl_id = requirement_2_acl.id

    self.api.set_user(self.users["creator"])

    # Global Creator has no access to Requirement 1.
    check(requirement_1.type, requirement_1_id, expected=0)
    # Global Creator has access to Requirement 2.
    check(requirement_2.type, requirement_2_id, expected=1)
    # Global Creator has access to Requirement 2 thus to its ACL too.
    check(requirement_2_acl.type, requirement_2_acl_id, expected=1)

  @ddt.data("creator", "admin")
  def test_count_type_in_accordion(self, glob_role):
    """Return count of Persons in DB for side accordion."""
    self.api.set_user(self.users[glob_role])
    ocordion_api_person_count_link = (
        "/search?"
        "q=&types=Program%2CWorkflow_All%2C"
        "Audit%2CAssessment%2CIssue%2CRegulation%2C"
        "Policy%2CStandard%2CContract%2CRequirement%2CControl%2C"
        "Objective%2CPerson%2COrgGroup%2CVendor%2CAccessGroup%2CSystem%2C"
        "Process%2CDataAsset%2CProduct%2CProject%2CFacility%2C"
        "Market%2CRisk%2CThreat&counts_only=true&"
        "extra_columns=Workflow_All%3DWorkflow%2C"
        "Workflow_Active%3DWorkflow%2CWorkflow_Draft%3D"
        "Workflow%2CWorkflow_Inactive%3DWorkflow&contact_id=1&"
        "extra_params=Workflow%3Astatus%3DActive%3BWorkflow_Active"
        "%3Astatus%3DActive%3BWorkflow_Inactive%3Astatus%3D"
        "Inactive%3BWorkflow_Draft%3Astatus%3DDraft"
    )
    resp = self.api.client.get(ocordion_api_person_count_link)
    self.assertIn("Person", resp.json["results"]["counts"])
    self.assertEqual(all_models.Person.query.count(),
                     resp.json["results"]["counts"]["Person"])

  @ddt.data(
      ("/api/revisions?resource_type={}&resource_id={}", 1),
      ("/api/revisions?source_type={}&source_id={}", 0),
      ("/api/revisions?destination_type={}&destination_id={}", 1),
  )
  @ddt.unpack
  def test_changelog_access(self, link, revision_count):
    """Test accessing changelog under GC user who is assigned to object"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      asmnt_id = asmnt.id
      factories.RelationshipFactory(source=audit, destination=asmnt)
      factories.AccessControlPersonFactory(
          ac_list=asmnt.acr_name_acl_map["Verifiers"],
          person=self.users["creator"],
      )

    self.api.set_user(self.users["creator"])
    response = self.api.client.get(link.format("Assessment", asmnt_id))
    self.assert200(response)
    self.assertEqual(
        len(response.json.get("revisions_collection", {}).get("revisions")),
        revision_count
    )

  @staticmethod
  def _query_revisions(api, resource_type, resource_id):
    """Helper function querying revisions related to particular object."""
    return api.send_request(
        api.client.post,
        api_link="/query",
        data=[{
            "object_name": "Revision",
            "type": "ids",
            "filters": {
                "expression": {
                    "left": {
                        "left": {
                            "left": "resource_type",
                            "op": {"name": "="},
                            "right": resource_type,
                        },
                        "op": {"name": "AND"},
                        "right": {
                            "left": "resource_id",
                            "op": {"name": "="},
                            "right": resource_id,
                        },
                    },
                    "op": {"name": "OR"},
                    "right": {
                        "left": {
                            "left": {
                                "left": "source_type",
                                "op": {"name": "="},
                                "right": resource_type,
                            },
                            "op": {"name": "AND"},
                            "right": {
                                "left": "source_id",
                                "op": {"name": "="},
                                "right": resource_id,
                            }
                        },
                        "op": {"name": "OR"},
                        "right": {
                            "left": {
                                "left": "destination_type",
                                "op": {"name": "="},
                                "right": resource_type,
                            },
                            "op": {"name": "AND"},
                            "right": {
                                "left": "destination_id",
                                "op": {"name": "="},
                                "right": resource_id,
                            }
                        }
                    }
                },
            },
        }],
    )

  def test_revision_access_query(self):
    """Test GC assigned to obj can access revisions through query API."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      audit = factories.AuditFactory()
      factories.RelationshipFactory(
          source=audit,
          destination=program,
      )
      factories.AccessControlPersonFactory(
          ac_list=audit.acr_name_acl_map["Auditors"],
          person=self.users["creator"],
      )

    audit_id = audit.id
    self.api.set_user(self.users["creator"])
    response = self._query_revisions(self.api, audit.type, audit_id)

    self.assert200(response)
    self.assertEqual(response.json[0]["Revision"]["count"], 2)

  def test_rev_access_query_no_right(self):
    """Test GC has no access to revisions of objects it has no right on."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      audit = factories.AuditFactory()
      factories.RelationshipFactory(
          source=audit,
          destination=program,
      )

    audit_id = audit.id
    self.api.set_user(self.users["creator"])
    response = self._query_revisions(self.api, audit.type, audit_id)

    self.assert200(response)
    self.assertEqual(response.json[0]["Revision"]["count"], 0)

  @ddt.data(
      ("creator", "creator", 1),
      ("admin", "creator", 0)
  )
  @ddt.unpack
  def test_comment_access_query(self, creator_role, access_role, count):
    """Test possibility to access comments through query API for GC."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      factories.AccessControlPersonFactory(
          ac_list=program.acr_name_acl_map["Program Managers"],
          person=self.users[creator_role],
      )
      comment = factories.CommentFactory(description="Test comment",)
      factories.RelationshipFactory(source=program, destination=comment)

    self.api.set_user(self.users[access_role])
    query_data = [{
        "limit": [0, 5],
        "object_name": all_models.Comment.__name__,
        "order_by": [{"name": "updated_at", "desc": True}],
        "filters": {"expression": {}}
    }]
    headers = {"Content-Type": "application/json", }
    response = self.api.client.post("/query",
                                    data=json.dumps(query_data),
                                    headers=headers)

    self.assert200(response)
    self.assertEqual(response.json[0]["Comment"]["count"], count)
