# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Policy attributes from HTML to markdown."""


from ggrc.migrations.markdown import base


class PolicyConverter(
    base.WithDefaultUpdateAttrMixin,
    base.BaseConverter,
):
  """Class for Policy converter."""

  DEFINITION_TYPE = "policy"
  OBJECT_TYPE = "Policy"
  TABLE_NAME = "policies"

  COLUMNS_TO_CONVERT = (
      "description",
      "notes",
      "test_plan",
  )
