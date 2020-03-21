# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
import datetime
import unittest

import ddt
import mock

from ggrc.query import builder
from ggrc.query import exceptions


@ddt.ddt
class TestQueryHelper(unittest.TestCase):
  # pylint: disable=protected-access
  """Basic unit tests QueryHelper methods."""

  @ddt.data(
      (set(), {}),
      (set(["key_1"]), {
          "left": "key_1",
          "op": {"name": "="},
          "right": "",
      }),
      (set(["key_1", "key_2"]), {
          "left": {
              "left": "key_2",
              "op": {"name": "="},
              "right": "",
          },
          "op": {"name": "AND"},
          "right": {
              "left": "key_1",
              "op": {"name": "!="},
              "right": "",
          },
      }),
      (set(), {
          "left": {
              "left": "5",
              "op": {"name": "="},
              "right": "",
          },
          "op": {"name": "="},
          "right": {
              "left": "key_1",
              "op": {"name": "!="},
              "right": "",
          },
      }),
  )
  @ddt.unpack
  def test_expression_keys(self, expected_result, expression):
    """ test expression keys function

    Make sure it works with:
      empty query
      simple query
      complex query
      invalid complex query
    """
    # pylint: disable=protected-access
    # needed for testing protected function inside the query helper
    query = mock.MagicMock()
    helper = builder.QueryHelper(query)

    self.assertEqual(expected_result, helper._expression_keys(expression))

  @ddt.data(
      ({
          "left": "verified",
          "op": {"name": "="},
          "right": "false",
      }, {
          "left": "verified",
          "op": {"name": "="},
          "right": "No",
      }),
      ({
          "left": {
              "left": "verified",
              "op": {"name": "="},
              "right": "true",
          },
          "op": {"name": "AND"},
          "right": {
              "left": "test field",
              "op": {"name": "="},
              "right": "test value",
          }
      }, {
          "left": {
              "left": "verified",
              "op": {"name": "="},
              "right": "Yes",
          },
          "op": {"name": "AND"},
          "right": {
              "left": "test field",
              "op": {"name": "="},
              "right": "test value",
          }
      }),
  )
  @ddt.unpack
  def test_find_verified_field(self, expr, expected_expr):
    """Test QueryHelper._find_verified_field method"""
    query = mock.MagicMock()
    helper = builder.QueryHelper(query)
    self.assertEqual(
        expected_expr,
        helper._find_verified_field(expr)
    )

  @ddt.data(
      ({
          "filters": {
              "expression": {
                  "left": "child_type",
                  "op": {"name": "="},
                  "right": "TestObject",
              },
          }
      }, "TestObject"),
      ({
          "filters": {
              "expression": {
                  "left": {
                      "left": "child_type",
                      "op": {"name": "="},
                      "right": "TestObject",
                  },
                  "op": {"name": "AND"},
                  "right": {
                      "left": "test field",
                      "op": {"name": "="},
                      "right": "test value",
                  },
              }
          }
      }, "TestObject")
  )
  @ddt.unpack
  def test_get_snapshot_child_type(
      self,
      object_query,
      expected_child_type
  ):
    """Test QueryHelper._get_snapshot_child_type method"""
    query = mock.MagicMock()
    helper = builder.QueryHelper(query)
    self.assertEqual(
        helper._get_snapshot_child_type(object_query),
        expected_child_type,
    )

  def test_missed_object_name(self):
    """Test error init QueryHelper with query not contains object_name"""
    with self.assertRaises(exceptions.BadQueryException) as err:
      builder.QueryHelper([{}])
    self.assertEqual(
        str(err.exception),
        "`object_name` required for each object block",
    )

  @ddt.data(
      ({
          "object_name": "TaskGroupTask",
          "filters": {
              "expression": {
                  "left": "start",
                  "op": {"name": "="},
                  "right": "10/11/2012",
              }
          }
      }, {
          "ids": [],
          "left": "start_date",
          "op": {"name": "="},
          "right": datetime.date(2012, 10, 11),
      }), ({
          "object_name": "TaskGroupTask",
          "filters": {
              "expression": {
                  "left": "start",
                  "op": {"name": "="},
                  "right": "10/11",
              }
          }
      }, {
          "ids": [],
          "left": {
              "op": {"name": "="},
              "left": "relative_start_month",
              "right": "10",
          },
          "op": {"name": "AND"},
          "right": {
              "op": {"name": "="},
              "left": "relative_start_day",
              "right": "11",
          }
      }), ({
          "object_name": "TaskGroupTask",
          "filters": {
              "expression": {
                  "left": "start",
                  "op": {"name": "="},
                  "right": "11",
              }
          },
      }, {
          "ids": [],
          "left": "relative_start_day",
          "op": {"name": "="},
          "right": "11",
      })
  )
  @ddt.unpack
  def test_tgt_filter_all_date(self, query, expected_expression):
    """Test QueryHelper._macro_expand_object_query for date formats"""
    self.assertEqual(
        builder.QueryHelper([query]).query[0]["filters"]["expression"],
        expected_expression
    )

  @ddt.data(
      (
          "one/two/three",
          "Date must consist of numbers",
      ),
      (
          "10/11/2011/59",
          "Field start should be a date of one of the "
          "following forms: DD, MM/DD, MM/DD/YYYY",
      ),
  )
  @ddt.unpack
  def test_tgt_data_error(self, data_value, error_message):
    """Test QueryHelper._macro_expand_object_query for invalid date"""
    query = [{
        "object_name": "TaskGroupTask",
        "filters": {
            "expression": {
                "left": "start",
                "op": {"name": "="},
                "right": data_value,
            }
        },
    }]
    with self.assertRaises(exceptions.BadQueryException) as err:
      builder.QueryHelper(query)
    self.assertEqual(
        str(err.exception),
        error_message
    )
