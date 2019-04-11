# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

from os.path import abspath, dirname, join

import collections
import ddt
from flask.json import dumps

from ggrc.converters import get_importables
from ggrc.models import inflector, all_models
from ggrc.models.reflection import AttributeInfo
from integration.ggrc import TestCase
from integration.ggrc.models import factories

THIS_ABS_PATH = abspath(dirname(__file__))
CSV_DIR = join(THIS_ABS_PATH, 'test_csvs/')


@ddt.ddt
class TestExportEmptyTemplate(TestCase):
  """Tests for export of import templates."""

  TICKET_TRACKER_FIELDS = ["Ticket Tracker", "Component ID",
                           "Ticket Tracker Integration", "Hotlist ID",
                           "Priority", "Severity", "Ticket Title",
                           "Issue Type"]

  def setUp(self):
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_basic_policy_template(self):
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Policy", "fields": "all"}]
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)
    self.assertIn("Policy", response.data)

  def test_multiple_empty_objects(self):
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Policy", "fields": "all"},
            {"object_name": "Regulation", "fields": "all"},
            {"object_name": "Requirement", "fields": "all"},
            {"object_name": "OrgGroup", "fields": "all"},
            {"object_name": "Contract", "fields": "all"},
        ],
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)
    self.assertIn("Policy", response.data)
    self.assertIn("Regulation", response.data)
    self.assertIn("Contract", response.data)
    self.assertIn("Requirement", response.data)
    self.assertIn("Org Group", response.data)

  @ddt.data("Assessment", "Issue")
  def test_ticket_tracker_field_order(self, model):
    """Tests if Ticket Tracker fields come before mapped objects for {}."""

    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)

    first_mapping_field_pos = response.data.find("map:")

    for field in self.TICKET_TRACKER_FIELDS:
      self.assertLess(response.data.find(field), first_mapping_field_pos)

  @ddt.data("Assessment", "Issue")
  def test_ticket_tracker_fields(self, model):
    """Tests if Ticket Tracker fields are in export file for {}"""

    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)

    for field in self.TICKET_TRACKER_FIELDS:
      self.assertIn(field, response.data)


class TestExportSingleObject(TestCase):

  def setUp(self):
    super(TestExportSingleObject, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_simple_export_query(self):
    """Test simple export query."""
    response = self._import_file("data_for_export_testing_program.csv")
    self._check_csv_response(response, {})
    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": "Cat ipsum 1",
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)
    expected = set([1])
    for i in range(1, 24):
      if i in expected:
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "~"},
                "right": "1",
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)
    expected = set([1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21])
    for i in range(1, 24):
      if i in expected:
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

  def test_and_export_query(self):
    """Test export query with AND clause."""
    response = self._import_file("data_for_export_testing_program.csv")
    self._check_csv_response(response, {})
    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": {
                    "left": "title",
                    "op": {"name": "!~"},
                    "right": "2",
                },
                "op": {"name": "AND"},
                "right": {
                    "left": "title",
                    "op": {"name": "~"},
                    "right": "1",
                },
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    expected = set([1, 10, 11, 13, 14, 15, 16, 17, 18, 19])
    for i in range(1, 24):
      if i in expected:
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

  def test_simple_relevant_query(self):
    """Test simple relevant query"""
    self.import_file("data_for_export_testing_program_contract.csv")
    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Contract",
                "slugs": ["contract-25", "contract-40"],
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    expected = set([1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 14, 16])
    for i in range(1, 24):
      if i in expected:
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

  def test_program_audit_relevant_query(self):
    response = self._import_file("data_for_export_testing_program_audit.csv")
    self._check_csv_response(response, {})
    data = [{  # should return just program prog-1
        "object_name": "Program",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Audit",
                "slugs": ["au-1"],
            },
        },
        "fields": "all",
    }, {  # Audits : au-1, au-3, au-5, au-7,
        "object_name": "Audit",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "__previous__",
                "ids": ["0"],
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    self.assertIn(",Cat ipsum 1,", response.data)
    expected = set([1, 3, 5, 7])
    for i in range(1, 14):
      if i in expected:
        self.assertIn(",Audit {},".format(i), response.data)
      else:
        self.assertNotIn(",Audit {},".format(i), response.data)

  def test_requirement_policy_relevant_query(self):
    """Test requirement policy relevant query"""
    response = self._import_file("data_for_export_testing_directives.csv")
    self._check_csv_response(response, {})
    data = [{  # sec-1
        "object_name": "Requirement",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Policy",
                "slugs": ["p1"],
            },
        },
        "fields": "all",
    }, {  # p3
        "object_name": "Policy",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Requirement",
                "slugs": ["sec-3"],
            },
        },
        "fields": "all",
    }, {  # sec-8
        "object_name": "Requirement",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Standard",
                "slugs": ["std-1"],
            },
        },
        "fields": "all",
    }, {  # std-3
        "object_name": "Standard",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Requirement",
                "slugs": ["sec-10"],
            },
        },
        "fields": "all",
    }, {  # sec-5
        "object_name": "Requirement",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Regulation",
                "slugs": ["reg-2"],
            },
        },
        "fields": "all",
    }, {  # reg-1
        "object_name": "Regulation",
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "Requirement",
                "slugs": ["sec-4"],
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    titles = [",mapped section {},".format(i) for i in range(1, 11)]
    titles.extend([",mapped reg {},".format(i) for i in range(1, 11)])
    titles.extend([",mapped policy {},".format(i) for i in range(1, 11)])
    titles.extend([",mapped standard {},".format(i) for i in range(1, 11)])

    expected = set([
        ",mapped section 1,",
        ",mapped section 5,",
        ",mapped section 8,",
        ",mapped reg 1,",
        ",mapped standard 3,",
        ",mapped policy 3,",
    ])

    for title in titles:
      if title in expected:
        self.assertIn(title, response.data, "'{}' not found".format(title))
      else:
        self.assertNotIn(title, response.data, "'{}' was found".format(title))

  def test_multiple_relevant_query(self):
    response = self._import_file(
        "data_for_export_testing_program_policy_contract.csv")
    self._check_csv_response(response, {})
    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": {
                    "op": {"name": "relevant"},
                    "object_name": "Policy",
                    "slugs": ["policy-3"],
                },
                "op": {"name": "AND"},
                "right": {
                    "op": {"name": "relevant"},
                    "object_name": "Contract",
                    "slugs": ["contract-25", "contract-40"],
                },
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    expected = set([1, 2, 4, 8, 10, 11, 13])
    for i in range(1, 24):
      if i in expected:
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

  def test_query_all_aliases(self):
    def rhs(model, attr):
      attr = getattr(model, attr, None)
      if attr is not None and hasattr(attr, "_query_clause_element"):
        class_name = attr._query_clause_element().type.__class__.__name__
        if class_name == "Boolean":
          return "1"
      return "1/1/2015"

    def data(model, attr, field):
      return [{
          "object_name": model.__name__,
          "fields": "all",
          "filters": {
              "expression": {
                  "left": field.lower(),
                  "op": {"name": "="},
                  "right": rhs(model, attr)
              },
          }
      }]

    failed = set()
    for model in set(get_importables().values()):
      for attr, field in AttributeInfo(model)._aliases.items():
        if field is None:
          continue
        try:
          field = field["display_name"] if type(field) is dict else field
          res = self.export_csv(data(model, attr, field))
          self.assertEqual(res.status_code, 200)
        except Exception as e:
          failed.add((model, attr, field, e))
    self.assertEqual(sorted(failed), [])


@ddt.ddt
class TestExportMultipleObjects(TestCase):

  def setUp(self):
    super(TestExportMultipleObjects, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_simple_multi_export(self):
    """Test basic import of multiple objects"""
    match = 1
    with factories.single_commit():
      programs = [factories.ProgramFactory().title for i in range(3)]
      regulations = [factories.RegulationFactory().title for i in range(3)]

    data = [{
        "object_name": "Program",  # prog-1
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": programs[match]
            },
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",  # regulation-9000
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": regulations[match]
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)
    for i in range(3):
      if i == match:
        self.assertIn(programs[i], response.data)
        self.assertIn(regulations[i], response.data)
      else:
        self.assertNotIn(programs[i], response.data)
        self.assertNotIn(regulations[i], response.data)

  def test_exportable_items(self):
    """Test multi export with exportable items."""
    with factories.single_commit():
      program = factories.ProgramFactory()
      regulation = factories.RegulationFactory()

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": program.title
            },
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": regulation.title
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(
        data,
        exportable_objects=[1]
    )
    response_data = response.data
    self.assertIn(regulation.title, response_data)
    self.assertNotIn(program.title, response_data)

  def test_exportable_items_incorrect(self):
    """Test export with exportable items and incorrect index"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      regulation = factories.RegulationFactory()

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": program.title
            },
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": regulation.title
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(
        data,
        exportable_objects=[3]
    )
    response_data = response.data
    self.assertEquals(response_data, "")

  def test_relevant_to_previous_export(self):
    """Test relevant to previous export"""
    res = self._import_file("data_for_export_testing_relevant_previous.csv")
    self._check_csv_response(res, {})
    data = [{
        "object_name": "Program",  # prog-1, prog-23
        "filters": {
            "expression": {
                "left": {
                    "left": "title",
                    "op": {"name": "="},
                    "right": "cat ipsum 1"
                },
                "op": {"name": "OR"},
                "right": {
                    "left": "title",
                    "op": {"name": "="},
                    "right": "cat ipsum 23"
                },
            },
        },
        "fields": ["slug", "title", "description"],
    }, {
        "object_name": "Contract",  # contract-25, contract-27, contract-47
        "filters": {
            "expression": {
                "op": {"name": "relevant"},
                "object_name": "__previous__",
                "ids": ["0"],
            },
        },
        "fields": ["slug", "title", "description"],
    }, {
        "object_name": "Product",  # product-3, product-4, product-5
        "filters": {
            "expression": {
                "left": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": ["0"],
                },
                "op": {"name": "AND"},
                "right": {
                    "left": {
                        "left": "code",
                        "op": {"name": "!~"},
                        "right": "1"
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "left": "code",
                        "op": {"name": "!~"},
                        "right": "2"
                    },
                },
            },
        },
        "fields": ["slug", "title", "description"],
    }, {
        "object_name": "Policy",  # policy - 3, 4, 5, 6, 15, 16
        "filters": {
            "expression": {
                "left": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": ["0"],
                },
                "op": {"name": "AND"},
                "right": {
                    "op": {"name": "relevant"},
                    "object_name": "__previous__",
                    "ids": ["2"],
                },
            },
        },
        "fields": ["slug", "title", "description"],
    }
    ]
    response = self.export_csv(data)

    # programs
    for i in range(1, 24):
      if i in (1, 23):
        self.assertIn(",Cat ipsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Cat ipsum {},".format(i), response.data)

    # contracts
    for i in range(5, 121, 5):
      if i in (5, 15, 115):
        self.assertIn(",con {},".format(i), response.data)
      else:
        self.assertNotIn(",con {},".format(i), response.data)

    # product
    for i in range(115, 140):
      if i in (117, 118, 119):
        self.assertIn(",Startupsum {},".format(i), response.data)
      else:
        self.assertNotIn(",Startupsum {},".format(i), response.data)

    # policies
    for i in range(5, 25):
      if i in (7, 8, 9, 10, 19, 20):
        self.assertIn(",Cheese ipsum ch {},".format(i), response.data)
      else:
        self.assertNotIn(",Cheese ipsum ch {},".format(i), response.data)

  @ddt.data(
      "Assessment",
      "Policy",
      "Regulation",
      "Standard",
      "Contract",
      "Requirement",
      "Objective",
      "Product",
      "System",
      "Process",
      "Access Group",
      "Data Asset",
      "Facility",
      "Market",
      "Org Group",
      "Project",
      "Vendor",
      "Risk Assessment",
      "Threat",
      "Key Report",
      "Account Balance",
  )
  def test_asmnt_procedure_export(self, model):
    """Test export of Assessment Procedure. {}"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      audit = factories.AuditFactory(program=program)
    import_queries = []
    for i in range(3):
      import_queries.append(collections.OrderedDict([
          ("object_type", model),
          ("Assessment Procedure", "Procedure-{}".format(i)),
          ("Title", "Title {}".format(i)),
          ("Code*", "{}-{}".format(model, i)),
          ("Admin", "user@example.com"),
          ("Assignees", "user@example.com"),
          ("Creators", "user@example.com"),
          ("Description", "{} description".format(model)),
          ("Program", program.slug),
          ("Audit", audit.slug),
          ("Start Date", "01/02/2019"),
          ("End Date", "03/03/2019"),
      ]))
      if model.replace(" ", "") in all_models.get_scope_model_names():
        import_queries[-1]["Assignee"] = "user@example.com"
        import_queries[-1]["Verifier"] = "user@example.com"

    self.check_import_errors(self.import_data(*import_queries))

    model_cls = inflector.get_model(model)
    objects = model_cls.query.order_by(model_cls.test_plan).all()
    self.assertEqual(len(objects), 3)
    for num, obj in enumerate(objects):
      self.assertEqual(obj.test_plan, "Procedure-{}".format(num))

    obj_dicts = [
        {
            "Code*": obj.slug,
            "Assessment Procedure": "Procedure-{}".format(i)
        } for i, obj in enumerate(objects)
    ]
    search_request = [{
        "object_name": model_cls.__name__,
        "filters": {
            "expression": {},
            "order_by": {"name": "id"}
        },
        "fields": ["slug", "test_plan"],
    }]
    exported_data = self.export_parsed_csv(search_request)[model]
    self.assertEqual(exported_data, obj_dicts)
