# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for bulk Assessments complete."""

import json
import mock
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

  def test_successfully_completed(self):
    """Test all assessments completed successfully"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory(status="Not Started")
      asmt2 = factories.AssessmentFactory(status="Not Started")

    data = {
        "assessments_ids": [asmt1.id, asmt2.id],
        "attributes": [{
            "assessment": {"id": asmt1.id, "slug": asmt1.slug},
            "values": [],
        }, {
            "assessment": {"id": asmt2.id, "slug": asmt2.slug},
            "values": [],
        }],
    }

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
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [],
        } for asmt in assmts],
    }

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    assessments = models.Assessment.query.all()
    for assessment in assessments:
      self.assertEqual(assessment.status, "In Review")

  def test_one_completed_one_in_review(self):
    """Test 1t asmt has become In Review status and 2nd has been completed

    1st assessment can't be completed in a one step because it has Verifiers,
    2nd assessment has no Verifiers and can be moved to the Complete status
    in a one step.
    """
    # pylint: disable=invalid-name
    with factories.single_commit():
      user = models.Person.query.first()
      asmt1 = factories.AssessmentFactory(status="Not Started")
      asmt2 = factories.AssessmentFactory(status="Not Started")
      asmt1.add_person_with_role_name(user, "Verifiers")
      asmt1_id = asmt1.id
      asmt2_id = asmt2.id

    data = {
        "assessments_ids": [asmt1_id, asmt2_id],
        "attributes": [{
            "assessment": {"id": asmt1_id, "slug": asmt1.slug},
            "values": [],
        }, {
            "assessment": {"id": asmt2_id, "slug": asmt2.slug},
            "values": [],
        }],
    }

    response = self.client.post("/api/bulk_operations/complete",
                                data=json.dumps(data),
                                headers=self.headers)

    self.assert200(response)
    self.assertEqual(
        models.Assessment.query.get(asmt1_id).status,
        "In Review",
    )
    self.assertEqual(
        models.Assessment.query.get(asmt2_id).status,
        "Completed",
    )

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
        "attributes": [{
            "assessment": {"id": success_id, "slug": success_assmt.slug},
            "values": [],
        }, {
            "assessment": {"id": failed_id, "slug": failed_assmt.slug},
            "values": [],
        }],
    }

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
    with factories.single_commit():
      assmt1 = factories.AssessmentFactory(status="Not Started")
      assmt2 = factories.AssessmentFactory(status="Not Started")
      cad_payload = dict(
          title="lca_title",
          definition_type="assessment",
          attribute_type="Dropdown",
          multi_choice_options="one,two",
          multi_choice_mandatory="1,1",
      )
      cad1 = factories.CustomAttributeDefinitionFactory(
          definition_id=assmt1.id,
          **cad_payload
      )
      cad2 = factories.CustomAttributeDefinitionFactory(
          definition_id=assmt2.id,
          **cad_payload
      )
      assmts = [
          (assmt1, cad1, "comment descr1"),
          (assmt2, cad2, "comment descr2"),
      ]

    data = {
        "assessments_ids": [assmt1.id, assmt2.id],
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": "one",
                "title": "lca_title",
                "type": "Dropdown",
                "definition_id": asmt.id,
                "id": cad.id,
                "extra": {
                    "comment": {"description": comment_value},
                    "urls": [],
                    "files": [],
                },
            }],
        } for asmt, cad, comment_value in assmts]
    }
    self.client.post("/api/bulk_operations/complete",
                     data=json.dumps(data),
                     headers=self.headers)

    comments = models.Comment.query.all()
    cad_definitions = {comment.custom_attribute_definition_id
                       for comment in comments}
    cads = models.CustomAttributeDefinition.query.all()
    self.assertEqual(cad_definitions, {cad.id for cad in cads})
    for assessment in models.Assessment.query.all():
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

    data = {
        "assessments_ids": assmts_ids,
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": "one",
                "title": "text_lca",
                "type": "Dropdown",
                "definition_id": asmt.id,
                "extra": {
                    "comment": None,
                    "urls": ["url1"],
                    "files": [],
                },
            }],
        } for asmt in assmts]
    }
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

    data = {
        "assessments_ids": assmts_ids,
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": "one",
                "title": "lca_title",
                "type": "Dropdown",
                "definition_id": asmt.id,
                "extra": {
                    "comment": None,
                    "urls": [],
                    "files": [{"source_gdrive_id": "mock_id"}],
                },
            }],
        } for asmt in assmts]
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

  @ddt.data(
      ("Text", "Text", "abc", "abc"),
      ("Rich Text", "Rich Text", "abc", "abc"),
      ("Date", "Date", "7/15/2015", "2015-07-15"),
      ("Checkbox", "Checkbox", "1", "1"),
      ("Checkbox", "Checkbox", "0", "0"),
      ("Checkbox", "checkbox", "0", "0"),
      ("Map:Person", "Map:Person", "test@test.com", "test@test.com"),
      ("Map:Person", "map:person", "test@test.com", "test@test.com"),
  )
  @ddt.unpack
  def test_attributes_values(
      self,
      attribute_type,
      request_type,
      value,
      expected_value,
  ):
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

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": value,
                "title": "test_lca",
                "type": request_type,
                "definition_id": asmt.id,
                "extra": {},
            }],
        } for asmt in asmts]
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

  def test_complete_one_asmt_one_update_only(self):
    """Test request /complete with two asmts, 1 for update, 1 for complete"""
    # pylint: disable=invalid-name
    asmt1 = factories.AssessmentFactory(status="Not Started")
    asmt1_id = asmt1.id
    asmt2 = factories.AssessmentFactory(status="Not Started")
    asmt2_id = asmt2.id
    cad_id = factories.CustomAttributeDefinitionFactory(
        definition_id=asmt1.id,
        title="test_lca",
        definition_type="assessment",
        attribute_type="Checkbox",
        mandatory=True,
    ).id
    data = {
        "assessments_ids": [asmt2.id],
        "attributes": [{
            "assessment": {"id": asmt2.id, "slug": asmt2.slug},
            "values": [],
        }, {
            "assessment": {"id": asmt1.id, "slug": asmt1.slug},
            "values": [{
                "value": "1",
                "title": "test_lca",
                "type": "Checkbox",
                "definition_id": asmt1.id,
                "extra": {},
            }],
        }],
    }
    self.client.post(
        "/api/bulk_operations/complete",
        data=json.dumps(data),
        headers=self.headers,
    )
    cav = models.CustomAttributeValue.query.filter_by(
        custom_attribute_id=cad_id,
    ).first()
    self.assertEqual("1", cav.attribute_value)
    self.assertEqual(
        models.Assessment.query.get(asmt1_id).status,
        "In Progress",
    )
    self.assertEqual(
        models.Assessment.query.get(asmt2_id).status,
        "Completed",
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

    data = {
        "assessments_ids": asmts_ids,
        "attributes": [{
            "assessment": {"id": asmt.id, "slug": asmt.slug},
            "values": [{
                "value": value,
                "title": "text_lca",
                "type": attribute_type,
                "definition_id": asmt.id,
                "extra": {},
            }]
        } for asmt in asmts]
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

  def test_bulk_save_person_lca_null(self):
    """Test set person type lca to null with bulk"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory()
      asmt_id = asmt.id
      cad = factories.CustomAttributeDefinitionFactory(
          title='person_lca',
          attribute_type='Map:Person',
          definition_type='assessment',
          definition_id=asmt_id,
      )
      cad_id = cad.id
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=asmt,
          attribute_value="user@example.com",
      )
    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {"id": asmt_id, "slug": asmt.slug},
            "values": [{
                "value": "-",
                "title": "person_lca",
                "type": "map:person",
                "definition_id": asmt_id,
                "extra": {},
            }],
        }],
    }
    self.client.post(
        "/api/bulk_operations/cavs/save",
        data=json.dumps(data),
        headers=self.headers,
    )
    self.assertEqual(
        models.CustomAttributeValue.query.filter_by(
            custom_attribute_id=cad_id,
        ).all(),
        [],
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
                    "files": [{"source_gdrive_id": "mock_id"}],
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
                    "files": [],
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

  def test_save_validate_params(self):
    """Test request /save endpoint with invalid assessments_ids param.

    Save operation do not proceed assessments listed in the assessments_ids
    parameter. It should be empty to avoid data inconsistency.
    """
    response = self.client.post(
        "/api/bulk_operations/cavs/save",
        data=json.dumps({"assessments_ids": [1, 2, 3]}),
        headers=self.headers,
    )
    self.assert400(response)
    self.assertEqual(
        response.json["message"],
        "assessments_ids list for /save operation should be empty.",
    )

  def test_complete_validate_params(self):
    """Test request /complete endpoint with missing assessments_ids param.

    Complete operation requires data in the assessments_ids list, because
    complete action can't be proceed on the empty data.
    """
    response = self.client.post(
        "/api/bulk_operations/complete",
        data=json.dumps({"assessments_ids": []}),
        headers=self.headers,
    )
    self.assert400(response)
    self.assertEqual(
        response.json["message"],
        "assessments_ids list for /complete operation can't be empty.",
    )
