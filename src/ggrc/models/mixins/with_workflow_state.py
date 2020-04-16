# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Object workflow_state mixin.

This is a mixin for adding workflow_state to all objects that can be mapped
to workflow tasks.
"""

from ggrc import db
from ggrc.models import reflection


class WithWorkflowState(object):
  """Object workflow_state mixin.

  This is a mixin for adding workflow_state to all objects that can be mapped
  to workflow tasks.
  """

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('workflow_state', create=False, update=False)
  )

  _aliases = {
      "workflow_state": None,
  }

  workflow_state = db.Column(
      "workflow_state",
      db.Enum("Overdue", "Verified", "Finished", "In Progress"),
      nullable=True,
      default=None,
  )
  OVERDUE = "Overdue"
  VERIFIED = "Verified"
  FINISHED = "Finished"
  ASSIGNED = "Assigned"
  IN_PROGRESS = "In Progress"
  UNKNOWN_STATE = None

  @classmethod
  def _get_state(cls, statusable_childs):
    """Get overall state of a group of tasks.

    Rules, the first that is true is selected:
      -if all are verified -> verified
      -if all are finished -> finished
      -if all are at least finished -> finished
      -if any are in progress or declined -> in progress
      -if any are assigned -> assigned

    The function will work correctly only for non Overdue states. If the result
    is overdue, it should be handled outside of this function.

    Args:
      current_tasks: list of tasks that are currently a part of an active
        cycle or cycles that are active in an workflow.

    Returns:
      Overall state according to the rules described above.
    """

    states = {i.status or i.ASSIGNED for i in statusable_childs}
    if states in [{cls.VERIFIED}, {cls.FINISHED}, {cls.ASSIGNED}]:
      return states.pop()
    if states == {cls.FINISHED, cls.VERIFIED}:
      return cls.FINISHED
    return cls.IN_PROGRESS if states else cls.UNKNOWN_STATE

  @classmethod
  def get_object_state(cls, objs):
    """Get lowest state of an object

    Get the lowest possible state of the tasks relevant to one object. States
    are scanned in order: Overdue, In Progress, Finished, Assigned, Verified.

    Args:
      objs: A list of cycle group object tasks, which should all be mapped to
        the same object.

    Returns:
      Name of the lowest state of all active cycle tasks that relate to the
      given objects.
    """
    current_tasks = []
    for task in objs:
      if not task.cycle.is_current:
        continue
      if task.is_overdue:
        return cls.OVERDUE
      current_tasks.append(task)
    return cls._get_state(current_tasks)

  @classmethod
  def get_workflow_state(cls, cycles):
    """Get lowest state of a workflow

    Get the lowest possible state of the tasks relevant to a given workflow.
    States are scanned in order: Overdue, In Progress, Finished, Assigned,
    Verified.

    Args:
      cycles: list of cycles belonging to a single workflow.

    Returns:
      Name of the lowest workflow state, if there are any active cycles.
      Otherwise it returns None.
    """
    current_cycles = []
    for cycle_instance in cycles:
      if not cycle_instance.is_current:
        continue
      for task in cycle_instance.cycle_task_group_object_tasks:
        if task.is_overdue:
          return cls.OVERDUE
      current_cycles.append(cycle_instance)
    return cls._get_state(current_cycles)
