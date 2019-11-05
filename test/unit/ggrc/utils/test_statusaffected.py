# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Unit tests for utils statusaffected."""

import unittest

import ddt
import mock

from ggrc.utils.statusaffected import statusaffected


@ddt.ddt
class TestStatusAffectedChanges(unittest.TestCase):
  """Unittests for statusaffected changes tracker validator."""

  @ddt.data(
      ("mock_obj_name", "mock_affected_name"),
      ("Evidence", "mock_affected_name"),
      ("Evidence", "Program"),
  )
  @ddt.unpack
  def test_track_wrong_objects(self, obj_name, affected_obj_name):
    """test for validate CAD checkbox type."""
    evindece = mock.MagicMock()
    evindece.__class__.__name__ = obj_name
    affected_obj = mock.MagicMock()
    affected_obj.__class__.__name__ = affected_obj_name

    result = statusaffected.StatusAffectedChanges(
        evindece, affected_obj).was_affected()

    self.assertTrue(result)
