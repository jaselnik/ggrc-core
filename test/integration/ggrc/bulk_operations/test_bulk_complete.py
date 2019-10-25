# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for bulk Assessments complete."""

import json
import mock

from ggrc import models
from integration import ggrc
from integration.ggrc.models import factories


class TestBulkComplete(ggrc.TestCase):
  """Test assessment bulk complete"""
  def setUp(self):
    super(TestBulkComplete, self).setUp()
    self.client.get('/login')

  def test_successfully_completed(self):
    """Test all assessments completed successfully"""
    with factories.single_commit():
      asmts_ids = []
      for _ in range(2):
        asmts_ids.append(factories.AssessmentFactory(status="Not Started").id)

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [],
    }

    self.init_taskqueue()
    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    self.assertEqual(len(assessments), 2)
    for assessment in assessments:
      self.assertEqual(assessment.status, "Completed")

  def test_successfully_in_review(self):
    """Test all assessments were moved to In review state successfully"""
    with factories.single_commit():
      assmts = []
      user = models.Person.query.first()
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        assmt.add_person_with_role_name(user, "Verifiers")
        assmts.append(assmt)
      asmts_ids = [assessment.id for assessment in assmts]

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [],
    }

    self.init_taskqueue()
    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    for assessment in assessments:
      self.assertEqual(assessment.status, "In Review")

  def test_partly_successfully(self):
    """Test one assessment moved to completed state and other not changed"""
    with factories.single_commit():
      success_assmt = factories.AssessmentFactory(status="Not Started")
      failed_assmt = factories.AssessmentFactory(status="Not Started")
      success_id = success_assmt.id
      failed_id = failed_assmt.id
      factories.CustomAttributeDefinitionFactory(
          definition_id=failed_id,
          definition_type="assessment",
          mandatory=True,
      )

    data = {
        "assessments_ids": [success_id, failed_id],
        "attributes": [],
    }
    self.init_taskqueue()

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    failed = models.Assessment.query.get(failed_id).status
    self.assertEqual(failed, "Not Started")
    success = models.Assessment.query.get(success_id).status
    self.assertEqual(success, "Completed")

  def test_mapped_comment(self):
    """Test assessment successfully completed after LCA comment mapping"""
    assmts = []
    assmts_ids = []
    with factories.single_commit():
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        definition = factories.CustomAttributeDefinitionFactory(
            definition_id=assmt.id,
            title="lca_title",
            definition_type="assessment",
            attribute_type="Dropdown",
            multi_choice_options="one,two",
            multi_choice_mandatory="1,1",
        )
        assmts.append((assmt, definition))
        assmts_ids.append(assmt.id)

    bulk_update = [{"assessment_id": asmt.id,
                    "attribute_definition_id": cad.id,
                    "slug": asmt.slug} for asmt, cad in assmts]
    data = {
        "assessments_ids": assmts_ids,
        "attributes": [{
            "attribute_value": "one",
            "attribute_title": "lca_title",
            "attribute_type": "Dropdown",
            "extra": {"comment": {"description": "comment descr1"},
                      "urls": [],
                      "files": []},
            "bulk_update": bulk_update,
        }],
    }
    self.init_taskqueue()
    self.client.post("/api/bulk_operations/complete",
                     data=json.dumps(data),
                     headers=self.headers)

    comments = models.Comment.query.all()
    cad_definitions = {comment.custom_attribute_definition_id
                       for comment in comments}
    cads = models.CustomAttributeDefinition.query.all()
    cads_ids = {cad.id for cad in cads}
    self.assertEqual(cad_definitions, cads_ids)
    assmts = models.Assessment.query.all()
    for assessment in assmts:
      self.assertEqual(assessment.status, "Completed")

  def test_urls_mapped(self):
    """Test urls were mapped to assessments and assessments were completed"""
    assmts = []
    assmts_ids = []
    with factories.single_commit():
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        factories.CustomAttributeDefinitionFactory(
            definition_id=assmt.id,
            title="lca_title",
            definition_type="assessment",
            attribute_type="Dropdown",
            multi_choice_options="one,two",
            multi_choice_mandatory="4,4",
        )
        assmts.append(assmt)
        assmts_ids.append(assmt.id)

    bulk_update = [{"assessment_id": asmt.id,
                    "attribute_definition_id": None,
                    "slug": asmt.slug} for asmt in assmts]
    data = {
        "assessments_ids": assmts_ids,
        "attributes": [{
            "attribute_value": "one",
            "attribute_title": "lca_title",
            "attribute_type": "Dropdown",
            "extra": {"comment": None,
                      "urls": ["url1"],
                      "files": []},
            "bulk_update": bulk_update,
        }],
    }
    self.init_taskqueue()
    self.client.post("/api/bulk_operations/complete",
                     data=json.dumps(data),
                     headers=self.headers)
    assmts = models.Assessment.query.all()
    for assmt in assmts:
      urls = {url.title for url in assmt.evidences_url}
      self.assertEqual(urls, {"url1"})
      self.assertEqual(assmt.status, "Completed")

  @mock.patch('ggrc.gdrive.file_actions.process_gdrive_file')
  @mock.patch('ggrc.gdrive.file_actions.get_gdrive_file_link')
  @mock.patch('ggrc.gdrive.get_http_auth')
  def test_evidences_mapped(self, _, get_gdrive_link, process_gdrive_mock):
    """Test files were mapped to assessments and completed successfully"""
    process_gdrive_mock.return_value = {
        "id": "mock_id",
        "webViewLink": "link",
        "name": "name",
    }
    get_gdrive_link.return_value = "mock_id"
    assmts = []
    assmts_ids = []
    with factories.single_commit():
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        factories.CustomAttributeDefinitionFactory(
            definition_id=assmt.id,
            title="lca_title",
            definition_type="assessment",
            attribute_type="Dropdown",
            multi_choice_options="one,two",
            multi_choice_mandatory="2,2",
        )
        assmts.append(assmt)
        assmts_ids.append(assmt.id)

    bulk_update = [{"assessment_id": asmt.id,
                    "attribute_definition_id": None,
                    "slug": asmt.slug} for asmt in assmts]
    data = {
        "assessments_ids": assmts_ids,
        "attributes": [{
            "attribute_value": "one",
            "attribute_title": "lca_title",
            "attribute_type": "Dropdown",
            "extra": {"comment": None,
                      "urls": [],
                      "files": [{"source_gdrive_id": "mock_id"}]},
            "bulk_update": bulk_update,
        }],
    }
    self.init_taskqueue()

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)
    self.assert200(response)
    assmts = models.Assessment.query.all()
    for assmt in assmts:
      urls = {ev_file.gdrive_id for ev_file in assmt.evidences_file}
      self.assertEqual(urls, {u"mock_id"})
      self.assertEqual(assmt.status, "Completed")
