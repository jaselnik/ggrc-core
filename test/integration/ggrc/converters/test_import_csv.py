# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Tests for basic csv imports."""
import collections
from collections import OrderedDict

import ddt
import mock

from appengine import base
from ggrc import models
from ggrc.converters import errors
from ggrc.models import all_models
import ggrc_basic_permissions
from integration.ggrc import TestCase, api_helper
from integration.ggrc import generator
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@ddt.ddt
class TestBasicCsvImport(TestCase):
  """Test basic CSV imports."""
  # pylint: disable=too-many-public-methods

  def setUp(self):
    super(TestBasicCsvImport, self).setUp()
    self.generator = generator.ObjectGenerator()
    self.api = api_helper.Api()
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

  def test_policy_work_with_warnings(self):
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
        errors.MISSING_VALUE_ERROR.format(line=9, column_name="Name"),
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

  def test_import_object_with_folder(self):
    """Test checks to add folder via import"""
    folder_id = '1WXB8oulc68ZWdFhX96Tv1PBLi8iwALR3'
    response = self.import_data(OrderedDict([
        ("object_type", "Program"),
        ("Code*", "program-1"),
        ("Program managers", "user@example.com"),
        ("Title", "program-1"),
        ("GDrive Folder ID", folder_id)

    ]))
    self._check_csv_response(response, {})
    program = models.Program.query.first()
    self.assertEqual(program.folder, folder_id)

  @ddt.data(
      'Contract',
      'Objective',
      'Policy',
      'Requirement',
      'Threat',
  )
  def test_document_recipients(self, object_type):
    """Test check admin recipients for document created via import"""
    title = 'program 1'
    user = factories.PersonFactory()
    response = self.import_data(OrderedDict([
        ("object_type", object_type),
        ("Code*", ""),
        ("title", title),
        ("Admin", user.email),
        ("reference url", "http://someurl.html")
    ]))

    self._check_csv_response(response, {})
    document = all_models.Document.query.one()
    self.assertEqual(document.recipients, 'Admin')

  def test_document_recipients_issue(self):
    """Test check admin recipients for document created via import issue"""
    title = 'program 1'
    user = factories.PersonFactory()
    response = self.import_data(OrderedDict([
        ("object_type", 'Issue'),
        ("Code*", ""),
        ("title", title),
        ("Admin", user.email),
        ("reference url", "http://someurl.html"),
        ("Due Date", "07/30/2019")
    ]))

    self._check_csv_response(response, {})
    document = all_models.Document.query.one()
    self.assertEqual(document.recipients, 'Admin')


@base.with_memcache
class TestImportPermissions(TestCase):
  """Test permissions loading during import."""

  def setUp(self):
    super(TestImportPermissions, self).setUp()
    self.api = api_helper.Api()

  def test_import_permissions(self):
    """Test that permissions aren't recalculated during import new objects."""
    with factories.single_commit():
      audit = factories.AuditFactory(slug="audit-1")
      market = factories.MarketFactory()
      user = factories.PersonFactory()
      system_role = all_models.Role.query.filter(
          all_models.Role.name == "Creator"
      ).one()
      rbac_factories.UserRoleFactory(role=system_role, person=user)
      audit.add_person_with_role_name(user, "Audit Captains")
      market.add_person_with_role_name(user, "Admin")
    self._create_snapshots(audit, [market])

    data = [
        collections.OrderedDict([
            ("Code*", ""),
            ("Audit*", "audit-1"),
            ("Title*", "assessment{}".format(i)),
            ("State", "Not Started"),
            ("Assignees*", "user@example.com"),
            ("Creators*", "user@example.com"),
            ("map:market versions", market.slug),
        ]) for i in range(10)
    ]

    self.api.set_user(user)

    with mock.patch(
        "ggrc_basic_permissions.load_access_control_list",
        side_effect=ggrc_basic_permissions.load_access_control_list
    ) as acl_loader:
      response = self.api.run_import_job(user, "Assessment", data)
      self.assert200(response)
      # 10 Assessments should be created in import
      self.assertEqual(all_models.Assessment.query.count(), 10)
      # Permissions were loaded once on dry run and once on real run
      self.assertEqual(acl_loader.call_count, 2)

  def test_permissions_cleared(self):
    """Test that permissions where cleared after import."""
    with factories.single_commit():
      user = factories.PersonFactory()
      user_id = user.id
      market = factories.MarketFactory(slug="test market")
      system_role = all_models.Role.query.filter(
          all_models.Role.name == "Creator"
      ).one()
      rbac_factories.UserRoleFactory(role=system_role, person=user)
      market.add_person_with_role_name(user, "Admin")

    user_perm_key = 'permissions:{}'.format(user_id)

    # Recalculate permissions under new user
    self.api.set_user(user)
    self.api.client.get("/permissions")

    perm_ids = self.memcache_client.get('permissions:list')
    self.assertEqual(perm_ids, {user_perm_key})
    user_perm = self.memcache_client.get(user_perm_key)
    self.assertIsNotNone(user_perm)

    data = [
        collections.OrderedDict([
            ("Code*", ""),
            ("Title*", "Test Objective"),
            ("Admin", "user@example.com"),
            ("map:market", "test market"),
        ])
    ]
    response = self.api.run_import_job(user, "Objective", data)
    self.assert200(response)
    self.assertEqual(all_models.Objective.query.count(), 1)

    perm_ids = self.memcache_client.get('permissions:list')
    self.assertEqual(perm_ids, set())
    user_perm = self.memcache_client.get(user_perm_key)
    self.assertIsNone(user_perm)

  def test_import_without_code_object(self):
    """Test import csv without 'Code' but with existing title."""
    title = 'program 1'
    factories.ProgramFactory(title=title)
    self.assertEqual(len(models.Program.query.all()), 1)
    response = self.import_data(OrderedDict([
        ("object_type", "Program"),
        ("Code*", ""),
        ("title", title),
        ("Program managers", "user@example.com"),
    ]))

    expected_errors = {
        "Program": {
            "row_errors": {
                errors.DUPLICATE_VALUE.format(
                    line=3, column_name='title', value=title
                ),
            }
        }
    }
    self._check_csv_response(response, expected_errors)
    self.assertEqual(len(models.Program.query.all()), 1)
