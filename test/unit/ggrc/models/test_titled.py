# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Titled mixin."""

import unittest

import ddt

from ggrc.models.mixins import Titled


@ddt.ddt
class TestTitled(unittest.TestCase):
  """Test cases for Titled mixin."""

  def setUp(self):
    self.titled = Titled()

  @ddt.data(None, "", " ", "     ")
  def test_validate_title_throws_error(self, title):
    """Test title validation with invalid values,
    should raises ValueError if title is invalid."""
    # pylint: disable=invalid-name

    with self.assertRaises(ValueError) as cm_err:
      self.titled.validate_title("title", title)
    exc_msg = cm_err.exception
    self.assertIn("'title' must be specified", exc_msg)

  @ddt.data(("123", "123"),
            ("   123", "123"),
            ("   123   ", "123"),
            ("123   ", "123"),)
  @ddt.unpack
  def test_validate_title(self, before, after):
    """Test title validation with valid values."""
    title = self.titled.validate_title("title", before)
    self.assertEqual(title, after)
