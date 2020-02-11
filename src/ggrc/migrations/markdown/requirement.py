# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Requirement attributes from HTML to markdown."""


from ggrc.migrations.markdown import base


class RequirementConverter(
    base.WithDefaultUpdateAttrMixin,
    base.BaseConverter,
):
  """Class for Requirement converter."""

  DEFINITION_TYPE = "requirement"
  OBJECT_TYPE = "Requirement"
  TABLE_NAME = "requirements"

  COLUMNS_TO_CONVERT = (
      "description",
      "notes",
      "test_plan",
  )
