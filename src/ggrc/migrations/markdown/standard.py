# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Standard attributes from html to markdown."""


from ggrc.migrations.markdown import directives


class StandardConverter(directives.DirectivesConverter):
  """Class for Standard converter."""

  DEFINITION_TYPE = 'standard'
  OBJECT_TYPE = 'Standard'
