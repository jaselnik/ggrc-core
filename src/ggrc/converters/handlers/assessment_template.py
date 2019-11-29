# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers for special object mappings."""

from ggrc import db
from ggrc.converters.handlers import handlers
from ggrc.converters import errors
from ggrc.models.hooks import assessment as asmt_hooks
from ggrc.models import assessment_template


class AssessmentTemplateColumnHandler(handlers.MappingColumnHandler):
  """Special handler for assessment template column only."""

  def parse_item(self):
    if len(self.raw_value.splitlines()) > 1:
      self.add_error(errors.WRONG_VALUE_ERROR, column_name=self.display_name)
      return None
    if self.raw_value in self.new_slugs:
      self.add_error(errors.UNSUPPORTED_OPERATION_ERROR, operation="Creating "
                     "and using assessment templates in one sheet")
      return None
    return super(AssessmentTemplateColumnHandler, self).parse_item()

  def set_obj_attr(self):
    self.value = self.parse_item()
    if not self.dry_run and self.row_converter.is_new:
      self.create_custom_attributes()
      self._set_verification_workflow()

  def insert_object(self):
    pass

  def create_custom_attributes(self):
    """Generates CADs instances for newly created Assessment instance."""
    if not self.value:
      return
    created_cads = asmt_hooks.relate_ca(self.row_converter.obj, self.value[0])
    # pylint: disable=protected-access
    if self.row_converter.block_converter._ca_definitions_cache:
      for cad in created_cads:
        key = (cad.definition_id, cad.title)
        self.row_converter.block_converter._ca_definitions_cache[key] = cad
    db.session.flush(created_cads)

  def _set_verification_workflow(self):
    """Set `sox_302_enabled` flag for newly created Assessment instance."""
    if not self.value:
      return

    assessment_template.AssessmentTemplate.set_verification_workflow(
        self.row_converter.obj,
        self.value[0],
    )

  def get_value(self):
    return ""
