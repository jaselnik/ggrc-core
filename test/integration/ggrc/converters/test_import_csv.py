# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Tests for basic csv imports."""

from collections import OrderedDict

import ddt
import mock

from ggrc import models
from ggrc.converters import errors
from integration.ggrc import TestCase
from integration.ggrc import generator
from integration.ggrc.models import factories


@ddt.ddt
class TestBasicCsvImport(TestCase):
  """Test basic CSV imports."""

  def setUp(self):
    super(TestBasicCsvImport, self).setUp()
    self.generator = generator.ObjectGenerator()
    self.client.get("/login")

  def generate_people(self, people):
    for person in people:
      self.generator.generate_person({
          "name": person,
          "email": "{}@reciprocitylabs.com".format(person),
      }, "Administrator")

  def test_policy_basic_import(self):
    """Test basic policy import."""
    filename = "policy_basic_import.csv"
    self.import_file(filename)
    policies = models.Policy.query.count()
    self.assertEqual(policies, 3)
    revisions = models.Revision.query.filter(
        models.Revision.resource_type == "Policy"
    ).count()
    self.assertEqual(revisions, 3)
    policy = models.Policy.eager_query().first()
    self.assertEqual(policy.modified_by.email, "user@example.com")

  def test_policy_import_working_with_warnings(self):
    """Test Policy import with warnings."""
    def test_owners(policy):
      """Assert policy has the correct Admin set."""
      self.assertNotEqual([], policy.access_control_list)
      self.assertEqual(
          "user@example.com",
          policy.access_control_list[0][0].email
      )
      owner = models.Person.query.filter_by(email="user@example.com").first()
      self.assert_roles(policy, Admin=owner)

    filename = "policy_import_working_with_warnings.csv"
    response_json = self.import_file(filename, safe=False)

    expected_warnings = {
        errors.UNKNOWN_USER_WARNING.format(line=3, email="miha@policy.com"),
        errors.UNKNOWN_OBJECT.format(
            line=3, object_type="Program", slug="p753"),
        errors.OWNER_MISSING.format(line=4, column_name="Admin"),
        errors.UNKNOWN_USER_WARNING.format(line=6, email="not@a.user"),
        errors.OWNER_MISSING.format(line=6, column_name="Admin"),
    }
    response_warnings = response_json[0]["row_warnings"]
    self.assertEqual(expected_warnings, set(response_warnings))
    response_errors = response_json[0]["row_errors"]
    self.assertEqual(set(), set(response_errors))
    self.assertEqual(4, response_json[0]["created"])

    policies = models.Policy.query.all()
    self.assertEqual(len(policies), 4)
    # Only 1 and 3 policies should have owners
    test_owners(policies[0])
    test_owners(policies[2])

  def test_policy_same_titles(self):
    """Test Policy imports with title collisions."""
    def test_owners(policy):
      """Assert policy has the correct Admin set."""
      self.assertNotEqual([], policy.access_control_list)
      self.assertEqual("user@example.com",
                       policy.access_control_list[0][0].email)
      owner = models.Person.query.filter_by(email="user@example.com").first()
      self.assert_roles(policy, Admin=owner)

    filename = "policy_same_titles.csv"
    response_json = self.import_file(filename, safe=False)

    self.assertEqual(3, response_json[0]["created"])
    self.assertEqual(6, response_json[0]["ignored"])
    self.assertEqual(0, response_json[0]["updated"])
    self.assertEqual(9, response_json[0]["rows"])

    expected_errors = {
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="4", processed_line="3", column_name="Title",
            value="A title"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="6", processed_line="3", column_name="Title",
            value="A title"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="10", processed_line="3", column_name="Title",
            value="A title"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="11", processed_line="3", column_name="Title",
            value="A title"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="7", processed_line="5", column_name="Title",
            value="A different title"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="9", processed_line="8", column_name="Code", value="code"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="10", processed_line="8", column_name="Code", value="code"),
        errors.DUPLICATE_VALUE_IN_CSV.format(
            line="11", processed_line="8", column_name="Code", value="code"),
    }
    response_errors = response_json[0]["row_errors"]
    self.assertEqual(expected_errors, set(response_errors))

    policies = models.Policy.query.all()
    self.assertEqual(len(policies), 3)
    for policy in policies:
      test_owners(policy)

  @ddt.data(True, False)
  def test_intermappings(self, reverse_order):
    """It is allowed to reference previous lines in map columns."""
    self.generate_people(["miha", "predrag", "vladan", "ivan"])
    facility_data_block = [
        OrderedDict([
            ("object_type", "facility"),
            ("Code*", "HOUSE-{}".format(idx)),
            ("title", "Facility-{}".format(idx)),
            ("admin", "user@example.com"),
            ("assignee", "user@example.com"),
            ("verifier", "user@example.com"),
            ("map:facility", "" if idx == 1 else "HOUSE-{}".format(idx - 1)),
        ])
        for idx in (xrange(1, 5) if not reverse_order else xrange(4, 0, -1))
    ]
    objective_data_block = [
        OrderedDict([
            ("object_type", "objective"),
            ("Code*", "O1"),
            ("title", "House of cards"),
            ("admin", "user@example.com"),
            ("map:facility", "HOUSE-2"),
            ("map:objective", ""),
        ]),
        OrderedDict([
            ("object_type", "objective"),
            ("Code*", "O2"),
            ("title", "House of the rising sun"),
            ("admin", "user@example.com"),
            ("map:facility", "HOUSE-3"),
            ("map:objective", "O1\nO2\nO3"),
        ]),
        OrderedDict([
            ("object_type", "objective"),
            ("Code*", "O3"),
            ("title", "Yellow house"),
            ("admin", "user@example.com"),
            ("map:facility", "HOUSE-4"),
            ("map:objective", ""),
        ]),
        OrderedDict([
            ("object_type", "objective"),
            ("Code*", "O4"),
            ("title", "There is no place like home"),
            ("admin", "user@example.com"),
            ("map:facility", "HOUSE-1"),
            ("map:objective", "O3\nO4\nO3"),
        ]),
    ]

    response_json = self.import_data(
        *(facility_data_block + objective_data_block)
    )
    self.assertEqual(4, response_json[0]["created"])  # Facility
    self.assertEqual(4, response_json[1]["created"])  # Objective

    if reverse_order:
      expected_block_1 = set([
          u"Line {line}: Facility 'house-{idx}' "
          u"doesn't exist, so it can't be mapped/unmapped.".format(
              idx=idx,
              line=6 - idx
          )
          for idx in xrange(1, 4)
      ])
      rel_numbers = 8
    else:
      expected_block_1 = set()
      rel_numbers = 11

    expected_block_2 = {
        u"Line 11: Objective 'o3' doesn't exist, "
        u"so it can't be mapped/unmapped."
    }
    self.assertEqual(expected_block_1, set(response_json[0]["row_warnings"]))
    self.assertEqual(expected_block_2, set(response_json[1]["row_warnings"]))
    self.assertEqual(rel_numbers, models.Relationship.query.count())

    obj2 = models.Objective.query.filter_by(slug="O2").first()
    obj3 = models.Objective.query.filter_by(slug="O3").first()
    self.assertNotEqual(None, models.Relationship.find_related(obj2, obj2))
    self.assertEqual(None, models.Relationship.find_related(obj3, obj3))

  @ddt.data(['Standard', ('Regulation', 'Policy', 'Contract', 'Requirement'),
             {"Standard": ["map:standard"]}],
            ['Regulation', ('Standard', 'Policy', 'Contract', 'Requirement'),
             {"Regulation": ["map:regulation"]}],
            ['Policy', ('Regulation', 'Standard', 'Contract', 'Requirement'),
             {"Policy": ["map:policy"]}],
            ['Requirement', ('Regulation', 'Policy', 'Contract', 'Standard'),
             {}],
            ['Contract', ('Regulation', 'Policy', 'Standard', 'Requirement'),
             {"Contract": ["map:contract"]}])
  @ddt.unpack
  def test_map_core_objects(self, check_object, other_objects, block_warnings):
    """Ensure that core GRC objects correctly map to each other

    Core objects to test are:
    * Standard
    * Regulation
    * Policy
    * Requirement
    * Contract

    CANNOT be mapped the following pairs:
    * Standard to Standard
    * Regulation to Regulation
    * Policy to Policy
    * Contract to Contract
    (however, Requirement CAN be mapped to Requirement)
    """

    data_block = [
        OrderedDict([
            ("object_type", obj_type),
            ("Code*", "{}-1".format(obj_type.upper())),
            ("Title*", "{}-1".format(obj_type)),
            ("Admin*", "user@example.com"),
        ]) for obj_type in other_objects
    ]

    # Add object to check
    data_block.extend([
        OrderedDict([
            ("object_type", check_object),
            ("Code*", "{}-1".format(check_object.upper())),
            ("Title*", "{}-1".format(check_object)),
            ("Admin*", "user@example.com"),
            ("map:regulation", ""),
            ("map:policy", ""),
            ("map:contract", ""),
            ("map:requirement", ""),
            ("map:standard", ""),
        ]),
        OrderedDict([
            ("object_type", check_object),
            ("Code*", "{}-2".format(check_object.upper())),
            ("Title*", "{}-2".format(check_object)),
            ("Admin*", "user@example.com"),
            ("map:regulation", "REGULATION-1"),
            ("map:policy", "POLICY-1"),
            ("map:contract", "CONTRACT-1"),
            ("map:requirement", "REQUIREMENT-1"),
            ("map:standard", "STANDARD-1"),
        ]),
    ])

    response = self.import_data(*data_block)

    self._check_csv_response(response, {
        obj_type: {
            "block_warnings": {
                errors.UNSUPPORTED_MAPPING.format(
                    line=18,
                    obj_a=obj_type,
                    obj_b=warn_column.split(":", 1)[1],
                    column_name=warn_column
                )
            } for warn_column in warn_columns
        } for obj_type, warn_columns in block_warnings.iteritems()
    })

  def test_policy_unique_title(self):
    """Test import of existing policy."""
    filename = "policy_sample1.csv"
    response_json = self.import_file(filename)

    self.assertEqual(response_json[0]["row_errors"], [])

    filename = "policy_sample2.csv"
    response_json = self.import_file(filename, safe=False)

    self.assertEqual(response_json[0]["row_errors"], [
        "Line 3: title 'will this work' already exists.Record will be ignored."
    ])

  def test_assessments_import_update(self):
    """Test for updating Assessment with import

    Checks for fields being updarted correctly
    """
    self.import_file("pci_program.csv")

    assessment = models.Assessment.query.filter_by(slug="CA.PCI 1.1").first()
    audit = models.Audit.query.filter_by(slug="AUDIT-Consolidated").first()
    self.assertEqual(assessment.design, "Effective")
    self.assertEqual(assessment.operationally, "Effective")
    self.assertIsNone(models.Relationship.find_related(assessment, audit))

    response = self.import_file("pci_program_update.csv", safe=False)

    self._check_csv_response(response, {
        "Assessment": {
            "row_warnings": {
                errors.UNMODIFIABLE_COLUMN.format(line=3, column_name="Audit")
            }
        }
    })

    assessment = models.Assessment.query.filter_by(slug="CA.PCI 1.1").first()
    audit = models.Audit.query.filter_by(slug="AUDIT-Consolidated").first()
    self.assertEqual(assessment.design, "Needs improvement")
    self.assertEqual(assessment.operationally, "Ineffective")
    self.assertIsNone(models.Relationship.find_related(assessment, audit))

  def test_person_imports(self):
    """Test imports for Person object with user roles."""
    filename = "people_test.csv"
    response = self.import_file(filename, safe=False)[0]

    expected_errors = {
        errors.MISSING_VALUE_ERROR.format(line=8, column_name="Email"),
        errors.WRONG_VALUE_ERROR.format(line=10, column_name="Email"),
        errors.WRONG_VALUE_ERROR.format(line=11, column_name="Email"),
    }

    self.assertEqual(expected_errors, set(response["row_errors"]))
    self.assertEqual(0, models.Person.query.filter_by(email=None).count())

  def test_duplicate_people(self):
    """Test adding two of the same object people objects in the same row."""
    filename = "duplicate_object_person.csv"
    response = self.import_file(filename)[0]

    self.assertEqual(0, len(response["row_warnings"]))
    self.assertEqual(0, len(response["row_errors"]))

  def test_duplicate_people_objective(self):
    """Test duplicate error that causes request to fail."""
    self.generator.generate_object(models.Objective, {"slug": "objective1"})
    filename = "duplicate_object_person_objective_error.csv"
    response = self.import_file(filename)[0]

    self.assertEqual(0, len(response["row_warnings"]))
    self.assertEqual(0, len(response["row_errors"]))

  def test_audit_import_context(self):
    """Test audit context on edits via import."""
    factories.ProgramFactory(slug="p")
    response = self.import_data(OrderedDict([
        ("object_type", "Audit"),
        ("Code*", "audit"),
        ("title", "audit"),
        ("Audit Captains", "user@example.com"),
        ("state", "In Progress"),
        ("program", "P"),
    ]))
    self._check_csv_response(response, {})

    audit = models.Audit.query.first()
    program = models.Program.query.first()
    self.assertNotEqual(audit.context_id, program.context_id)

    response = self.import_data(OrderedDict([
        ("object_type", "Audit"),
        ("Code*", "audit"),
        ("title", "audit"),
        ("Audit Captains", "user@example.com"),
        ("state", "In Progress"),
        ("program", "P"),
    ]))
    self._check_csv_response(response, {})

    audit = models.Audit.query.first()
    program = models.Program.query.first()
    self.assertNotEqual(audit.context_id, program.context_id)

  def test_import_with_code_column(self):
    """Test import csv with 'Code' column."""
    file_name = "import_with_code_column.csv"
    response = self.import_file(file_name)

    self.assertEqual(response[0]["created"], 1)
    self.assertEqual(response[0]["block_errors"], [])

  def test_import_without_code_column(self):
    """Test error message when trying to import csv without 'Code' column."""
    file_name = "import_without_code_column.csv"
    response = self.import_file(file_name, safe=False)

    self.assertEqual(response[0]["created"], 0)
    self.assertEqual(response[0]["block_errors"], [
        errors.MISSING_COLUMN.format(column_names="Code", line=2, s="")
    ])

  def test_import_code_validation(self):
    """Test validation of 'Code' column during import"""
    response = self.import_data(OrderedDict([
        ("object_type", "Program"),
        ("Code*", "*program-1"),
        ("Program managers", "user@example.com"),
        ("Title", "program-1"),
    ]))
    self._check_csv_response(response, {
        "Program": {
            "row_errors": {
                "Line 3: Field 'Code' validation failed with the following "
                "reason: Field 'Code' contains unsupported symbol '*'. "
                "The line will be ignored."
            }
        }
    })

  def test_import_lines(self):
    """Test importing CSV with empty lines in block
    and check correct lines numbering"""
    file_name = "import_empty_lines.csv"
    response = self.import_file(file_name, safe=False)
    results = {r["name"]: r for r in response}
    expected = {
        "Person": {
            "created": 4,
            "ignored": 0,
            "row_errors": 0,
            "row_warnings": 0,
            "rows": 4,
        },
        "Audit": {
            "created": 2,
            "ignored": 0,
            "row_errors": 0,
            "row_warnings": 1,
            "rows": 2,
        },
        "Program": {
            "created": 2,
            "ignored": 0,
            "row_errors": 0,
            "row_warnings": 1,
            "rows": 2,
        },
    }
    for name, data in expected.items():
      result = results[name]
      result_dict = {
          "created": result["created"],
          "ignored": result["ignored"],
          "row_errors": len(result["row_errors"]),
          "row_warnings": len(result["row_warnings"]),
          "rows": result["rows"],
      }
      self.assertDictEqual(
          result_dict,
          data,
          u"Numbers don't match for {}: expected {!r}, got {!r}".format(
              name,
              data,
              result_dict,
          ),
      )
      self.assertIn(u"Line 16", results["Program"]["row_warnings"][0])
      self.assertIn(u"Line 21", results["Audit"]["row_warnings"][0])

  def test_import_hook_error(self):
    """Test errors in import"""
    with mock.patch(
        "ggrc.converters.base_block."
        "ImportBlockConverter.send_collection_post_signals",
        side_effect=Exception("Test Error")
    ):
      self._import_file("assessment_template_no_warnings.csv")
      self._import_file("assessment_with_templates.csv")
    self.assertEqual(models.all_models.Assessment.query.count(), 0)
    self.assertEqual(models.all_models.Revision.query.count(), 0)
