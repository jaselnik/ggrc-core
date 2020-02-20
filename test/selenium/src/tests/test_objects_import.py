# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Objects imports tests."""
# pylint: disable=no-self-use
# pylint: disable=unused-argument
from lib import base
from lib.constants import objects
from lib.page.modal import download_template
from lib.service import webui_facade


class TestObjectsImport(base.Test):
  """Tests for objects import functionality."""

  def test_available_template_types(self, selenium):
    """Check available template types list is valid in dropdown on
    Download Template modal."""
    expected_list = sorted([objects.get_normal_form(obj_name)
                            for obj_name in list(objects.IMPORTABLE_OBJECTS) +
                            [download_template.SELECT_ALL_OPTION]])
    available_templates = webui_facade.get_available_templates_list()
    assert available_templates == expected_list
