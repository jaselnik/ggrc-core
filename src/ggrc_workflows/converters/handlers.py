# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


""" Module for all special column handlers for workflow objects """

from sqlalchemy import inspection

from ggrc import db
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.models import all_models
from ggrc_workflows import models as wf_models


class WorkflowColumnHandler(handlers.ParentColumnHandler):
  """Handler for workflow column in task groups."""

  parent = all_models.Workflow

  def parse_item(self):
    """Workflow column shouldn't be changed for TaskGroup."""
    obj = self.row_converter.obj
    workflow = db.session.query(
        wf_models.Workflow.slug
    ).filter_by(
        id=obj.workflow_id
    ).first()
    if workflow and workflow.slug != self.raw_value:
      self.add_error(errors.TASKGROUP_MAPPED_TO_ANOTHER_WORKFLOW,
                     slug=obj.slug)
    return super(WorkflowColumnHandler, self).parse_item()


class TaskGroupColumnHandler(handlers.ParentColumnHandler):
  """Handler for task group column in task group tasks."""

  parent = all_models.TaskGroup


class CycleTaskGroupColumnHandler(handlers.ParentColumnHandler):
  """Handler for cycle task group column in cycle task group tasks."""

  parent = all_models.CycleTaskGroup


class UnitColumnHandler(handlers.ColumnHandler):

  """Handler for workflow 'repeat every' units column."""

  def parse_item(self):
    """Parse Unit column value."""
    value = self.raw_value.lower()

    if self.value_explicitly_empty(value):
      self.set_empty = True
      value = None
    elif not value:
      value = None

    if not self.row_converter.is_new and self.raw_value:
      insp = inspection.inspect(self.row_converter.obj)
      unit_prev = getattr(insp.attrs, self.key).history.unchanged
      if value not in unit_prev:
        self.add_warning(errors.UNMODIFIABLE_COLUMN,
                         column_name=self.display_name)
        self.set_empty = False
      return None

    if value and value not in wf_models.Workflow.VALID_UNITS:
      self.add_error(errors.WRONG_VALUE_ERROR,
                     column_name=self.display_name)
      return None

    return value


class RepeatEveryColumnHandler(handlers.ColumnHandler):

  """Handler for workflow 'repeat every' column."""

  def parse_item(self):
    """Parse 'repeat every' value
    """
    value = self.raw_value

    if self.value_explicitly_empty(value):
      self.set_empty = True
      value = None
    elif value:
      try:
        value = int(self.raw_value)
        if not (0 < value < 31):
          raise ValueError
      except ValueError:
        self.add_error(errors.WRONG_VALUE_ERROR,
                       column_name=self.display_name)
        return
    else:
      # if it is an empty string
      value = None

    # check if value is unmodified for existing workflow
    if not self.row_converter.is_new and self.raw_value:
      insp = inspection.inspect(self.row_converter.obj)
      repeat_prev = getattr(insp.attrs, self.key).history.unchanged
      if value not in repeat_prev:
        self.add_warning(errors.UNMODIFIABLE_COLUMN,
                         column_name=self.display_name)
        self.set_empty = False
      return None

    return value

  def get_value(self):
    """Get 'Repeat Every' user readable value for Workflow."""
    value = super(RepeatEveryColumnHandler, self).get_value()
    if value:
      return str(value)
    return ""


class TaskTypeColumnHandler(handlers.ColumnHandler):

  """Handler for task type column in task group tasks."""

  type_map = {
      "rich text": "text",
      "dropdown": "menu",
      "drop down": "menu",
      "checkboxes": "checkbox",
      "checkbox": "checkbox",
  }

  reverse_map = {
      "text": "rich text",
      "menu": "dropdown",
      "checkbox": "checkbox"
  }

  def parse_item(self):
    """Parse task type column value."""
    value = self.type_map.get(self.raw_value.lower())
    if value is None:
      if self.raw_value.lower() in self.type_map.values():
        value = self.raw_value.lower()
    if value is None:
      value = self.row_converter.obj.default_task_type()
      default_value = self.reverse_map.get(value).title()
      if self.raw_value:
        self.add_warning(errors.WRONG_REQUIRED_VALUE,
                         value=self.raw_value,
                         column_name=self.display_name)
      else:
        self.add_warning(errors.MISSING_VALUE_WARNING,
                         default_value=default_value,
                         column_name=self.display_name)
    return value

  def get_value(self):
    """Get titled user readable value for taks type."""
    return self.reverse_map.get(self.row_converter.obj.task_type,
                                "rich text").title()


class CycleWorkflowColumnHandler(handlers.ExportOnlyColumnHandler):

  def get_value(self):
    return self.row_converter.obj.workflow.slug


class CycleColumnHandler(handlers.ExportOnlyColumnHandler):

  def get_value(self):
    return self.row_converter.obj.cycle.slug


class TaskDescriptionColumnHandler(handlers.TextColumnHandler):

  def set_obj_attr(self):
    """ Set task attribute based on task type """
    if not self.value or self.row_converter.ignore:
      return
    if self.row_converter.obj.task_type == "text":
      self.row_converter.obj.description = self.value
    else:
      options = [v.strip() for v in self.value.split(",")]
      self.row_converter.obj.response_options = options

  def get_value(self):
    if self.row_converter.obj.task_type == "text":
      return self.row_converter.obj.description
    else:
      return ", ".join(self.row_converter.obj.response_options)
