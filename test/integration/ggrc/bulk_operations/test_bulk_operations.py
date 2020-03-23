# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for bulk Assessments complete."""

import json
import mock
import unittest
import ddt

from ggrc import models
from integration import ggrc
from integration.ggrc import generator
from integration.ggrc.models import factories


@ddt.ddt
class TestBulkOperations(ggrc.TestCase):
  """Test assessment bulk complete"""
  def setUp(self):
    super(TestBulkOperations, self).setUp()
    self.client.get('/login')
    self.api = ggrc.Api()
    self.object_generator = generator.ObjectGenerator()
    self.init_taskqueue()

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
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

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    self.assertEqual(len(assessments), 2)
    for assessment in assessments:
      self.assertEqual(assessment.status, "Completed")

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
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

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    for assessment in assessments:
      self.assertEqual(assessment.status, "In Review")

  def test_successfully_verified(self):
    """Test bulk verify was successful"""

    with factories.single_commit():
      assmts = []
      user = models.Person.query.first()
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="In Review")
        assmt.add_person_with_role_name(user, "Verifiers")
        assmts.append(assmt)
      asmts_ids = [assessment.id for assessment in assmts]

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [],
    }

    response = self.client.post("/api/bulk_operations/verify",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    for assessment in assessments:
      self.assertEqual(assessment.status, "Completed")
      self.assertTrue(assessment.verified)

  def test_not_verified(self):
    """Test bulk verify failed"""
    with factories.single_commit():
      assmts = []
      user = models.Person.query.first()
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="In Review")
        assmt.add_person_with_role_name(user, "Verifiers")
        assmts.append(assmt)
      asmts_ids = [assessment.id for assessment in assmts]

    _, user = self.object_generator.generate_person(user_role="Creator")
    self.api.set_user(user)

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [],
    }
    response = self.api.client.post("/api/bulk_operations/verify",
                                    data=json.dumps(data),
                                    headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    for assessment in assessments:
      self.assertEqual(assessment.status, "In Review")

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
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

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    failed = models.Assessment.query.get(failed_id).status
    self.assertEqual(failed, "Not Started")
    success = models.Assessment.query.get(success_id).status
    self.assertEqual(success, "Completed")

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
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

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
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
    self.client.post("/api/bulk_operations/complete",
                     data=json.dumps(data),
                     headers=self.headers)
    assmts = models.Assessment.query.all()
    for assmt in assmts:
      urls = {url.title for url in assmt.evidences_url}
      self.assertEqual(urls, {"url1"})
      self.assertEqual(assmt.status, "Completed")

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  @mock.patch('ggrc.gdrive.file_actions.process_gdrive_file')
  @mock.patch('ggrc.gdrive.file_actions.get_gdrive_file_link')
  @mock.patch('ggrc.gdrive.get_http_auth')
  def test_evidences_mapped(self, _, get_gdrive_link, process_gdrive_mock):
    """Test files were mapped to assessments and completed successfully"""
    process_gdrive_mock.return_value = {
        "id": "mock_id",
        "webViewLink": "test_mock_link",
        "name": "mock_name",
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

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)
    self.assert200(response)
    assmts = models.Assessment.query.all()
    for assmt in assmts:
      urls = {ev_file.gdrive_id for ev_file in assmt.evidences_file}
      self.assertEqual(urls, {u"mock_id"})
      self.assertEqual(assmt.status, "Completed")

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  @ddt.data(
      ("Text", "abc", "abc"),
      ("Rich Text", "abc", "abc"),
      ("Date", "7/15/2015", "2015-07-15"),
      ("Checkbox", "1", "1"),
      ("Checkbox", "0", "0"),
      ("Map:Person", "test@test.com", "test@test.com"),
  )
  @ddt.unpack
  def test_attributes_values(self, attribute_type, value, expected_value):
    """Test complete asmts set cavs with attribute_type {0}."""
    # pylint: disable=too-many-locals
    asmts = []
    asmts_ids = []
    cads_ids = []
    with factories.single_commit():
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        cad = factories.CustomAttributeDefinitionFactory(
            definition_id=assmt.id,
            title="test_lca",
            definition_type="assessment",
            attribute_type=attribute_type,
        )
        asmts.append(assmt)
        asmts_ids.append(assmt.id)
        cads_ids.append(cad.id)

    bulk_update = [{
        "assessment_id": asmt.id,
        "attribute_definition_id": cad_id,
        "slug": asmt.slug} for cad_id, asmt in zip(cads_ids, asmts)]
    data = {
        "assessments_ids": asmts_ids,
        "attributes": [{
            "attribute_value": value,
            "attribute_title": "test_lca",
            "attribute_type": attribute_type,
            "extra": {},
            "bulk_update": bulk_update,
        }],
    }
    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)
    self.assert200(response)
    asmts = models.Assessment.query.all()
    cavs = models.CustomAttributeValue.query.filter(
        models.CustomAttributeValue.custom_attribute_id.in_(cads_ids)
    ).all()
    for asmt in asmts:
      self.assertEqual(asmt.status, "Completed")
    for cav in cavs:
      self.assertEqual(cav.attribute_value, expected_value)

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  @ddt.data(
      ("Multiselect", "onE,tWo,Three", "One,three", "onE,Three"),
      ("Dropdown", "yes,No", "no", "No"),
  )
  @ddt.unpack
  def test_attributes_select_values(self, attribute_type, options,
                                    value, expected_value):
    """Test complete asmts select cavs with attribute_type {0}."""
    # pylint: disable=too-many-locals
    asmts = []
    asmts_ids = []
    cads_ids = []
    with factories.single_commit():
      for _ in range(2):
        assmt = factories.AssessmentFactory(status="Not Started")
        cad = factories.CustomAttributeDefinitionFactory(
            definition_id=assmt.id,
            title="test_lca",
            definition_type="assessment",
            attribute_type=attribute_type,
            multi_choice_options=options,
        )
        asmts.append(assmt)
        asmts_ids.append(assmt.id)
        cads_ids.append(cad.id)

    bulk_update = [{
        "assessment_id": asmt.id,
        "attribute_definition_id": cad_id,
        "slug": asmt.slug} for cad_id, asmt in zip(cads_ids, asmts)]
    data = {
        "assessments_ids": asmts_ids,
        "attributes": [{
            "attribute_value": value,
            "attribute_title": "test_lca",
            "attribute_type": attribute_type,
            "extra": {},
            "bulk_update": bulk_update,
        }],
    }
    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)
    self.assert200(response)
    asmts = models.Assessment.query.all()
    cavs = models.CustomAttributeValue.query.filter(
        models.CustomAttributeValue.custom_attribute_id.in_(cads_ids)
    ).all()
    for asmt in asmts:
      self.assertEqual(asmt.status, "Completed")
    for cav in cavs:
      self.assertEqual(cav.attribute_value, expected_value)

  def test_bulk_cavs_save(self):
    """Test save assessment's CAD in bulk with new value"""
    with factories.single_commit():
      assmt = factories.AssessmentFactory(status="Not Started")
      cad_id = factories.CustomAttributeDefinitionFactory(
          definition_id=assmt.id,
          title="text_lca",
          definition_type="assessment",
          attribute_type="Text",
      ).id

    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {
                "id": assmt.id,
                "slug": assmt.slug,
            },
            "values": [{
                "value": "test value",
                "title": "text_lca",
                "type": "Text",
                "definition_id": assmt.id,
                "extra": {},
            }]
        }]
    }
    response = self.client.post("/api/bulk_operations/cavs/save",
                                data=json.dumps(data),
                                headers=self.headers)
    self.assert200(response)
    cav = models.CustomAttributeValue.query.filter_by(
        custom_attribute_id=cad_id
    ).one()
    self.assertEqual(
        cav.attribute_value,
        "test value",
    )

  @mock.patch('ggrc.gdrive.file_actions.process_gdrive_file')
  @mock.patch('ggrc.gdrive.file_actions.get_gdrive_file_link')
  @mock.patch('ggrc.gdrive.get_http_auth')
  def test_bulk_save_files(self, _, get_gdrive_link, process_gdrive_mock):
    """Test files were mapped to assessments successfully"""
    process_gdrive_mock.return_value = {
        "id": "mock_id",
        "webViewLink": "test_mock_link",
        "name": "mock_name",
    }
    get_gdrive_link.return_value = "mock_id"
    with factories.single_commit():
      assmt = factories.AssessmentFactory(status="Not Started")
      factories.CustomAttributeDefinitionFactory(
          definition_id=assmt.id,
          title="lca_title",
          definition_type="assessment",
          attribute_type="Dropdown",
          multi_choice_options="one,two",
          multi_choice_mandatory="2,2",
      )

    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {
                "id": assmt.id,
                "slug": assmt.slug,
            },
            "values": [{
                "value": "one",
                "title": "lca_title",
                "type": "Dropdown",
                "definition_id": assmt.id,
                "extra": {
                    "comment": None,
                    "urls": [],
                    "files": [{"source_gdrive_id": "mock_id"}]
                },
            }]
        }]
    }

    response = self.client.post(
        "/api/bulk_operations/cavs/save",
        data=json.dumps(data),
        headers=self.headers,
    )
    self.assert200(response)
    assmt = models.Assessment.query.first()
    urls = {ev_file.gdrive_id for ev_file in assmt.evidences_file}
    self.assertEqual(urls, {u"mock_id"})

  def test_bulk_save_comment(self):
    """Test assessment successfully LCA comment mapping"""
    with factories.single_commit():
      assmt = factories.AssessmentFactory(status="Not Started")
      cad_id = factories.CustomAttributeDefinitionFactory(
          definition_id=assmt.id,
          title="lca_title",
          definition_type="assessment",
          attribute_type="Dropdown",
          multi_choice_options="one,two",
          multi_choice_mandatory="1,1",
      ).id

    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {
                "id": assmt.id,
                "slug": assmt.slug,
            },
            "values": [{
                "value": "one",
                "title": "lca_title",
                "type": "Dropdown",
                "definition_id": assmt.id,
                "id": cad_id,
                "extra": {
                    "comment": {"description": "comment descr1"},
                    "urls": [],
                    "files": []
                },
            }]
        }]
    }
    self.client.post(
        "/api/bulk_operations/cavs/save",
        data=json.dumps(data),
        headers=self.headers,
    )

    comment = models.Comment.query.filter_by(
        custom_attribute_definition_id=cad_id,
    ).one()
    self.assertIn("comment descr1", comment.description)
