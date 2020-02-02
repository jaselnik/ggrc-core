# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for convert Regulation attributes from html to markdown."""


from ggrc.migrations.markdown import directives


class RegulationConverter(directives.DirectivesConverter):
  """Class for Regulation converter."""

  DEFINITION_TYPE = 'regulation'
  OBJECT_TYPE = 'Regulation'
