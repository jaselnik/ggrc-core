# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=too-many-lines
# pylint: disable=too-many-public-methods

"""Tests exported csv files"""

import collections
import ddt

from flask.json import dumps

from ggrc import utils
from ggrc.converters import get_exportables
from ggrc.integrations import constants
from ggrc.models import inflector, all_models
from ggrc.models.mixins import WithNetworkZone
from ggrc.models.reflection import AttributeInfo

from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc.converters import constants as test_constants


def define_op_expr(left_expr, opr, right_expr):
  """Returns op expression"""
  obj = {
      "left": left_expr,
      "op": {"name": opr},
      "right": right_expr,
  }
  return obj


def define_relevant_expr(obj_name, obj_slugs=None, obj_ids=None):
  """Returns relevant op expression"""
  obj = {
      "op": {"name": "relevant"},
      "object_name": obj_name,
  }
  if obj_slugs:
    obj["slugs"] = obj_slugs
  if obj_ids:
    obj["ids"] = obj_ids
  return obj


# pylint: disable=too-many-arguments
def get_related_objects(obj_name, related_obj_name,
                        obj_slugs=None, obj_ids=None):
  """Returns query filter expression"""
  related_objects = {
      "object_name": related_obj_name,
      "filters": {
          "expression": define_relevant_expr(obj_name, obj_slugs, obj_ids),
      },
      "fields": "all",
  }

  return related_objects


def get_object_data(obj_name, obj_code="", contract=None,
                    policy=None, product=None, requirement=None):
  """Returns data object"""
  data = collections.OrderedDict([
      ("object_type", obj_name),
      ("Code", obj_code),
  ])
  if contract:
    data["map:contract"] = contract
  if policy:
    data["map:policy"] = policy
  if product:
    data["map:product"] = product
  if requirement:
    data["map:Requirement"] = requirement
  return data


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

  @ddt.data(("AccessGroup", 4),
            ("AccountBalance", 4),
            ("DataAsset", 4),
            ("Facility", 4),
            ("KeyReport", 4),
            ("Market", 4),
            ("Metric", 4),
            ("OrgGroup", 4),
            ("Process", 4),
            ("Product", 4),
            ("ProductGroup", 4),
            ("Project", 4),
            ("System", 4),
            ("TechnologyEnvironment", 4),
            ("Vendor", 4),
            ("Threat", 6),
            ("Objective", 6),
            ("Issue", 6),
            ("Contract", 6),
            ("Policy", 6),
            ("Regulation", 6),
            ("Requirement", 6),
            ("Standard", 6),
            ("Audit", 4),
            ("Program", 6),
            ("Assessment", 8),
            ("AssessmentTemplate", 3),
            ("TaskGroup", 3),
            ("TaskGroupTask", 3),
            ("Workflow", 3),
            ("Person", 3))
  @ddt.unpack
  def test_non_editable_tips(self, model, counts):
    """Tests if {} has non-editable fields hint correctly"""
    data = {
        "export_to": "csv",
        "objects": [{"object_name": model, "fields": "all"}]
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertEqual(counts,
                     response.data.count("Automatically provided values"))

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
    self.assertIn("Allowed values are:\nyes\nno", response.data)

  def test_custom_attr_people(self):
    """Test if LCA Map:Person type has hint for Assessment ."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          title="Included LCAD",
          attribute_type="Map:Person",
          definition_id=assessment.id,
      )
    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Assessment", "fields": "all"}]
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Included LCAD", response.data)
    self.assertIn("Allowed values are emails", response.data)

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

  @ddt.data(
      ("Assessment", "Dropdown"),
      ("Assessment", "Multiselect"),
      ("Issue", "Dropdown"),
      ("Issue", "Multiselect"),
      ("Person", "Dropdown"),
      ("Person", "Multiselect"),
      ("Audit", "Dropdown"),
      ("Audit", "Multiselect"),
      ("Product", "Dropdown"),
      ("Product", "Multiselect"),
  )
  @ddt.unpack
  def test_ca_dropdown_multiselect(self, model, attribute):
    """Test if CAD {1} type has hint for {0}."""
    with factories.single_commit():
      multi_options = "option_1,option_2,option_3"
      factories.CustomAttributeDefinitionFactory(
          definition_type=model.lower(),
          attribute_type=attribute,
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

  @ddt.data("Dropdown", "Multiselect")
  def test_lca_multichoice_hint(self, attribute):
    """Test if Local CAD {} has hint for Assessment ."""
    with factories.single_commit():
      assessment = factories.AssessmentFactory()
      multi_options = "option_1,option_2,option_3"
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          title="LCAD ",
          attribute_type=attribute,
          definition_id=assessment.id,
          multi_choice_options=multi_options,
      )

    data = {
        "export_to": "csv",
        "objects": [{"object_name": "Assessment", "fields": "all"}]
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
        WithNetworkZone.NZ_OPTIONS
    )), response.data
    )

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

  def test_assessment_template_tip(self):
    """Tests if Assessment Template Ticket Tracker Integration column has
      tip message in export file"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "AssessmentTemplate", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nOn\nOff", response.data)

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

  def test_policy_tip(self):
    """Tests if Policy Kind/Type column has tip message in export file"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "Policy", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)

    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        all_models.Policy.POLICY_OPTIONS)), response.data)

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
                  "\nAllowed values are:\nyes\nno", response.data)

  def test_severity_tip(self):
    """Tests for tip in Severity column for AssessmentTemplate object"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": "AssessmentTemplate", "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format(
        '\n'.join(constants.AVAILABLE_SEVERITIES)), response.data)

  @ddt.data("Assessment", "AssessmentTemplate", "Issue", "Audit")
  def test_priority_tip(self, model):
    """Tests for tip in Priority column for {} """
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": "all"},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format('\n'.join(
        constants.AVAILABLE_PRIORITIES)), response.data)

  @ddt.data("Assessment", "Audit", "AssessmentTemplate")
  def test_archived_attributes(self, model):
    """Test to check export values for archived objects"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": ["archived"]},
        ]
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nyes\nno", response.data)


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
    with factories.single_commit():
      for i in range(1, 24):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": define_op_expr("title", "=", "Cat ipsum 1"),
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
            "expression": define_op_expr("title", "~", "1"),
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
            "expression": define_op_expr("title", "=", obj.title),
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

  @ddt.data("Assessment", "AssessmentTemplate", "Audit", "Issue")
  def test_tracker_integration_hint(self, model):
    """Tests if {} attribute 'Ticket Tracker Integration' has hint expected"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": ["enabled"]},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\nOn\nOff", response.data)

  @ddt.data("Assessment", "AssessmentTemplate", "Audit", "Contract",
            "Issue", "Program", "Regulation", "Objective", "Policy",
            "Standard", "Threat", "Requirement")
  def test_unified_hint_state(self, model):
    """Tests if {} type attribute state has hint expected"""
    data = {
        "export_to": "csv",
        "objects": [
            {"object_name": model, "fields": ["title", "status"]},
        ],
    }
    response = self.client.post("/_service/export_csv",
                                data=dumps(data), headers=self.headers)
    self.assertIn("Allowed values are:\n{}".format(
        '\n'.join(inflector.get_model(model).VALID_STATES)), response.data)

  def test_and_export_query(self):
    """Test export query with AND clause."""
    with factories.single_commit():
      for i in range(1, 24):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": {
                "left": define_op_expr("title", "!~", "2"),
                "op": {"name": "AND"},
                "right": define_op_expr("title", "~", "1"),
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
    contract_slugs = []
    program_slugs = []
    with factories.single_commit():
      for i in range(1, 5):
        contract = factories.ContractFactory(title="contract-{}".format(i))
        contract_slugs.append(contract.slug)
        program = factories.ProgramFactory(title="program-{}".format(i))
        program_slugs.append(program.slug)
        factories.RelationshipFactory(source=contract, destination=program)

    data = [
        get_related_objects("Contract", "Program", contract_slugs[:2])
    ]
    response = self.export_csv(data)
    expected = set([1, 2])
    for i in range(1, 5):
      if i in expected:
        self.assertIn(",program-{},".format(i), response.data)
      else:
        self.assertNotIn(",program-{},".format(i), response.data)

  # pylint:disable=invalid-name
  def test_program_audit_relevant_query(self):
    """Test program audit relevant query"""
    with factories.single_commit():
      programs = [factories.ProgramFactory(title="Prog-{}".format(i))
                  for i in range(1, 3)]

    program_slugs = [program.slug for program in programs]
    audit_data = [
        collections.OrderedDict([
            ("object_type", "Audit"),
            ("Code", ""),
            ("Title", "Au-{}".format(i)),
            ("State", "Planned"),
            ("Audit Captains", "user@example.com"),
            ("Program", program_slugs[0]),
        ]) for i in range(1, 3)
    ]

    audit_data += [
        collections.OrderedDict([
            ("object_type", "Audit"),
            ("Code", ""),
            ("Title", "Au-{}".format(i)),
            ("State", "Planned"),
            ("Audit Captains", "user@example.com"),
            ("Program", program_slugs[1]),
        ]) for i in range(3, 5)
    ]
    self.import_data(*audit_data)

    audit = all_models.Audit.query.filter_by(title="Au-1").first()
    data = [
        get_related_objects("Audit", "Program", [audit.slug]),
        get_related_objects("__previous__", "Audit", obj_ids=["0"]),
    ]
    response = self.export_csv(data)

    self.assertIn(",Prog-1,", response.data)
    expected = set([1, 2])
    for i in range(1, 5):
      if i in expected:
        self.assertIn(",Au-{},".format(i), response.data)
      else:
        self.assertNotIn(",Au-{},".format(i), response.data)

  # pylint:disable=invalid-name
  # pylint:disable=too-many-locals
  def test_requirement_policy_relevant_query(self):
    """Test requirement policy relevant query"""
    with factories.single_commit():
      policies = [factories.PolicyFactory(title="pol-{}".format(i))
                  for i in range(1, 3)]
      standards = [factories.StandardFactory(title="stand-{}".format(i))
                   for i in range(1, 3)]
      regulations = [factories.RegulationFactory(title="reg-{}".format(i))
                     for i in range(1, 3)]
      requirements = [factories.RequirementFactory(title="req-{}".format(i))
                      for i in range(1, 4)]

    policy_slugs = [policy.slug for policy in policies]
    standard_slugs = [standard.slug for standard in standards]
    regulation_slugs = [regulation.slug for regulation in regulations]
    requirement_slugs = [requirement.slug for requirement in requirements]

    policy_map_data = [
        get_object_data("Policy", policy_slugs[0],
                        requirement=requirement_slugs[0]),
    ]
    self.import_data(*policy_map_data)

    standard_map_data = [
        get_object_data("Standard", standard_slugs[0],
                        requirement=requirement_slugs[1]),
    ]
    self.import_data(*standard_map_data)

    regulation_map_data = [
        get_object_data("Regulation", regulation_slugs[0],
                        requirement=requirement_slugs[2]),
    ]
    self.import_data(*regulation_map_data)

    data = [
        get_related_objects("Policy", "Requirement", policy_slugs[:1]),
        get_related_objects("Requirement", "Policy", requirement_slugs[:1]),
        get_related_objects("Standard", "Requirement", standard_slugs[:1]),
        get_related_objects("Requirement", "Standard", requirement_slugs[1:2]),
        get_related_objects("Regulation", "Requirement", regulation_slugs[:1]),
        get_related_objects("Requirement", "Regulation",
                            requirement_slugs[2:3])
    ]

    response = self.export_csv(data)
    titles = [",req-{},".format(i) for i in range(1, 4)]
    titles.extend([",pol-1,", ",pol-2,",
                   ",stand-1,", ",stand-2,",
                   ",reg-1,", ",reg-2,"])

    expected = set([
        ",req-1,",
        ",req-2,",
        ",req-3,",
        ",pol-1,",
        ",stand-1,",
        ",reg-1,",
    ])

    for title in titles:
      if title in expected:
        self.assertIn(title, response.data, "'{}' not found".format(title))
      else:
        self.assertNotIn(title, response.data, "'{}' was found".format(title))

  def test_multiple_relevant_query(self):
    """Test multiple relevant query"""
    with factories.single_commit():
      policies = [factories.PolicyFactory(title="policy-{}".format(i))
                  for i in range(1, 5)]
      contracts = [factories.ContractFactory(title="contract-{}".format(i))
                   for i in range(1, 5)]
      programs = [factories.ProgramFactory(title="program-{}".format(i))
                  for i in range(1, 10)]

    policy_slugs = [policy.slug for policy in policies]
    contract_slugs = [contract.slug for contract in contracts]
    program_slugs = [program.slug for program in programs]

    program_data = [
        get_object_data("Program", program_slugs[0], "", ""),
        get_object_data("Program", program_slugs[1], contract_slugs[0], ""),
        get_object_data("Program", program_slugs[2],
                        '\n'.join(contract_slugs[1:3]), ""),
        get_object_data("Program", program_slugs[3], "", policy_slugs[0]),
        get_object_data("Program", program_slugs[4], contract_slugs[1],
                        policy_slugs[1]),
        get_object_data("Program", program_slugs[5],
                        '\n'.join(contract_slugs[2:4]), policy_slugs[2]),
        get_object_data("Program", program_slugs[6], "",
                        '\n'.join(policy_slugs[1:3])),
        get_object_data("Program", program_slugs[7],
                        contract_slugs[1], '\n'.join(policy_slugs[2:4])),
        get_object_data("Program", program_slugs[8],
                        '\n'.join(contract_slugs[:2]),
                        '\n'.join(policy_slugs[:2])),
    ]

    self.import_data(*program_data)

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": define_op_expr(
                define_relevant_expr("Policy", policy_slugs[1:2]), "AND",
                define_relevant_expr("Contract", contract_slugs[:2])
            ),
        },
        "fields": "all",
    }]
    response = self.export_csv(data)
    expected = set([5, 9])
    for i in range(1, 10):
      if i in expected:
        self.assertIn(",program-{},".format(i), response.data)
      else:
        self.assertNotIn(",program-{},".format(i), response.data)

  def test_query_all_aliases(self):
    """Tests query for all aliases"""
    def rhs(model, attr):  # pylint:disable=missing-docstring
      attr = getattr(model, attr, None)
      if attr is not None and hasattr(attr, "_query_clause_element"):
        # pylint:disable=protected-access
        class_name = attr._query_clause_element().type.__class__.__name__
        if class_name == "Boolean":
          return "1"
      return "1/1/2015"

    def data(model, attr, field):
      return [{
          "object_name": model.__name__,
          "fields": "all",
          "filters": {
              "expression": define_op_expr(field.lower(), "=",
                                           rhs(model, attr)),
          }
      }]

    failed = set()
    for model in set(get_exportables().values()):
      # pylint:disable=protected-access
      for attr, field in AttributeInfo(model)._aliases.items():
        if field is None:
          continue
        try:
          field = field["display_name"] if isinstance(field, dict) else field
          res = self.export_csv(data(model, attr, field))
          self.assertEqual(res.status_code, 200)
        except Exception as err:  # pylint:disable=broad-except
          failed.add((model, attr, field, err))
    self.assertEqual(sorted(failed), [])


@ddt.ddt
class TestExportMultipleObjects(TestCase):
  """Tests export of Multiple objects"""
  def setUp(self):
    super(TestExportMultipleObjects, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_simple_multi_export(self):
    """Test basic export of multiple objects"""
    match = 1
    with factories.single_commit():
      programs = [factories.ProgramFactory().title for _ in range(3)]
      regulations = [factories.RegulationFactory().title for _ in range(3)]

    data = [{
        "object_name": "Program",
        "filters": {
            "expression": define_op_expr("title", "=", programs[match]),
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",
        "filters": {
            "expression": define_op_expr("title", "=", regulations[match]),
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
            "expression": define_op_expr("title", "=", program.title),
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",
        "filters": {
            "expression": define_op_expr("title", "=", regulation.title),
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
            "expression": define_op_expr("title", "=", program.title),
        },
        "fields": "all",
    }, {
        "object_name": "Regulation",
        "filters": {
            "expression": define_op_expr("title", "=", regulation.title),
        },
        "fields": "all",
    }]
    response = self.export_csv(
        data,
        exportable_objects=[3]
    )
    response_data = response.data
    self.assertEquals(response_data, "")

  # pylint:disable=invalid-name
  def test_relevant_to_previous_export(self):
    """Test relevant to previous export"""
    with factories.single_commit():
      products = [factories.ProductFactory(title="product-{}".format(i))
                  for i in range(1, 3)]
      policies = [factories.PolicyFactory(title="policy-{}".format(i))
                  for i in range(1, 3)]
      programs = [factories.ProgramFactory(title="program-{}".format(i))
                  for i in range(1, 3)]

    product_slugs = [product.slug for product in products]
    policy_slugs = [policy.slug for policy in policies]
    program_slugs = [program.slug for program in programs]

    policy_data = [
        get_object_data("Policy", policy_slugs[0], product=product_slugs[0]),
        get_object_data("Policy", policy_slugs[1],
                        product="\n".join(product_slugs[:2])),
    ]
    self.import_data(*policy_data)

    program_data = [
        get_object_data("Program", program_slugs[0], policy=policy_slugs[0],
                        product=product_slugs[1]),
        get_object_data("Program", program_slugs[1], policy=policy_slugs[1],
                        product=product_slugs[0]),
    ]
    self.import_data(*program_data)

    data = [{
        "object_name": "Program",  # program-1
        "filters": {
            "expression": define_op_expr("title", "=", "program-1"),
        },
        "fields": ["slug", "title", "description"],
    }, {
        "object_name": "Product",  # product-2
        "filters": {
            "expression": define_relevant_expr("__previous__", obj_ids=["0"]),
        },
        "fields": ["slug", "title", "description"],
    }, {
        "object_name": "Policy",  # policy-2
        "filters": {
            "expression": define_relevant_expr("__previous__", obj_ids=["1"])
        },
        "fields": ["slug", "title", "description"],
    }
    ]
    response = self.export_csv(data)

    self.assertIn(",program-1,", response.data)
    self.assertNotIn(",program-2,", response.data)
    self.assertIn(",product-2,", response.data)
    self.assertNotIn(",product-1,", response.data)
    self.assertIn(",policy-2,", response.data)
    self.assertNotIn(",policy-{},", response.data)

  @ddt.data(
      "Assessment",
      "Policy",
      "Regulation",
      "Standard",
      "Contract",
      "Requirement",
      "Objective",
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
          ("Code*", ""),
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
      self.assertEqual(obj.test_plan, u"<p>Procedure-{}</p>".format(num))

    obj_dicts = [
        {
            "Code*": obj.slug,
            "Assessment Procedure": u"Procedure-{}".format(i)
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

  @ddt.data(*all_models.get_scope_models())
  def test_export_for_scope(self, model):
    """Test export {} with assessment procedure."""
    with factories.single_commit():
      model_ = factories.get_model_factory(model.__name__)()
      model_.test_plan = "Procedure-{}".format(model.__name__)

    obj_dict = [{
        "Code*": model_.slug,
        "Assessment Procedure": "Procedure-{}".format(model.__name__)
    }]
    search_request = [{
        "object_name": model.__name__,
        "filters": {
            "expression": {},
        },
        "fields": ["slug", "test_plan"],
    }]
    model_key = model._inflector.title_singular
    exported_data = self.export_parsed_csv(search_request)[model_key]
    self.assertEqual(obj_dict, exported_data)


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

  @ddt.data(*test_constants.FLAG_VALIDATORS)
  @ddt.unpack
  def test_import_archived_values(self, import_value, expected_value):
    """Test to check import values for archived."""
    with factories.single_commit():
      audit = factories.AuditFactory()
    self.import_data(collections.OrderedDict([
        ("object_type", "Audit"),
        ("Code*", audit.slug),
        ("archived", import_value),
    ]))
    audit1 = all_models.Audit.query.filter_by(title=audit.title).first()
    self.assertEqual(audit1.archived, expected_value)
