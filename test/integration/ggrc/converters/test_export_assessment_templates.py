# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""Tests for assessment templates export."""
import ddt

from ggrc.models.assessment_template import AssessmentTemplate

from integration.ggrc.models import factories
from integration.ggrc import TestCase


@ddt.ddt
class TestAssessmentTemplatesExport(TestCase):
  """Assessment Template export test"""

  EXPORT_ALL_FIELDS_DATA = [{
      "object_name": "AssessmentTemplate",
      "filters": {
          "expression": {},
      },
      "fields": "all",
  }]

  def setUp(self):
    """Set up for Assessment Template test cases."""
    super(TestAssessmentTemplatesExport, self).setUp()
    self.client.get("/login")

  @ddt.data(
      ("Object Admins", "Admin"),
      ("Audit Captain", "Audit Lead"),
      ("Auditors", "Auditors"),
      ("Principal Assignees", "Principal Assignees"),
      ("Secondary Assignees", "Secondary Assignees"),
      ("Primary Contacts", "Primary Contacts"),
      ("Secondary Contacts", "Secondary Contacts")
  )
  @ddt.unpack
  def test_people_labels_export(self, title, label):
    """Test for check people label export"""
    default_people = {"assignees": label, "verifiers": label}
    factories.AssessmentTemplateFactory(
        title=title,
        default_people=default_people
    )

    response = self.export_parsed_csv(self.EXPORT_ALL_FIELDS_DATA)
    assessment_template = response["Assessment Template"][0]
    self.assertEqual(assessment_template["Default Assignees*"], title)
    self.assertEqual(assessment_template["Default Verifiers"], title)

  def test_empty_people_export(self):
    """Test for check people label export"""
    default_people = {"assignees": "Auditors", "verifiers": None}
    factories.AssessmentTemplateFactory(
        title="Audit Lead",
        default_people=default_people
    )

    response = self.export_parsed_csv(self.EXPORT_ALL_FIELDS_DATA)
    assessment_template = response["Assessment Template"][0]
    self.assertEqual(assessment_template["Default Assignees*"], "Auditors")
    self.assertEqual(assessment_template["Default Verifiers"], "--")

  def test_procedure_description(self):
    """Test correct export of Default Assessment Procedure field"""
    proc_description = "some description"
    factories.AssessmentTemplateFactory(
        title="Audit Lead",
        procedure_description=proc_description
    )

    response = self.export_parsed_csv(self.EXPORT_ALL_FIELDS_DATA)
    assessment_template = response["Assessment Template"][0]
    self.assertEqual(proc_description,
                     assessment_template["Default Assessment Procedure"])

  def test_default_description(self):
    """Test default assignees and verifiers description"""
    # pylint: disable=protected-access

    response = self.export_csv(self.EXPORT_ALL_FIELDS_DATA)
    expected_description = AssessmentTemplate._HINT_VERIFIERS_ASSIGNEES

    self.assertEqual(response.status_code, 200)
    self.assertIn(expected_description, response.data)

  def test_default_assessment_type(self):
    """Tests if Default Assignment Type has tip message"""
    response = self.export_csv(self.EXPORT_ALL_FIELDS_DATA)
    expected_description = "Allowed values are:\n{}".format(
        '\n'.join(AssessmentTemplate.DEFAULT_ASSESSMENT_TYPE_OPTIONS
                  ))

    self.assertEqual(response.status_code, 200)
    self.assertIn(expected_description, response.data)
