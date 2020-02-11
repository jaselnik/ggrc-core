# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Threat attributes from HTML to markdown."""


from ggrc.migrations.markdown import base


class ThreatConverter(
    base.WithDefaultUpdateAttrMixin,
    base.BaseConverter,
):
  """Class for Threat converter."""

  DEFINITION_TYPE = "threat"
  OBJECT_TYPE = "Threat"
  TABLE_NAME = "threats"

  COLUMNS_TO_CONVERT = (
      "description",
      "notes",
      "test_plan",
  )
