# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>]

"""Test csv builder methods for assessments bulk complete"""

import copy
import unittest
import ddt

import freezegun
from integration.ggrc import TestCase
from integration.ggrc.models import factories

from ggrc.bulk_operations import csvbuilder


CAVS_STUB = {
    "assessments_ids": [],
    "attributes": [{
        "assessment": {
            "id": 1,
            "slug": "slug1",
        },
        "values": [{
            "value": "cav_value",
            "title": "cav_title",
            "type": "Text",
            "definition_id": 1,
            "id": 1,
            "extra": {
                "comment": {},
                "urls": [],
                "files": []
            },
        }, {
            "value": "cav_value1",
            "title": "cav_title1",
            "type": "Text",
            "definition_id": 1,
            "id": 3,
            "extra": {
                "comment": {},
                "urls": [],
                "files": []
            },
        }]
    }, {
        "assessment": {
            "id": 2,
            "slug": "slug2",
        },
        "values": [{
            "value": "cav_value",
            "title": "cav_title",
            "type": "Text",
            "definition_id": 2,
            "id": 2,
            "extra": {
                "comment": {},
                "urls": [],
                "files": []
            },
        }],
    }]
}

EXPECTED_STUB = {1: {"files": [],
                     "urls": [],
                     "cavs": {'cav_title1': 'cav_value1',
                              'cav_title': 'cav_value'},
                     "slug": "slug1",
                     "verification": False,
                     "comments": []},
                 2: {"files": [],
                     "urls": [],
                     "cavs": {'cav_title': 'cav_value'},
                     "slug": "slug2",
                     "verification": False,
                     "comments": []}}


def create_input_data(cavs_data):
  """Update input CAVS_STUB-like structure with appropriate data

    Args:
      cavs_data: {asmt_ind: {cad_id: {{key:value, }, }, }.
        ind - indexes of CAVS_STUB["attributes"] list (0,1) to update,
        key - fields to be updated in stub,
        value - values for appropriate fields.
  """
  input_data = copy.deepcopy(CAVS_STUB)
  for asmt_ind in cavs_data:
    for value_ind in cavs_data[asmt_ind]:
      for key in cavs_data[asmt_ind][value_ind]:
        if key in input_data["attributes"][asmt_ind]["values"][value_ind]:
          input_data["attributes"][asmt_ind]["values"][value_ind][key] = \
              cavs_data[asmt_ind][value_ind][key]
        else:
          input_data["attributes"][asmt_ind]["values"][
              value_ind
          ]["extra"][key] = cavs_data[asmt_ind][value_ind][key]
  return input_data


def create_assert_data(expected_data):
  """Update EXPECTED_STUB-like structure with appropriate data

    Args:
      cavs_data: {ind: {key:value, }, }.
        ind - indexes of EXPECTED_STUB list (0,1) to update,
        key - fields to be updated in stub,
        value - values for appropriate fields.
  """
  assert_data = copy.deepcopy(EXPECTED_STUB)
  for assmt_id in expected_data:
    for key in expected_data[assmt_id]:
      assert_data[assmt_id][key] = expected_data[assmt_id][key]
  return assert_data


@ddt.ddt
class TestMatrixCsvBuilder(TestCase):
  """Class for testing MatrixCsvBuilder methods"""
  # pylint: disable=invalid-name

  def assert_assessments(self, builder, assert_data):
    """Asserts all assessments in builder"""
    for assessment in builder.assessments:
      self.assert_assessment(assessment, assert_data[assessment.id])

  def assert_assessment(self, assessment, expected_dict):
    """Asserts single AssessmentStub fields"""
    self.assertEqual(assessment.files, expected_dict["files"])
    self.assertEqual(assessment.urls, expected_dict["urls"])
    self.assertEqual(assessment.cavs, expected_dict["cavs"])
    self.assertEqual(assessment.slug, expected_dict["slug"])
    self.assertEqual(assessment.comments, expected_dict["comments"])
    self.assertEqual(
        assessment.needs_verification,
        expected_dict["verification"]
    )

  @ddt.data(
      [{}, {}],

      [
          {
              0: {0: {"urls": ["1", "2"]}, 1: {"urls": ["3"]}},
              1: {0: {"urls": ["1", "2"]}}
          },
          {1: {"urls": ["1", "2", "3"]}, 2: {"urls": ["1", "2"]}}
      ],

      [{0: {1: {"urls": ["3"]}}}, {1: {"urls": ["3"]}, 2: {"urls": []}}],

      [
          {
              0: {
                  0: {"files": [
                      {"source_gdrive_id": "1"},
                      {"source_gdrive_id": "2"}
                  ]},
                  1: {"files": [{"source_gdrive_id": "3"}]},
              },
              1: {0: {"files": [
                  {"source_gdrive_id": "1"},
                  {"source_gdrive_id": "2"}
              ]}},
          },
          {1: {"files": ["1", "2", "3"]}, 2: {"files": ["1", "2"]}}
      ],

      [
          {0: {1: {"files": [{"source_gdrive_id": "3"}]}}},
          {1: {"files": ["3"]}, 2: {"files": []}},
      ],

      [
          {
              0: {
                  0: {"comment": {"description": "comment descr1"}},
                  1: {"comment": {"description": "comment descr2"}},
              },
              1: {0: {"comment": {"description": "comment descr1"}}}
          },
          {1: {"comments": [{'cad_id': 1, 'description': 'comment descr1'},
                            {'cad_id': 3, 'description': 'comment descr2'}]},
           2: {"comments": [{'cad_id': 2, 'description': 'comment descr1'}]}}
      ],

      [
          {0: {1: {"comment": {"description": "comment descr2"}}}},
          {
              1: {"comments": [
                  {'cad_id': 3, 'description': 'comment descr2'}
              ]},
              2: {"comments": []},
          }
      ],

      [
          {
              0: {
                  0: {"value": "cv", "title": "ct"},
                  1: {"value": "cv1", "title": "ct1"}
              },
              1: {0: {"value": "cv", "title": "ct"}}
          },
          {
              1: {"cavs": {'ct': 'cv', 'ct1': 'cv1'}},
              2: {"cavs": {'ct': 'cv'}}
          }
      ]
  )
  @ddt.unpack
  def test_convert_data(self, data, expected_result):
    """Test convert_data method"""
    builder = csvbuilder.MatrixCsvBuilder(create_input_data(data))
    self.assert_assessments(builder, create_assert_data(expected_result))

  def _set_assessments_values(self, builder, data):
    """Updates or creates AssessmentStub structures in builder

      Args:
        builder - CsvBuilder instance,
        data = {id: {key:value, }, }.
          id - assessment to update id,
          key - AssessmentStub attribute,
          value - new value for key attribute.
    """
    for assessment_id in data:
      self._set_assessment_values(builder.assessments[assessment_id],
                                  data[assessment_id])

  @staticmethod
  def _set_assessment_values(assessment, data):
    """Update AssessmentStub structure with appropriate data

      Args:
        assessment - AssessmentStub structure,
        data = {key: value, }.
          key - AssessmentStub attribute.
          value - new value for key attribute.
    """
    for key in data:
      setattr(assessment, key, data[key])

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_needs_verification_assessment(self):
    """Test assessment needs verification"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory()
      asmt.add_person_with_role_name(
          factories.PersonFactory(),
          "Verifiers"
      )
      cad_text = factories.CustomAttributeDefinitionFactory(
          title="test_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Text",
      )
    data = {
        "assessments_ids": [asmt.id],
        "attributes": [
            {
                "attribute_value": "cav_value",
                "attribute_title": cad_text.title,
                "attribute_type": "Text",
                "extra": {
                    "comment": {},
                    "urls": [],
                    "files": [],
                },
                "bulk_update": [
                    {
                        "assessment_id": asmt.id,
                        "attribute_definition_id": cad_text.id,
                        "slug": asmt.slug,
                    },
                ]
            }
        ]
    }
    builder = csvbuilder.MatrixCsvBuilder(data)
    expected_data = {
        asmt.id: {
            "files": [],
            "urls": [],
            "cavs": {"test_LCA": "cav_value"},
            "slug": asmt.slug,
            "verification": True,
            "comments": []
        }
    }
    self.assert_assessments(builder, expected_data)
    self.assertEqual(builder.assessment_ids, [asmt.id])

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_needs_verification_many_assessments(self):
    """Test multiple assessments and one needs verification"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory()
      asmt2 = factories.AssessmentFactory()
      asmt1.add_person_with_role_name(
          factories.PersonFactory(),
          "Verifiers"
      )
      cad1 = factories.CustomAttributeDefinitionFactory(
          title="Test text LCA",
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Text",
      )
      cad2 = factories.CustomAttributeDefinitionFactory(
          title="Test text LCA",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    asmt_ids = [asmt1.id, asmt2.id]
    data = {
        "assessments_ids": asmt_ids,
        "attributes": [
            {
                "attribute_value": "cav_value",
                "attribute_title": cad1.title,
                "attribute_type": "Text",
                "extra": {
                    "comment": {},
                    "urls": [],
                    "files": [],
                },
                "bulk_update": [
                    {
                        "assessment_id": asmt1.id,
                        "attribute_definition_id": cad1.id,
                        "slug": asmt1.slug,
                    },
                    {
                        "assessment_id": asmt2.id,
                        "attribute_definition_id": cad2.id,
                        "slug": asmt2.slug,
                    },
                ]
            },
        ]
    }
    builder = csvbuilder.MatrixCsvBuilder(data)
    expected_data = {
        asmt1.id: {
            "files": [],
            "urls": [],
            "cavs": {"Test text LCA": "cav_value"},
            "slug": asmt1.slug,
            "verification": True,
            "comments": []
        },
        asmt2.id: {
            "files": [],
            "urls": [],
            "cavs": {"Test text LCA": "cav_value"},
            "slug": asmt2.slug,
            "verification": False,
            "comments": []
        },
    }
    self.assert_assessments(builder, expected_data)
    self.assertEqual(set(builder.assessment_ids), set(asmt_ids))

  @unittest.skip(
      "Implementing transition to MatrixCsvBuilder for bulk operations"
  )
  def test_needs_verification_two_diff_cads(self):
    """Test two cads from two assessments"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory()
      asmt2 = factories.AssessmentFactory()
      asmt1.add_person_with_role_name(
          factories.PersonFactory(),
          "Verifiers"
      )
      cad1 = factories.CustomAttributeDefinitionFactory(
          title="test_LCA_1",
          definition_type="assessment",
          definition_id=asmt1.id,
          attribute_type="Text",
      )
      cad2 = factories.CustomAttributeDefinitionFactory(
          title="test_LCA_2",
          definition_type="assessment",
          definition_id=asmt2.id,
          attribute_type="Text",
      )
    asmt_ids = [asmt1.id, asmt2.id]
    data = {
        "assessments_ids": asmt_ids,
        "attributes": [
            {
                "attribute_value": "cav_value_1",
                "attribute_title": cad1.title,
                "attribute_type": "Text",
                "extra": {
                    "comment": {},
                    "urls": [],
                    "files": [],
                },
                "bulk_update": [
                    {
                        "assessment_id": asmt1.id,
                        "attribute_definition_id": cad1.id,
                        "slug": asmt1.slug,
                    },
                ]
            },
            {
                "attribute_value": "cav_value_2",
                "attribute_title": cad2.title,
                "attribute_type": "Text",
                "extra": {
                    "comment": {},
                    "urls": [],
                    "files": [],
                },
                "bulk_update": [
                    {
                        "assessment_id": asmt2.id,
                        "attribute_definition_id": cad2.id,
                        "slug": asmt2.slug,
                    },
                ]
            }
        ]
    }
    builder = csvbuilder.MatrixCsvBuilder(data)

    expected_data = {
        asmt1.id: {
            "files": [],
            "urls": [],
            "cavs": {"test_LCA_1": "cav_value_1"},
            "slug": asmt1.slug,
            "verification": True,
            "comments": []
        },
        asmt2.id: {
            "files": [],
            "urls": [],
            "cavs": {"test_LCA_2": "cav_value_2"},
            "slug": asmt2.slug,
            "verification": False,
            "comments": []
        },
    }
    self.assert_assessments(builder, expected_data)
    self.assertEqual(builder.assessment_ids, asmt_ids)

  @ddt.data(None, {})
  def test_attributes_extra_null(self, extra_data):
    """Test attributes extra data empty"""
    with factories.single_commit():
      asmt = factories.AssessmentFactory()
      cad = factories.CustomAttributeDefinitionFactory(
          title="Test_LCA",
          definition_type="assessment",
          definition_id=asmt.id,
          attribute_type="Text",
      )
    data = {
        "assessments_ids": [],
        "attributes": [{
            "assessment": {
                "id": asmt.id,
                "slug": asmt.slug,
            },
            "values": [{
                "value": "cav_value",
                "title": cad.title,
                "type": "Text",
                "definition_id": asmt.id,
                "id": cad.id,
                "extra": extra_data,
            }]
        }]
    }
    builder = csvbuilder.MatrixCsvBuilder(data)
    expected_data = {
        asmt.id: {
            "files": [],
            "urls": [],
            "cavs": {"Test_LCA": "cav_value"},
            "slug": asmt.slug,
            "verification": False,
            "comments": []
        }
    }
    self.assert_assessments(builder, expected_data)
    self.assertEqual([obj.id for obj in builder.assessments], [asmt.id])


class TestVerifyCsvBuilder(TestCase):
  """Class for testing VerifyCsvBuilder methods"""
  @freezegun.freeze_time("2019-10-21 10:28:34")
  def test_bulk_verify_csv(self):
    """Test building csv for bulk verify"""
    with factories.single_commit():
      asmt1 = factories.AssessmentFactory()
      asmt2 = factories.AssessmentFactory()
    builder = csvbuilder.VerifyCsvBuilder({
        "assessments_ids": [asmt1.id, asmt2.id],
        "attributes": [],
    })
    builded_list = builder.assessments_verify_to_csv()
    expected_list = [
        [u"Object type"],
        [u"Assessment", u"Code", u"State", u"Verified Date"],
        [u"", asmt1.slug, u"Completed", u"10/21/2019"],
        [u"", asmt2.slug, u"Completed", u"10/21/2019"],
    ]
    self.assertEqual(expected_list, builded_list)
