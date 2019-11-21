# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Workflow object and WorkflowState mixins.

This contains the basic Workflow object and a mixin for determining the state
of the Objects that are mapped to any cycle tasks.
"""
import calendar
import itertools
import datetime
from dateutil import relativedelta

from sqlalchemy import case
from sqlalchemy import orm
from sqlalchemy.ext import hybrid

from ggrc import builder
from ggrc import db
from ggrc.access_control import roleable, role
from ggrc.fulltext import attributes
from ggrc.fulltext.mixin import Indexed
from ggrc.login import get_current_user
from ggrc.models import mixins
from ggrc.models.mixins import base
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models.context import HasOwnContext
from ggrc.models.deferred import deferred


class Workflow(roleable.Roleable,
               relationship.Relatable,
               mixins.CustomAttributable,
               HasOwnContext,
               mixins.Timeboxed,
               mixins.Described,
               mixins.Titled,
               mixins.Notifiable,
               mixins.Stateful,
               base.ContextRBAC,
               mixins.Slugged,
               mixins.Folderable,
               Indexed,
               db.Model):
  """Basic Workflow first class object.
  """
  __tablename__ = 'workflows'
  _title_uniqueness = False

  DRAFT = u"Draft"
  ACTIVE = u"Active"
  INACTIVE = u"Inactive"
  VALID_STATES = [DRAFT, ACTIVE, INACTIVE]

  @classmethod
  def default_status(cls):
    return cls.DRAFT

  parent_id = db.Column(
      db.Integer,
      db.ForeignKey('workflows.id', ondelete="SET NULL"),
      nullable=True,
  )
  notify_on_change = deferred(
      db.Column(db.Boolean, default=False, nullable=False), 'Workflow')
  notify_custom_message = deferred(
      db.Column(db.Text, nullable=False, default=u""), 'Workflow')

  object_approval = deferred(
      db.Column(db.Boolean, default=False, nullable=False), 'Workflow')

  recurrences = db.Column(db.Boolean, default=False, nullable=False)

  task_groups = db.relationship(
      'TaskGroup', backref='_workflow', cascade='all, delete-orphan')

  cycles = db.relationship(
      'Cycle', backref='_workflow', cascade='all, delete-orphan')

  next_cycle_start_date = db.Column(db.Date, nullable=True)

  non_adjusted_next_cycle_start_date = db.Column(db.Date, nullable=True)

  # this is an indicator if the workflow exists from before the change where
  # we deleted cycle objects, which changed how the cycle is created and
  # how objects are mapped to the cycle tasks
  is_old_workflow = deferred(
      db.Column(db.Boolean, default=False, nullable=True), 'Workflow')

  IS_VERIFICATION_NEEDED_DEFAULT = False
  is_verification_needed = db.Column(
      db.Boolean,
      default=IS_VERIFICATION_NEEDED_DEFAULT,
      nullable=False)

  repeat_every = deferred(db.Column(db.Integer, nullable=True, default=None),
                          'Workflow')
  DAY_UNIT = 'day'
  WEEK_UNIT = 'week'
  MONTH_UNIT = 'month'
  VALID_UNITS = (DAY_UNIT, WEEK_UNIT, MONTH_UNIT)
  unit = deferred(db.Column(db.Enum(*VALID_UNITS), nullable=True,
                            default=None), 'Workflow')
  repeat_multiplier = deferred(db.Column(db.Integer, nullable=False,
                                         default=0), 'Workflow')

  UNIT_FREQ_MAPPING = {
      None: "one_time",
      DAY_UNIT: "daily",
      WEEK_UNIT: "weekly",
      MONTH_UNIT: "monthly"
  }

  # pylint: disable=unnecessary-lambda
  REPEAT_MAPPING = {
      None: lambda px, sx: "off",
      DAY_UNIT: lambda px, sx: "every {}weekday{}".format(px, sx),
      WEEK_UNIT: lambda px, sx: "every {}week{}".format(px, sx),
      MONTH_UNIT: lambda px, sx: "every {}month{}".format(px, sx)
  }
  REPEAT_ORDER_MAPPING = {
      None: 0,
      DAY_UNIT: 1,
      WEEK_UNIT: 2,
      MONTH_UNIT: 3
  }

  @hybrid.hybrid_property
  def frequency(self):
    """Hybrid property for SearchAPI filtering backward compatibility"""
    return self.UNIT_FREQ_MAPPING[self.unit]

  @frequency.expression
  def frequency(self):
    """Hybrid property for SearchAPI filtering backward compatibility"""
    return case([
        (self.unit.is_(None), self.UNIT_FREQ_MAPPING[None]),
        (self.unit == self.DAY_UNIT, self.UNIT_FREQ_MAPPING[self.DAY_UNIT]),
        (self.unit == self.WEEK_UNIT, self.UNIT_FREQ_MAPPING[self.WEEK_UNIT]),
        (self.unit == self.MONTH_UNIT,
         self.UNIT_FREQ_MAPPING[self.MONTH_UNIT]),
    ])

  @classmethod
  def _get_repeat(cls, unit, repeat_every):
    """Return repeat field representation for QueryAPI"""
    if repeat_every is None or repeat_every == 1:
      prefix, suffix = "", ""
    else:
      prefix, suffix = "{} ".format(repeat_every), "s"

    func = cls.REPEAT_MAPPING[unit]
    return func(prefix, suffix)

  @hybrid.hybrid_property
  def repeat(self):
    """Hybrid property for filtering in QueryAPI"""
    return self._get_repeat(self.unit, self.repeat_every)

  @repeat.expression
  def repeat(self):
    """Hybrid property for filtering in QueryAPI"""
    case_ = [(self.unit.is_(None), self.REPEAT_MAPPING[None](None, None))]
    case_.extend(((self.unit == unit) & (self.repeat_every == repeat_every),
                 self._get_repeat(unit, repeat_every))
                 for unit in self.VALID_UNITS
                 for repeat_every in xrange(1, 31))

    return case(case_)

  @property
  def repeat_order(self):
    """Property for ordering in QueryAPI"""
    unit_map = self.REPEAT_ORDER_MAPPING[self.unit]
    repeat_every_map = self.repeat_every or 0

    return u"{:0>4}_{:0>4}".format(unit_map, repeat_every_map)

  @builder.simple_property
  def can_start_cycle(self):
    """Can start cycle.

    Boolean property, returns True if all task groups have at least one
    task group task, False otherwise.
    """
    return not any(tg for tg in self.task_groups if not tg.task_group_tasks) \
        if self.task_groups else False

  @property
  def tasks(self):
    return list(itertools.chain(*[t.task_group_tasks
                                  for t in self.task_groups]))

  @property
  def min_task_start_date(self):
    """Fetches non adjusted setup cycle start date based on TGT user's setup.

    Args:
        self: Workflow instance.

    Returns:
        Date when first cycle should be started based on user's setup.
    """
    tasks = self.tasks
    min_date = None
    for task in tasks:
      min_date = min(task.start_date, min_date or task.start_date)
    return min_date

  WORK_WEEK_LEN = 5

  @classmethod
  def first_work_day(cls, day):
    """Get first work day."""
    while day.isoweekday() > cls.WORK_WEEK_LEN:
      day -= relativedelta.relativedelta(days=1)
    return day

  def calc_next_adjusted_date(self, setup_date):
    """Calculates adjusted date which are expected in next cycle.

    Args:
        setup_date: Date which was setup by user.

    Returns:
        Adjusted date which are expected to be in next Workflow cycle.
    """
    if self.repeat_every is None or self.unit is None:
      return self.first_work_day(setup_date)
    try:
      key = {
          self.WEEK_UNIT: "weeks",
          self.MONTH_UNIT: "months",
          self.DAY_UNIT: "days",
      }[self.unit]
    except KeyError:
      raise ValueError("Invalid Workflow unit")
    repeater = self.repeat_every * self.repeat_multiplier
    if self.unit == self.DAY_UNIT:
      weeks = repeater / self.WORK_WEEK_LEN
      days = repeater % self.WORK_WEEK_LEN
      # append weekends if it's needed
      days += ((setup_date.isoweekday() + days) > self.WORK_WEEK_LEN) * 2
      return setup_date + relativedelta.relativedelta(
          setup_date, weeks=weeks, days=days)
    calc_date = setup_date + relativedelta.relativedelta(
        setup_date,
        **{key: repeater}
    )
    if self.unit == self.MONTH_UNIT:
      # check if setup date is the last day of the month
      # and if it is then calc_date should be the last day of hte month too
      setup_day = calendar.monthrange(setup_date.year, setup_date.month)[1]
      if setup_day == setup_date.day:
        calc_date = datetime.date(
            calc_date.year,
            calc_date.month,
            calendar.monthrange(calc_date.year, calc_date.month)[1])
    return self.first_work_day(calc_date)

  @orm.validates('repeat_every')
  def validate_repeat_every(self, _, value):
    """Validate repeat_every field for Workflow.

    repeat_every shouldn't have 0 value.
    """
    if value is not None and not isinstance(value, (int, long)):
      raise ValueError("'repeat_every' should be integer or 'null'")
    if value is not None and value <= 0:
      raise ValueError("'repeat_every' should be strictly greater than 0")
    return value

  @orm.validates('unit')
  def validate_unit(self, _, value):
    """Validate unit field for Workflow.

    Unit should have one of the value from VALID_UNITS list or None.
    """
    if value is not None and value not in self.VALID_UNITS:
      raise ValueError("'unit' field should be one of the "
                       "value: null, {}".format(", ".join(self.VALID_UNITS)))
    return value

  @orm.validates('is_verification_needed')
  def validate_is_verification_needed(self, _, value):
    # pylint: disable=unused-argument
    """Validate is_verification_needed field for Workflow.

    It's not allowed to change is_verification_needed flag after creation.
    If is_verification_needed doesn't send,
    then is_verification_needed flag is True.
    """

    if self.is_verification_needed is None:
      return self.IS_VERIFICATION_NEEDED_DEFAULT if value is None else value
    if value is None:
      return self.is_verification_needed
    if self.status != self.DRAFT and value != self.is_verification_needed:
      raise ValueError("is_verification_needed value isn't changeble "
                       "on workflow with '{}' status".format(self.status))
    return value

  @builder.simple_property
  def workflow_state(self):
    return WorkflowState.get_workflow_state(self.cycles)

  @property
  def workflow_archived(self):
    """Determines whether workflow is archived."""
    return bool(self.unit and not self.recurrences and
                self.next_cycle_start_date)

  _sanitize_html = [
      'notify_custom_message',
  ]

  _fulltext_attrs = [
      attributes.CustomOrderingFullTextAttr(
          'repeat', 'repeat',
          order_prop_getter='repeat_order'
      )
  ]

  _api_attrs = reflection.ApiAttributes(
      'task_groups',
      'notify_on_change',
      'notify_custom_message',
      'cycles',
      'recurrences',
      'is_verification_needed',
      'repeat_every',
      'unit',
      reflection.Attribute('object_approval', update=False),
      reflection.Attribute('next_cycle_start_date',
                           create=False, update=False),
      reflection.Attribute('can_start_cycle', create=False, update=False),
      reflection.Attribute('non_adjusted_next_cycle_start_date',
                           create=False, update=False),
      reflection.Attribute('workflow_state',
                           create=False, update=False),
      reflection.Attribute('repeat',
                           create=False, update=False)
  )

  _aliases = {
      "repeat_every": {
          "display_name": "Repeat Every",
          "description": "'Repeat Every' value\nmust fall into\nthe range 1~30"
                         "\nor '-' for None",
      },
      "unit": {
          "display_name": "Unit",
          "description": "Allowed values are:\n{}".format(
              "\n".join(VALID_UNITS)),
      },
      "is_verification_needed": {
          "display_name": "Need Verification",
          "mandatory": True,
          "description": "This field is not changeable\nafter "
                         "workflow activation."
                         "\nAllowed values are:\nyes\nno",
      },
      "notify_custom_message": "Custom email message",
      "notify_on_change": {
          "display_name": "Force real-time email updates",
          "mandatory": False,
          "description": "Allowed values are:\nYes\nNo"
      },
      "status": None,
      "start_date": None,
      "end_date": None,
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for workflow obj"""
    from ggrc.converters.handlers import boolean
    from ggrc_workflows.converters import handlers
    return {
        "unit": handlers.UnitColumnHandler,
        "notify_on_change": boolean.CheckboxColumnHandler,
        "repeat_every": handlers.RepeatEveryColumnHandler,
    }

  def copy(self, _other=None, **kwargs):
    """Create a partial copy of the current workflow.
    """
    columns = ['title',
               'description',
               'notify_on_change',
               'notify_custom_message',
               'end_date',
               'start_date',
               'repeat_every',
               'unit',
               'parent_id',
               'is_verification_needed']
    kwargs['parent_id'] = self.id
    if kwargs.get('clone_people', False):
      access_control_list = [
          {
              "ac_role_id": acl.ac_role.id,
              "person": {"id": person.id}
          }
          for person, acl in self.access_control_list
      ]
    else:
      role_id = {
          name: ind
          for (ind, name) in role.get_custom_roles_for(self.type).iteritems()
      }['Admin']
      access_control_list = [{"ac_role_id": role_id,
                              "person": {"id": get_current_user().id}}]
    target = self.copy_into(_other, columns,
                            access_control_list=access_control_list, **kwargs)
    return target

  def copy_task_groups(self, target, **kwargs):
    """Copy all task groups and tasks mapped to this workflow.
    """
    for task_group in self.task_groups:
      obj = task_group.copy(
          workflow=target,
          context=target.context,
          clone_people=kwargs.get("clone_people", False),
          clone_objects=kwargs.get("clone_objects", False),
          modified_by=get_current_user(),
      )
      target.task_groups.append(obj)

      if kwargs.get("clone_tasks"):
        task_group.copy_tasks(
            obj,
            clone_people=kwargs.get("clone_people", False),
            clone_objects=kwargs.get("clone_objects", True)
        )

    return target

  @classmethod
  def eager_query(cls, **kwargs):
    return super(Workflow, cls).eager_query(**kwargs).options(
        orm.subqueryload('cycles').undefer_group('Cycle_complete')
           .subqueryload("cycle_task_group_object_tasks")
           .undefer_group("CycleTaskGroupObjectTask_complete"),
        orm.subqueryload('task_groups').undefer_group('TaskGroup_complete'),
        orm.subqueryload(
            'task_groups'
        ).subqueryload(
            "task_group_tasks"
        ).undefer_group(
            'TaskGroupTask_complete'
        ),
    )

  @classmethod
  def indexed_query(cls):
    return super(Workflow, cls).indexed_query().options(
        orm.Load(cls).undefer_group(
            "Workflow_complete",
        ),
    )


class WorkflowState(object):
  """Object state mixin.

  This is a mixin for adding workflow_state to all objects that can be mapped
  to workflow tasks.
  """

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('workflow_state', create=False, update=False)
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

  @builder.simple_property
  def workflow_state(self):
    return WorkflowState.get_object_state(self.cycle_task_group_object_tasks)
