# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Checker function for import pre commit hooks."""

from ggrc.converters import errors
from ggrc.models import all_models


def check_tasks(row_converter):
  """Checker for task group task objects.

  This checker should make sure if a task group task has any invalid values
  that should be ignored. Object will not be checked if there's already
  an error on and it's marked as ignored.

  Args:
    row_converter: RowConverter object with row data for a task group task
      import.
  """
  if row_converter.ignore:
    return

  obj = row_converter.obj
  if obj.start_date > obj.end_date:
    row_converter.add_error(
        errors.INVALID_START_END_DATES,
        start_date="Task Start Date",
        end_date="Task Due Date",
    )

  if obj.start_date.isoweekday() > all_models.Workflow.WORK_WEEK_LEN:
    row_converter.add_error(errors.START_DATE_ON_WEEKEND_ERROR)

  if obj.end_date.isoweekday() > all_models.Workflow.WORK_WEEK_LEN:
    row_converter.add_error(errors.END_DATE_ON_WEEKEND_ERROR)


def check_cycle_tasks(row_converter):  # noqa
  """Checker for CycleTaskGroupObjectTask model objects.

  This checker should make sure if a cycle-task has any invalid values
  that should be ignored during update via import.

  Args:
    row_converter: RowConverter object with row data for a cycle-task
      import.
  """
  # Cycle-Task creation is denied. Don't need checks for new items.
  if row_converter.is_new:
    return
  obj = row_converter.obj
  if obj.start_date > obj.end_date:
    row_converter.add_error(
        errors.INVALID_START_END_DATES,
        start_date="Start Date",
        end_date="Due Date",
    )


def check_workflows(row_converter):
  """Checker for Workflow object.

  Check if a Workflow has any invalid values. If so, it should be ignored.
  Object will not be checked if there's already an error exists
  and it's marked as ignored.

  Args:
    row_converter: RowConverter object with row data for a task group task
      import.
  """
  if row_converter.ignore:
    return

  obj = row_converter.obj
  if (obj.unit is None and obj.repeat_every is not None or
          obj.unit is not None and obj.repeat_every is None):
    row_converter.add_error(
        errors.VALIDATION_ERROR,
        column_name="'repeat_every', 'unit'",
        message="'repeat_every' and 'unit' fields can be set to NULL only"
                " simultaneously",
    )


def check_assessment(row_converter):
  """Checker for Assessment model instance.

  This checker should make sure if an assessment are invalid or non-importable
  and should be ignored.

  Args:
      row_converter: RowConverter object with row data for an assessment
        import.
      kwargs: Dict with options.
  """
  if row_converter.obj.archived:
    row_converter.add_error(errors.ARCHIVED_IMPORT_ERROR)


def _is_done_or_end_state(obj):
  """Check Assessment status.

  Status should be 'Completed and verified', 'Verified',
  'In Review' or 'Rework Needed'.

  Args:
    obj: db.Model instance.

  Returns:
     Boolean: indicated that obj in 'Completed and verified', 'Verified',
    'In Review' or 'Rework Needed' status.
  """
  in_done_state = obj.status in {obj.DONE_STATE, obj.REWORK_NEEDED}
  in_end_state = obj.status in obj.END_STATES and obj.verified
  return in_done_state or in_end_state


def secondary_check_assessment(row_converter):
  """Check Assessment after setup of secondary objects

  Assessment can't be imported with 'Completed and verified', 'Verified',
  'In Review', 'Rework Needed' state if don't have Verifier

  Assessment can't be imported with 'Completed' state if any
  assessment precondition failed"""

  obj = row_converter.obj
  if (_is_done_or_end_state(obj) and not obj.verifiers and
          not row_converter.status_changing):
    row_converter.add_warning(errors.NO_VERIFIER_WARNING, status=obj.status)
    # In case of import new asmt with 'Rework Needed' status
    # we can't change it to default state because of validation
    obj.skip_rework_validation = True
    obj.status = row_converter.initial_state.status or obj.default_status()

  old_value = row_converter.initial_state.status
  new_value = obj.status
  if old_value in obj.NOT_DONE_STATES and new_value in obj.DONE_STATES:
    if hasattr(obj, "preconditions_failed") and obj.preconditions_failed:
      row_converter.add_error_slug()
      row_converter.add_warning(errors.NO_REQUIRED_ANSWERS_WARNING)
      obj.status = old_value or obj.default_status()


def check_assessment_template(row_converter):
  """Checker for AssessmentTemplate model objects.

  This checker sets default_people attribute from values of default_assignees
  and default_verifier.

  Args:
     row_converter: RowConverter object with row data for a cycle-task
     import.
  """
  if row_converter.ignore:
    return

  key_map = {
      "default_assignees": "assignees",
      "default_verifier": "verifiers",
  }
  key_map_inverse = {
      "assignees": "default_assignees",
      "verifiers": "default_verifier",
  }
  default_empty_value = "--"

  default_people = {}
  _errors, _warnings = row_converter.obj.get_import_errors()
  for error in _errors:
    row_converter.add_error(error)
  for warning in _warnings:
    row_converter.add_warning(warning)

  for key, value in key_map.iteritems():
    default_people[value] = getattr(row_converter.obj, key, "")

  if not row_converter.obj.default_people:
    row_converter.obj.default_people = default_people
    return

  for key, value in default_people.iteritems():
    header = row_converter.headers.get(key_map_inverse[key], None)
    previous_value = row_converter.obj.default_people.get(key, "")
    if not header:
      default_people[key] = previous_value
      continue

    index = row_converter.headers.keys().index(key_map_inverse[key])
    raw_value = row_converter.row[index]

    if raw_value == default_empty_value:
      default_people[key] = None
    elif not value:
      default_people[key] = None if row_converter.is_new else previous_value

  row_converter.obj.default_people = default_people


CHECKS = {
    "TaskGroupTask": check_tasks,
    "CycleTaskGroupObjectTask": check_cycle_tasks,
    "Workflow": check_workflows,
    "Assessment": check_assessment,
    "AssessmentTemplate": check_assessment_template,
}

SECONDARY_CHECKS = {
    "Assessment": secondary_check_assessment
}
