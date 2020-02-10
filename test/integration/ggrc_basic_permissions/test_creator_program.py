# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Test Creator role with Program scoped roles
"""

# pylint: disable=unused-import
from ggrc.app import app  # NOQA
from ggrc import db
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import Generator
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


class TestCreatorProgram(TestCase):
  """Set up necessary objects and test Creator role with Program roles"""

  def setUp(self):
    super(TestCreatorProgram, self).setUp()
    self.generator = Generator()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.init_users()
    self.init_roles()
    self.init_test_cases()
    self.objects = {}

  def init_test_cases(self):
    """ Create a dict of all possible test cases """
    self.test_cases = {
        "notmapped": {
            "objects": {
                "program": {
                    "get": 403,
                    "put": 403,
                    "delete": 403
                },
                "mapped_object": {
                    "get": 403,
                    "put": 403,
                    "delete": 403
                },
                "unrelated": {
                    "get": 403,
                    "put": 403,
                    "delete": 403,
                    "map": 403,
                }
            },
        },
        "mapped": {
            "objects": {
                "program": {
                    "get": 403,
                    "put": 403,
                    "delete": 403
                },
                "mapped_object": {
                    "get": 403,
                    "put": 403,
                    "delete": 403
                },
                "unrelated": {
                    "get": 403,
                    "put": 403,
                    "delete": 403,
                    "map": 403,
                }
            }
        },
        "ProgramReader": {
            "program_role": "Program Readers",
            "objects": {
                "program": {
                    "get": 200,
                    "put": 403,
                    "delete": 403
                },
                "mapped_object": {
                    "get": 200,
                    "put": 403,
                    "delete": 403
                },
                "unrelated": {
                    "get": 403,
                    "put": 403,
                    "delete": 403,
                    "map": 403,
                }
            }
        },
        "ProgramManager": {
            "program_role": "Program Managers",
            "objects": {
                "program": {
                    "get": 200,
                    "put": 200,
                    "delete": 200
                },
                "mapped_object": {
                    "get": 200,
                    "put": 200,
                    "delete": 200,
                },
                "unrelated": {
                    "get": 403,
                    "put": 403,
                    "delete": 403,
                    "map": 403,
                }
            }
        },
        "ProgramEditor": {
            "program_role": "Program Editors",
            "objects": {
                "program": {
                    "get": 200,
                    "put": 200,
                    "delete": 200
                },
                "mapped_object": {
                    "get": 200,
                    "put": 200,
                    "delete": 403
                },
                "unrelated": {
                    "get": 403,
                    "put": 403,
                    "delete": 403,
                    "map": 403,
                }
            }
        },
    }

  def init_roles(self):
    """ Create a delete request for the given object """
    ac_roles = all_models.AccessControlRole.query.all()
    self.ac_roles = {}
    for ac_role in ac_roles:
      self.ac_roles[ac_role.name] = ac_role.id

  def init_users(self):
    """ Create users used by test cases """
    users = [
        ("creator", "Creator"),
        ("notmapped", "Creator"),
        ("mapped", "Creator"),
        ("ProgramReader", "Creator"),
        ("ProgramEditor", "Creator"),
        ("ProgramManager", "Creator")]
    self.people = {}
    for (name, role) in users:
      _, user = self.object_generator.generate_person(
          data={"name": name, "email": name + "@example.com"}, user_role=role)
      self.people[name] = user

  def delete(self, obj):
    """ Create a delete request for the given object """
    return self.api.delete(obj).status_code

  def get(self, obj):
    """ Create a get request for the given object """
    return self.api.get(obj.__class__, obj.id).status_code

  def put(self, obj):
    """ Create a put request for the given object """
    response = self.api.get(obj.__class__, obj.id)
    if response.status_code == 200:
      return self.api.put(obj, response.json).status_code
    return response.status_code

  def map(self, dest):
    """ Map src to dest """
    response = self.api.post(all_models.Relationship, {
        "relationship": {"source": {
            "id": self.objects["program"].id,
            "type": self.objects["program"].type,
        }, "destination": {
            "id": dest.id,
            "type": dest.type
        }, "context": None},
    })
    return response.status_code

  def init_objects(self, test_case_name):
    """ Create a Program and a Mapped object for a given test case """
    # Create a program
    test_case = self.test_cases[test_case_name]
    creator = self.people.get('creator')
    self.api.set_user(creator)
    random_title = factories.random_str()
    person = self.people.get(test_case_name)
    acl = [acl_helper.get_acl_json(self.ac_roles["Program Managers"],
                                   creator.id)]
    if "program_role" in test_case:
      ac_role_id = self.ac_roles[test_case["program_role"]]
      acl.append(acl_helper.get_acl_json(ac_role_id, person.id))
    response = self.api.post(all_models.Program, {
        "program": {
            "title": random_title,
            "context": None,
            "access_control_list": acl
        },
    })
    self.assertEqual(response.status_code, 201, "Creator can't create program")
    context_id = response.json.get("program").get("context").get("id")
    program_id = response.json.get("program").get("id")

    # Use admin owner role to map it with system
    acr_id = all_models.AccessControlRole.query.filter_by(
        object_type="Issue",
        name="Admin"
    ).first().id
    self.objects["program"] = all_models.Program.query.get(program_id)

    # Create an object:
    for obj in ("mapped_object", "unrelated"):
      random_title = factories.random_str()
      response = self.api.post(all_models.Issue, {
          "issue": {
              "title": random_title,
              "context": None,
              "due_date": "2022-01-20",
              "access_control_list": [
                  acl_helper.get_acl_json(acr_id, creator.id)],
          },
      })
      self.assertEqual(response.status_code, 201,
                       "Creator can't create object")
      system_id = response.json.get("issue").get("id")
      self.objects[obj] = all_models.Issue.query.get(system_id)

    # Map Object to Program
    response = self.api.post(all_models.Relationship, {
        "relationship": {"source": {
            "id": program_id,
            "type": "Program"
        }, "destination": {
            "id": self.objects["mapped_object"].id,
            "type": "Issue"
        }, "context": None},
    })
    self.assertEqual(response.status_code, 201,
                     "Creator can't map object to program")

    # Map people to Program:
    if test_case_name != "notmapped":
      person = self.people.get(test_case_name)
      response = self.api.post(all_models.ObjectPerson, {"object_person": {
          "person": {
              "id": person.id,
              "type": "Person",
              "href": "/api/people/{}".format(person.id),
          }, "personable": {
              "type": "Program",
              "href": "/api/programs/{}".format(program_id),
              "id": program_id,
          }, "context": {
              "type": "Context",
              "id": context_id,
              "href": "/api/contexts/{}".format(context_id)
          }}})

  def test_creator_program_roles(self):
    """ Test creator role with all program scoped roles """
    # Check permissions based on test_cases:
    errors = []
    for test_case in self.test_cases:
      self.init_objects(test_case)
      person = self.people.get(test_case)
      objects = self.test_cases.get(test_case).get('objects')
      self.api.set_user(person)
      for obj in ("unrelated", "mapped_object", "program"):
        actions = objects[obj]
        for action in ("map", "get", "put", "delete"):
          # reset sesion:
          db.session.commit()
          if action not in actions:
            continue
          func = getattr(self, action)
          res = func(self.objects[obj])
          if res != actions[action]:
            errors.append(
                "{}: Tried {} on {}, but received {} instead of {}".format(
                    test_case, action, obj, res, actions[action]))
      # Try mapping
    self.assertEqual(errors, [])
