# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=too-many-lines
"""Tests exported csv files"""
from os.path import abspath, dirname, join

import collections
import ddt
from flask.json import dumps

from ggrc import utils
from ggrc.converters import get_exportables
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

  @ddt.data("Assessment", "Issue", "Person", "Audit", "Product")
  def test_custom_attr_cb(self, model):
    """Test if  custom attribute checkbox type has hint for {}."""
    with factories.single_commit():
      factories.CustomAttributeDefinitionFactory(
          definition_type=model.lower(),
          attribute_type="Checkbox",
      )
    data = {
        "export_to": "csv",
        "objects": [{"object_name": model, "fields": "all"}]
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nTRUE\nFALSE", response.data)

  def test_basic_policy_template(self):
    """Tests for basic policy templates."""
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Policy", "fields": "all"}]
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)
    self.assertIn("Policy", response.data)

  @ddt.data("Assessment", "Issue", "Person", "Audit", "Product")
  def test_custom_attr_dd(self, model):
    """Test if custom attribute Dropdown type has hint for {}."""
    with factories.single_commit():
      multi_options = "option_1,option_2,option_3"
      factories.CustomAttributeDefinitionFactory(
          definition_type=model.lower(),
          attribute_type="Dropdown",
          multi_choice_options=multi_options,
      )
    data = {
        "export_to": "csv",
        "objects": [{"object_name": model, "fields": "all"}]
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format(
        multi_options.replace(',', '\n')), response.data)

  def test_multiple_empty_objects(self):
    """Tests for multiple empty objects"""
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

  @ddt.data("Program", "Regulation", "Objective", "Contract",
            "Policy", "Standard", "Threat", "Requirement")
  def test_empty_template_columns(self, object_name):
    """Test review state/reviewers not exist in empty template"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": object_name, "fields": "all"},
        ],
    }

    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)
    self.assertIn(object_name, response.data)
    self.assertNotIn("Review State", response.data)
    self.assertNotIn("Reviewers", response.data)

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

  @ddt.data("Process", "System")
  def test_network_zone_tip(self, model):
    """Tests if Network Zone column has tip message in export file for {}"""

    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        all_models.SystemOrProcess.NZ_OPTIONS)), response.data)

  @ddt.data("Assessment", "Issue")
  def test_delete_tip_in_export_csv(self, model):
    """Tests if delete column has tip message in export file for {}"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed value is:\nYes", response.data)

  @ddt.data("Assessment", "Issue")
  def test_ga_tip_people_type(self, model):
    """Tests if Predefined GA of people type  has tip message for {}"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn(u"Multiple values are allowed.\nDelimiter is"
                  u" 'line break'.\nAllowed values are emails", response.data)

  def test_conclusion_tip(self):
    """Tests if design and operationally are with tip in export file."""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Assessment", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        all_models.Assessment.VALID_CONCLUSIONS)), response.data)

  @ddt.data("Assessment", "Audit")
  def test_archived_tip(self, model):
    """Tests if Archived column has tip message for {}. """
    data = {
        "export_to": "csv",
        "objects": [
           {"object_name": model, "fields": "all"},

        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nyes\nno", response.data)

  def test_assessment_type_tip(self):
    """Tests if Assessment type column has tip message for Assessment."""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Assessment", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        all_models.Assessment.ASSESSMENT_TYPE_OPTIONS)), response.data)

  def test_role_tip(self):
    """Tests if Role column has tip message in export file (People Object)."""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Person", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are\n{}".format('\n'.join(
        all_models.Person.ROLE_OPTIONS)), response.data)

  def test_kind_tip(self):
    """Tests if Kind/Type column has tip message in export file"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Product", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)

    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        all_models.Product.TYPE_OPTIONS)), response.data)

  def test_f_realtime_email_updates(self):
    """Tests if Force real-time email updates column has tip message. """
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Workflow", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nYes\nNo", response.data)

  def test_need_verification_tip(self):
    """Tests if Need Verification column has tip message in export file. """
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Workflow", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("This field is not changeable\nafter workflow activation."
                  "\nAllowed values are:\nTRUE\nFALSE", response.data)


@ddt.ddt
class TestExportSingleObject(TestCase):
  """Test case for export single object."""

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

  @ddt.data(
      ("Program", factories.ProgramFactory),
      ("Regulation", factories.RegulationFactory),
      ("Objective", factories.ObjectiveFactory),
      ("Contract", factories.ContractFactory),
      ("Policy", factories.PolicyFactory),
      ("Standard", factories.StandardFactory),
      ("Threat", factories.ThreatFactory),
      ("Requirement", factories.RequirementFactory),
  )
  @ddt.unpack
  def test_reviewable_object_columns(self, object_name, object_factory):
    """Test review state/reviewers exist export file"""
    obj = object_factory()
    data = [{
        "object_name": object_name,
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": obj.title,
            },
        },
        "fields": "all",
    }]
    response = self.export_csv(data)

    self.assertEqual(response.status_code, 200)
    self.assertIn("Title*", response.data)
    self.assertIn(object_name, response.data)
    self.assertIn(obj.title, response.data)
    self.assertIn("Review State", response.data)
    self.assertIn("Reviewers", response.data)

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
    """Test program audit relevant query"""
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
    """Test multiple relevant query"""
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
    """Tests query for all aliases"""
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
    for model in set(get_exportables().values()):
      for attr, field in AttributeInfo(model)._aliases.items():
        if field is None:
          continue
        try:
          field = field["display_name"] if isinstance(field, dict) else field
          res = self.export_csv(data(model, attr, field))
          self.assertEqual(res.status_code, 200)
        except Exception as err:
          failed.add((model, attr, field, err))
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


@ddt.ddt
class TestExportPerformance(TestCase):
  """Test performance of export."""

  def setUp(self):
    super(TestExportPerformance, self).setUp()
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }
    self.client.get("/login")

  @ddt.data(
      ("Assessment", 21),
      ("Issue", 25),
  )
  @ddt.unpack
  def test_export_query_count(self, model_name, query_limit):
    """Test query count during export of {0}."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      model_factory = factories.get_model_factory(model_name)
      for _ in range(3):
        model_factory(audit=audit)
    data = [{
        "object_name": model_name,
        "filters": {
            "expression": {},
        },
        "fields": "all",
    }]
    with utils.QueryCounter() as counter:
      response = self.export_parsed_csv(data)
      self.assertNotEqual(counter.get, 0)
      self.assertLessEqual(counter.get, query_limit)
    self.assertEqual(len(response[model_name]), 3)

  @ddt.data(
      ("Assessment", ["Objective", "Market"], 21),
      ("Issue", ["Objective", "Risk", "System"], 25),
  )
  @ddt.unpack
  def test_with_snapshots_query_count(self, model_name, snapshot_models,
                                      query_limit):
    """Test query count during export of {0} with mapped {1} snapshots."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      snap_objects = []
      for snap_model in snapshot_models:
        snap_objects.append(factories.get_model_factory(snap_model)())
      snapshots = self._create_snapshots(audit, snap_objects)

      model_factory = factories.get_model_factory(model_name)
      for _ in range(3):
        obj = model_factory(audit=audit)
        for snapshot in snapshots:
          factories.RelationshipFactory(source=obj, destination=snapshot)

    data = [{
        "object_name": model_name,
        "filters": {
            "expression": {},
        },
        "fields": "all",
    }]
    with utils.QueryCounter() as counter:
      response = self.export_parsed_csv(data)
      self.assertNotEqual(counter.get, 0)
      self.assertLessEqual(counter.get, query_limit)
    self.assertEqual(len(response[model_name]), 3)
