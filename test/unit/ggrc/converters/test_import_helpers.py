# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for functions inside import_helper module.
"""

import copy
import random
import unittest
import collections

import mock

from ggrc import app  # noqa - this is neede for imports to work
from ggrc.converters import import_helper
from ggrc.converters import get_exportables
from ggrc.converters import get_importables
from ggrc.converters import GGRC_IMPORTABLE_ONLY
from ggrc.converters.column_handlers import aggregate_column_handlers


class TestSplitArry(unittest.TestCase):
  """Class for testing the split array function
  """

  def test_sigle_block(self):
    """Test splitting of a single csv block

    The array represents a read csv file with no lines that contain only
    commas.
    """
    test_data = [
        ["Object type", "world"],
        ["hello", "world"],
        ["hello", "world"],
    ]
    offsets, data_blocks, _ = zip(*import_helper.split_array(test_data))
    self.assertEqual(len(data_blocks), 1)
    self.assertEqual(data_blocks[0], test_data)
    self.assertEqual(offsets[0], 0)

  def test_sigle_block_with_padding(self):
    """Test stripping away empty csv lins
    """
    test_data = [
        ["", ""],
        ["Object type", "world"],
        ["hello", "world", "uet"],
        ["hello", "world"],
        ["hello", "world"],
    ]
    offsets, data_blocks, _ = zip(*import_helper.split_array(test_data))
    self.assertEqual(len(data_blocks), 1)
    self.assertEqual(data_blocks[0], test_data[1:])
    self.assertEqual(offsets[0], 1)

    test_data = [
        ["", ""],
        ["", ""],
        ["", ""],
        ["Object type", "world"],
        ["hello", "world", "uet"],
        ["hello", "world"],
        ["hello", "world"],
        ["", ""],
        ["", ""],
    ]
    offsets, data_blocks, _ = zip(*import_helper.split_array(test_data))
    self.assertEqual(len(data_blocks), 1)
    self.assertEqual(data_blocks[0], test_data[3:7])
    self.assertEqual(offsets[0], 3)

  def test_multiple_blocks(self):
    """Test splitting blocks of csv file

    Test that split_array function splits a csv file by lines beginning with
    "Object type" cell
    """
    test_data = [
        ["", ""],
        ["Object type", "foo"],
        ["hello", "world", "uet"],
        ["", ""],
        ["Object type", "bar"],
        ["hello", "world"],
    ]
    offsets, data_blocks, _ = zip(*import_helper.split_array(test_data))
    self.assertEqual(len(data_blocks), 2)
    self.assertEqual(data_blocks[0], test_data[1:3])
    self.assertEqual(data_blocks[1], test_data[4:6])
    self.assertEqual(offsets[0], 1)
    self.assertEqual(offsets[1], 4)

    test_data = [
        ["", ""],
        ["Object type", "world"],
        ["hello", "world", "uet"],
        ["hello", "world"],
        ["", ""],
        ["", ""],
        ["Object type", "foo"],
        ["", ""],
        ["", ""],
        ["Object type", "bar"],
        ["hello", "world"],
        ["hello", "world"],
    ]
    offsets, data_blocks, _ = zip(*import_helper.split_array(test_data))
    self.assertEqual(len(data_blocks), 3)
    self.assertEqual(data_blocks[0], test_data[1:4])
    self.assertEqual(data_blocks[1], test_data[6:7])
    self.assertEqual(data_blocks[2], test_data[9:])
    self.assertEqual(offsets[0], 1)
    self.assertEqual(offsets[1], 6)
    self.assertEqual(offsets[2], 9)


class TestColumnOrder(unittest.TestCase):

  """Tests for colum order function.
  """

  def test_column_order(self):
    """Test sorting of columns by a predefined positions.

    The predefined positions for all columns can be found in reflection.py.
    Attr_list is created in an expected correct order, against which a newly
    ordered list is compared.
    """
    attr_list = [
        "slug",
        "title",
        "description",
        "notes",
        "test_plan",
        "owners",
        "start_date",
        "status",
        "kind",
        "name",
        "email",
        "is_enabled",
        "company",
        "documents_file",
        "documents_reference_url",
        "A Capital custom attribute",
        "a simple custom attribute",
        "some custom attribute",
        "map:A thing",
        "map:B thing",
        "map:c thing",
        "map:Program",
        "map:some other mapping",
    ]
    original_list = copy.copy(attr_list)
    for _ in range(10):
      random.shuffle(attr_list)
      column_order = import_helper.get_column_order(attr_list)
      self.assertEqual(original_list, column_order)


class TestModelColumntHandler(unittest.TestCase):

  """Tests for get handlers for current model"""

  def test_get_default(self):
    """test get default model handler"""

    test_handler = collections.namedtuple("TestHandler", [])
    test_class = collections.namedtuple("TestClass", [])

    tested_handlers_dict = {
        "col_a": test_handler,
        "col_b": test_handler,
    }

    with mock.patch(
        "ggrc.converters.column_handlers._DEFAULT_COLUMN_HANDLERS_DICT",
        tested_handlers_dict
    ):
      self.assertEqual({"col_a": test_handler, "col_b": test_handler},
                       aggregate_column_handlers(test_class))

  def test_get_custom(self):
    """Test get custom model handler"""
    test_handler = collections.namedtuple("TestHandler", [])
    test_custom_handler = collections.namedtuple("TestCustomHandler", [])
    test_custom_class = collections.namedtuple(
        "TestCustomClass",
        ["specific_column_handlers"]
    )
    test_custom_class.specific_column_handlers = mock.MagicMock(
        return_value={"col_a": test_custom_handler}
    )
    tested_handlers_dict = {
        "col_a": test_handler,
        "col_b": test_handler,
    }
    with mock.patch(
        "ggrc.converters.column_handlers._DEFAULT_COLUMN_HANDLERS_DICT",
        tested_handlers_dict
    ):
      self.assertEqual(
          {"col_a": test_custom_handler, "col_b": test_handler},
          aggregate_column_handlers(test_custom_class)
      )


class TestImportablesExportables(unittest.TestCase):

  """Test for existing importables and exportables"""

  def test_importable_only(self):
    """Test importable only objects not exists in exportables"""
    result_importables = set(get_importables().keys())
    result_exportables = set(get_exportables().keys())
    importable_only = set(GGRC_IMPORTABLE_ONLY.keys())
    self.assertTrue(importable_only.issubset(result_importables))
    self.assertFalse(importable_only.issubset(result_exportables))
