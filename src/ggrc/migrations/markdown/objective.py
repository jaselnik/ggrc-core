# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Objective attributes from HTML to markdown."""


from ggrc.migrations.markdown import base


class ObjectiveConverter(
    base.WithDefaultUpdateAttrMixin,
    base.BaseConverter,
):
  """Class for Objective converter."""

  DEFINITION_TYPE = "objective"
  OBJECT_TYPE = "Objective"
  TABLE_NAME = "objectives"

  COLUMNS_TO_CONVERT = (
      "description",
      "notes",
      "test_plan",
  )
