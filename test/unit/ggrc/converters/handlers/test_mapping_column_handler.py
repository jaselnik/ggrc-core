# -*- coding: utf-8 -*-

# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for the MappingColumnHandler class"""

import unittest
from mock import MagicMock
from mock import patch

from ggrc.converters.handlers.handlers import MappingColumnHandler


class MappingColumnHandlerTestCase(unittest.TestCase):
  """Base class for MappingColumnHandler tests"""
  def setUp(self):
    row_converter = MagicMock(name=u"row_converter")
    key = u"field_foo"
    self.handler = MappingColumnHandler(row_converter, key)


class IsAllowedMappingByTypeTestCase(MappingColumnHandlerTestCase):
  """Tests for the _is_allowed_mapping_by_type() method"""
  # pylint: disable=invalid-name

  def test_returns_false_for_regulation(self):
    """The method should return True if destination is 'Regulation'."""
    # pylint: disable=protected-access
    result = self.handler._is_allowed_mapping_by_type('Product', 'Regulation')
    self.assertFalse(result)

  def test_returns_false_for_standard(self):
    """The method should return True if destination is 'Standard'."""
    # pylint: disable=protected-access
    result = self.handler._is_allowed_mapping_by_type('Product', 'Standard')
    self.assertFalse(result)

  def test_returns_true_for_other_types(self):
    """The method should return True if destination is other."""
    # pylint: disable=protected-access
    result = self.handler._is_allowed_mapping_by_type('Product', 'Issue')
    self.assertTrue(result)

  def test_returns_false_for_product_control(self):
    """The method should return False if destination is other."""
    # pylint: disable=protected-access
    result = self.handler._is_allowed_mapping_by_type('Product', 'Control')
    self.assertFalse(result)


class AddMappingWarningTestCase(MappingColumnHandlerTestCase):
  """Tests for the _add_mapping_warning() method"""
  # pylint: disable=invalid-name

  def test_count_warnings_where_unmap_and_mapping(self):
    """The method should return True if unmap = true and mapping isset."""
    self.handler.raw_value = u""

    with patch('ggrc.models.all_models.Relationship.find_related',
               side_effect=lambda args, opts: True):
      self.handler.unmap = True

      # pylint: disable=protected-access
      self.handler._add_mapping_warning({}, {})
      self.assertEqual(self.handler.row_converter.add_warning.call_count, 1)

  def test_count_warnings_where_map_and_not_mapping(self):
    """The method should return True if unmap = false and mapping not is."""
    self.handler.raw_value = u""

    with patch('ggrc.models.all_models.Relationship.find_related',
               side_effect=lambda args, opts: False):
      self.handler.unmap = False

      # pylint: disable=protected-access
      self.handler._add_mapping_warning({}, {})
      self.assertEqual(self.handler.row_converter.add_warning.call_count, 1)

  def test_count_warnings_where_map_and_mapping(self):
    """The method should return True if unmap = false and mapping is."""
    self.handler.raw_value = u""

    with patch('ggrc.models.all_models.Relationship.find_related',
               side_effect=lambda args, opts: True):
      self.handler.unmap = False

      # pylint: disable=protected-access
      self.handler._add_mapping_warning({}, {})
      self.assertEqual(self.handler.row_converter.add_warning.call_count, 0)

  def test_count_warnings_where_unmap_and_not_mapping(self):
    """The method should return True if unmap = true and mapping not is."""
    self.handler.raw_value = u""

    with patch('ggrc.models.all_models.Relationship.find_related',
               side_effect=lambda args, opts: False):
      self.handler.unmap = True

      # pylint: disable=protected-access
      self.handler._add_mapping_warning({}, {})
      self.assertEqual(self.handler.row_converter.add_warning.call_count, 0)
