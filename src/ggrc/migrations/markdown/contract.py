# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Contract attributes from HTML to markdown."""


from ggrc.migrations.markdown import base


class ContractConverter(
    base.WithDefaultUpdateAttrMixin,
    base.BaseConverter,
):
  """Class for Contract converter."""

  DEFINITION_TYPE = "contract"
  OBJECT_TYPE = "Contract"
  TABLE_NAME = "contracts"

  COLUMNS_TO_CONVERT = (
      "description",
      "notes",
      "test_plan",
  )
