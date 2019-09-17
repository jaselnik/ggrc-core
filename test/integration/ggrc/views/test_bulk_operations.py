# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Tests for module provides endpoints to calc cavs in bulk"""

import json

from integration.ggrc import TestCase
from integration.ggrc.models import factories


class TestBulkOperations(TestCase):
  """Textra views.ests for bulk operations POST view"""

  ENDPOINT_URL = "/api/bulk_operations/cavs/search"

  def setUp(self):
    super(TestBulkOperations, self).setUp()
    self.client.get("/login")

  def test_calc_cad_400(self):
    """Test for the CADs missing query POST data"""
    response = self.client.post(
        self.ENDPOINT_URL,
        data="[{}]",
        headers=self.headers
    )
    self.assert400(response)

  def test_related_assessments(self):
    """Test for the CADs has no value in assessments"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(assessment_type="Control")
      cad_text = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Text",
      )
      asmt2 = factories.AssessmentFactory(assessment_type="Control")
      factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    data = [{
        "ids": [asmt.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Text",
            "title": "text_LCA",
            "default_value": "",
            "multi_choice_options": None,
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 1,
            "values": [{
                "assessments_type": "Control",
                "assessments": [{
                    "id": asmt.id,
                    "attribute_definition_id": cad_text.id,
                }]
            }],
        },
        "assessments_with_values": []
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_assessments_with_values(self):
    """Test for the CADs has value in assessments"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(assessment_type="Control")
      cad_text = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Text",
      )
      cav = factories.CustomAttributeValueFactory(
          custom_attribute=cad_text,
          attributable=asmt,
          attribute_value="test_value",
      )
    data = [{
        "ids": [asmt.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Text",
            "title": "text_LCA",
            "default_value": "",
            "multi_choice_options": None,
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 0,
            "values": [],
        },
        "assessments_with_values": [{
            "id": asmt.id,
            "title": asmt.title,
            "attribute_value": cav.attribute_value,
        }]
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_dropdown_cad(self):
    """Test for the dropdown CADs"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(assessment_type="Control")
      cad_obj = factories.CustomAttributeDefinitionFactory(
          title="dropdown_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Dropdown",
          multi_choice_options="1,2,3",
      )
    data = [{
        "ids": [asmt.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Dropdown",
            "title": "dropdown_LCA",
            "default_value": "",
            "multi_choice_options": "1,2,3",
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 1,
            "values": [{
                "assessments_type": "Control",
                "assessments": [{
                    "id": asmt.id,
                    "attribute_definition_id": cad_obj.id,
                }]
            }],
        },
        "assessments_with_values": []
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_multiselect_cad(self):
    """Test for the multiselect CADs"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory(assessment_type="Control")
      cad_obj = factories.CustomAttributeDefinitionFactory(
          title="multiselect_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Multiselect",
          multi_choice_options="1,2,3",
          mandatory=True
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=cad_obj,
          attributable=asmt,
          attribute_value="1,2",
      )
    data = [{
        "ids": [asmt.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Multiselect",
            "title": "multiselect_LCA",
            "default_value": "",
            "multi_choice_options": "1,2,3",
            "multi_choice_mandatory": None,
            "mandatory": True,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 0,
            "values": [],
        },
        "assessments_with_values": [{
            "id": asmt.id,
            "title": asmt.title,
            "attribute_value": "1,2",
        }]
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_same_cads(self):
    """Test group by same cads"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory(assessment_type="Control")
      cad_obj1 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Text",
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=cad_obj1,
          attributable=asmt1,
          attribute_value="test_value",
      )
      asmt2 = factories.AssessmentFactory(assessment_type="Control")
      cad_obj2 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    data = [{
        "ids": [asmt1.id, asmt2.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Text",
            "title": "text_LCA",
            "default_value": "",
            "multi_choice_options": None,
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 1,
            "values": [{
                "assessments_type": "Control",
                "assessments": [{
                    "id": asmt2.id,
                    "attribute_definition_id": cad_obj2.id,
                }]
            }],
        },
        "assessments_with_values": [{
            "id": asmt1.id,
            "title": asmt1.title,
            "attribute_value": "test_value",
        }]
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_many_related_assessments(self):
    """Test same CADs with same assessment_types"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory(assessment_type="Control")
      cad_obj1 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Text",
      )
      asmt2 = factories.AssessmentFactory(assessment_type="Control")
      cad_obj2 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    data = [{
        "ids": [asmt1.id, asmt2.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Text",
            "title": "text_LCA",
            "default_value": "",
            "multi_choice_options": None,
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 2,
            "values": [{
                "assessments_type": "Control",
                "assessments": [{
                    "id": asmt1.id,
                    "attribute_definition_id": cad_obj1.id,
                }, {
                    "id": asmt2.id,
                    "attribute_definition_id": cad_obj2.id,
                }]
            }],
        },
        "assessments_with_values": [],
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)

  def test_diff_assessments_type(self):
    """Test same CADs with diff assessment_types"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory(assessment_type="Control")
      cad_obj1 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Text",
      )
      asmt2 = factories.AssessmentFactory(assessment_type="Risk")
      cad_obj2 = factories.CustomAttributeDefinitionFactory(
          title="text_LCA",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    data = [{
        "ids": [asmt1.id, asmt2.id]
    }]
    expected_response = [{
        "attribute": {
            "attribute_type": "Text",
            "title": "text_LCA",
            "default_value": "",
            "multi_choice_options": None,
            "multi_choice_mandatory": None,
            "mandatory": False,
            "placeholder": None,
        },
        "related_assessments": {
            "count": 2,
            "values": [{
                "assessments_type": "Control",
                "assessments": [{
                    "id": asmt1.id,
                    "attribute_definition_id": cad_obj1.id,
                }],
            }, {
                "assessments_type": "Risk",
                "assessments": [{
                    "id": asmt2.id,
                    "attribute_definition_id": cad_obj2.id,
                }],
            }],
        },
        "assessments_with_values": [],
    }]
    response = self.client.post(
        self.ENDPOINT_URL,
        data=json.dumps(data),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(expected_response, response.json)
