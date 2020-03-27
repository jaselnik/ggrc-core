# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests generation of import template for core objects."""

import ddt

from integration.ggrc import TestCase


@ddt.ddt
class TestExportImportCoreObjectTemplate(TestCase):
  """Tests generation of import template for core objects."""

  def setUp(self):
    """Set up for test cases."""
    super(TestExportImportCoreObjectTemplate, self).setUp()
    self.client.get("/login")

  @ddt.data(
      ('Standard', ('map:regulation', 'map:requirement', 'map:contract',
                    'map:policy'), ('map:standard', )),
      ('Regulation', ('map:standard', 'map:requirement', 'map:contract',
                      'map:policy'), ('map:regulation',)),
      ('Assessment', [], ('Last Deprecated Date',))
  )
  @ddt.unpack
  def test_columns(self, obj_type, expected, not_expected):
    """Test generation of csv template for object - {obj_type}"""
    objects = [{"object_name": obj_type}]

    response = self.export_csv_template(objects)
    for column in expected:
      self.assertIn(column, response.data)

    for column in not_expected:
      self.assertNotIn(column, response.data)
