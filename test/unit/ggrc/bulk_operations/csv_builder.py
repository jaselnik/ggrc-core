# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>]

"""Test csv builder methods for assessments bulk complete"""

import copy
import unittest

import ddt

from ggrc.bulk_operations import csvbuilder


CAVS_STUB = [{"attribute_value": "cav_value",
              "attribute_title": "cav_title",
              "extra": {
                  "comment": {},
                  "urls": [],
                  "files": [],
              },
             "bulk_update": [{"assessment_id": 1,
                              "attribute_definition_id": 1,
                              "slug": "slug1"},
                             {"assessment_id": 2,
                              "attribute_definition_id": 2,
                              "slug": "slug2"}]},
             {"attribute_value": "cav_value1",
              "attribute_title": "cav_title1",
              "extra": {
                  "comment": {},
                  "urls": [],
                  "files": [],
              },
              "bulk_update": [{"assessment_id": 1,
                               "attribute_definition_id": 3,
                               "slug": "slug1"}]}]

EXPECTED_STUB = {1: {"files": [],
                     "urls": [],
                     "cavs": {'cav_title1': 'cav_value1',
                              'cav_title': 'cav_value'},
                     "slug": "slug1",
                     "comments": []},
                 2: {"files": [],
                     "urls": [],
                     "cavs": {'cav_title': 'cav_value'},
                     "slug": "slug2",
                     "comments": []}}


def create_input_data(cavs_data):
  """Update input CAVS_STUB-like structure with appropriate data

    Args:
      cavs_data: {ind: {key:value, }, }.
        ind - indexes of CAVS_STUB list (0,1) to update,
        key - fields to be updated in stub,
        value - values for appropriate fields.
  """
  input_data = copy.deepcopy(CAVS_STUB)
  for cav_data in cavs_data:
    for key in cavs_data[cav_data]:
      if key in input_data[cav_data]:
        input_data[cav_data][key] = cavs_data[cav_data][key]
      else:
        input_data[cav_data]["extra"][key] = cavs_data[cav_data][key]
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
class TestCsvBuilder(unittest.TestCase):
  """Class for testing CsvBuilder methods"""

  def assert_assessments(self, builder, assert_data):
    """Asserts all assessments in builder"""
    for assessment in builder.assessments:
      self.assert_assessment(builder.assessments[assessment],
                             assert_data[assessment])

  def assert_assessment(self, assessment, expected_dict):
    """Asserts single AssessmentStub fields"""
    self.assertEqual(assessment.files, expected_dict["files"])
    self.assertEqual(assessment.urls, expected_dict["urls"])
    self.assertEqual(assessment.cavs, expected_dict["cavs"])
    self.assertEqual(assessment.slug, expected_dict["slug"])
    self.assertEqual(assessment.comments, expected_dict["comments"])

  @ddt.data(
      [{}, {}],

      [{0: {"urls": ["1", "2"]}, 1: {"urls": ["3"]}},
       {1: {"urls": ["1", "2", "3"]}, 2: {"urls": ["1", "2"]}}],

      [{1: {"urls": ["3"]}},
       {1: {"urls": ["3"]}, 2: {"urls": []}}],

      [{0: {"files": [{"source_gdrive_id": "1"}, {"source_gdrive_id": "2"}]},
        1: {"files": [{"source_gdrive_id": "3"}]}},
       {1: {"files": ["1", "2", "3"]}, 2: {"files": ["1", "2"]}}],

      [{1: {"files": [{"source_gdrive_id": "3"}]}},
       {1: {"files": ["3"]}, 2: {"files": []}}],

      [{0: {"comment": {"description": "comment descr1"}},
        1: {"comment": {"description": "comment descr2"}}},
       {1: {"comments": [{'cad_id': 1, 'description': 'comment descr1'},
                         {'cad_id': 3, 'description': 'comment descr2'}]},
        2: {"comments": [{'cad_id': 2, 'description': 'comment descr1'}]}}],

      [{1: {"comment": {"description": "comment descr2"}}},
       {1: {"comments": [{'cad_id': 3, 'description': 'comment descr2'}]},
        2: {"comments": []}}],

      [{0: {"attribute_value": "cv", "attribute_title": "ct"},
        1: {"attribute_value": "cv1", "attribute_title": "ct1"}},
       {1: {"cavs": {'ct': 'cv', 'ct1': 'cv1'}},
        2: {"cavs": {'ct': 'cv'}}}]
  )
  @ddt.unpack
  def test_convert_data(self, data, expected_result):
    """Test convert_data method"""
    builder = csvbuilder.CsvBuilder(create_input_data(data))
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

  @ddt.data(
      [{}, [], []],

      [{1: {"cavs": {"title1": "value1", "title2": "value2"}},
        2: {"cavs": {"title3": "value3", "title4": "value4"}}},
       ["title1", "title2", "title3", "title4"],
       [1, 2]],

      [{1: {"cavs": {"title1": "v1", "title2": "v2"}},
        2: {"cavs": {"title3": "v3", "title4": "v4"}},
        3: {"cavs": {"title3": "v3", "title1": "v4"}},
        4: {"cavs": {"title2": "v3", "title1": "v4"}}},
       ["title1", "title2", "title3", "title4"],
       [1, 2, 3, 4]],

      [{1: {"cavs": {}},
        2: {"cavs": {"title3": "value3", "title4": "value4"}},
        3: {"cavs": {}},
        4: {"cavs": {}}},
       ["title3", "title4"],
       [1, 2, 3, 4]],

      [{1: {"cavs": {"title1": "value1", "title2": "value3"}},
        2: {"cavs": {"title1": "value1", "title2": "value4"}}},
       ["title1", "title2"],
       [1, 2]],

      [{1: {"cavs": {"title1": "value1"}},
        2: {"cavs": {"title1": "value1", "title2": "value2"}}},
       ["title1", "title2"],
       [1, 2]],
  )
  @ddt.unpack
  def test_collect_keys(self, cavs, expected_keys, expected_ids):
    """Test _collect_keys method"""
    builder = csvbuilder.CsvBuilder({})
    self._set_assessments_values(builder, cavs)
    # pylint:disable=protected-access
    builder._collect_keys()
    self.assertEqual(builder.cav_keys, expected_keys)
    self.assertEqual(builder.assessment_ids, expected_ids)
