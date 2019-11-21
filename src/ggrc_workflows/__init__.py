# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=redefined-outer-name

"""Workflows module"""

import collections
import itertools
import logging
from datetime import datetime, date
from flask import Blueprint
from sqlalchemy import inspect, orm

from ggrc import db
from ggrc.login import get_current_user, get_user_date
from ggrc.models import all_models
from ggrc.models.relationship import Relationship
from ggrc.rbac.permissions import is_allowed_update
from ggrc.access_control import role
from ggrc.services import signals
from ggrc.utils import benchmark
from ggrc.utils.log_event import log_event
from ggrc_workflows import models, notification
from ggrc_workflows import services
from ggrc_workflows.models import relationship_helper
from ggrc_workflows.models import WORKFLOW_OBJECT_TYPES
from ggrc_workflows.notification import pusher
from ggrc_workflows.converters import IMPORTABLE, EXPORTABLE
from ggrc_workflows.services.common import Signals
from ggrc_basic_permissions.contributed_roles import RoleContributions

# pylint: disable=invalid-name
logger = logging.getLogger(__name__)

COPY_TITLE_TEMPLATE = '%(parent_title)s (copy %(copy_count)s)'

# Initialize Flask Blueprint for extension
blueprint = Blueprint(
    'ggrc_workflows',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/ggrc_workflows',
)


_INJECTABLE_MIXINS = (
    models.cycle_task_group_object_task.CycleTaskable,
    models.workflow.WorkflowState,
)


def _inject_workflow_mixins():
  """Inject Workflow mixins to configured model classes"""

  # This function contains slightly refactored code which injects mixins
  # Mixin injection produces bad side effects, for now only one of them
  # is found and workarounded.
  # This code needs to be completely refactored!

  for type_ in WORKFLOW_OBJECT_TYPES:
    model = getattr(all_models, type_)
    model.__bases__ = _INJECTABLE_MIXINS + model.__bases__
    _workaround_mixin_injection(model)


def _workaround_mixin_injection(model):
  """Workaround mixin injection

  We inject mixin to existing Model, and mapper for this Model is
  already configured. So, all sqlalchemy attrs will not be added to mapper
  To resolve it, we need to add all attrs to mapper manually.
  """

  for mixin in _INJECTABLE_MIXINS:
    for attr_name in getattr(mixin, '_mapper_inject_properties', list()):
      model.__mapper__.add_property(attr_name, getattr(model, attr_name))


def get_public_config(current_user):  # noqa
  """Expose additional permissions-dependent config to client.
  """
  return {}


# Initialize service endpoints
def contributed_services():
  return services.contributed_services()


def contributed_object_views():
  """Contributed object views"""
  from ggrc.views.registry import object_view

  return [
      object_view(models.Workflow),
  ]


def get_copy_title(current_title, used_titles):
  """Get's first available copy title from the list of titles.
  In general, the convention is:
    title = old_title + (copy N)

  Args:
      current_title (str): Title of the parent object
      used_titles (List[str]): List of object titles copied from the same
          parent
  """
  copy_title = ''
  for copy_count in range(1, len(used_titles) + 2):
    title = COPY_TITLE_TEMPLATE % {
        'parent_title': current_title,
        'copy_count': copy_count
    }
    if title not in used_titles:
      copy_title = title
      break
  return copy_title


def _get_min_next_due_date(due_dated_objects):
  next_due_date = None

  for obj in due_dated_objects:
    if not obj.is_done:
      obj_next_due_date = obj.next_due_date
      if isinstance(obj_next_due_date, datetime):
        obj_next_due_date = obj_next_due_date.date()
      if obj_next_due_date is not None:
        if next_due_date is None or next_due_date > obj_next_due_date:
          next_due_date = obj_next_due_date

  return next_due_date


def _get_min_end_date(timeboxed_objects):
  end_date = None
  for obj in timeboxed_objects:
    if not obj.is_done:
      obj_end_date = obj.end_date
      if isinstance(obj_end_date, datetime):
        obj_end_date = obj_end_date.date()
      if obj_end_date is not None:
        if end_date is None or end_date > obj_end_date:
          end_date = obj_end_date
  return end_date


def _get_date_range(timeboxed_objects):
  start_date = None
  end_date = None

  for obj in timeboxed_objects:
    obj_start_date = obj.start_date
    if isinstance(obj_start_date, datetime):
      obj_start_date = obj_start_date.date()
    obj_end_date = obj.end_date
    if isinstance(obj_end_date, datetime):
      obj_end_date = obj_end_date.date()
    if obj_start_date is not None:
      if start_date is None or start_date > obj_start_date:
        start_date = obj_start_date
    if obj_end_date is not None:
      if end_date is None or end_date < obj_end_date:
        end_date = obj_end_date
  return start_date, end_date


def update_cycle_dates(cycle):
  """ This gets all cycle task groups and tasks associated with a cycle and
  calculates the start and end date for the cycle by aggregating cycle task
  dates to cycle task groups and then cycle task group dates to cycle.

  Args:
    cycle: Cycle for which we want to calculate the start and end dates.

  """
  if not cycle.cycle_task_group_object_tasks:
    cycle.start_date, cycle.end_date = None, None
    cycle.next_due_date = None
    cycle.is_current = False
    return

  for ctg in cycle.cycle_task_groups:
    ctg.start_date, ctg.end_date = _get_date_range(
        ctg.cycle_task_group_tasks)
    ctg.next_due_date = _get_min_end_date(
        ctg.cycle_task_group_tasks)

  cycle.start_date, cycle.end_date = _get_date_range(cycle.cycle_task_groups)
  cycle.next_due_date = _get_min_next_due_date(cycle.cycle_task_groups)


def build_cycles(workflow, cycle=None, user=None):
  """Build all required cycles for current workflow.

  workflow: Workflow instance (required).
  cycle: Cycle instance (optional). Cycle instance that started at first.
  user: User isntance (optional). User who will be the creator of the cycles.
  """
  user = user or get_current_user()
  request_user_date = get_user_date()
  if not workflow.next_cycle_start_date:
    workflow.next_cycle_start_date = workflow.calc_next_adjusted_date(
        workflow.min_task_start_date)
  if cycle:
    build_cycle(workflow, cycle, user)
  if workflow.unit and workflow.repeat_every:
    while workflow.next_cycle_start_date <= request_user_date:
      build_cycle(workflow, current_user=user)


@signals.Restful.model_posted.connect_via(models.Cycle)
def handle_cycle_post(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  if not src.get('autogenerate', False):
    return
  # When called via a REST POST, use current user.
  workflow = obj.workflow
  workflow.status = workflow.ACTIVE
  if not workflow.can_start_cycle:
    raise ValueError("Workflow with misconfigured "
                     "Task Groups can not be activated.")
  build_cycles(workflow, obj)


def _create_cycle_task(task_group_task, cycle, cycle_task_group, current_user):
  """Create a cycle task along with relations to other objects"""
  description = models.CycleTaskGroupObjectTask.default_description if \
      task_group_task.object_approval else task_group_task.description

  workflow = cycle.workflow
  start_date = workflow.calc_next_adjusted_date(task_group_task.start_date)
  end_date = workflow.calc_next_adjusted_date(task_group_task.end_date)
  access_control_list = []
  for role_id, role_name in role.get_custom_roles_for(
          models.CycleTaskGroupObjectTask.__name__).iteritems():
    for person_id in task_group_task.get_person_ids_for_rolename(role_name):
      access_control_list.append(
          {"ac_role_id": role_id, "person": {"id": person_id}}
      )
  cycle_task_group_object_task = models.CycleTaskGroupObjectTask(
      context=cycle.context,
      cycle=cycle,
      cycle_task_group=cycle_task_group,
      task_group_task=task_group_task,
      title=task_group_task.title,
      description=description,
      start_date=start_date,
      end_date=end_date,
      access_control_list=access_control_list,
      status=models.CycleTaskGroupObjectTask.ASSIGNED,
      modified_by=current_user,
      task_type=task_group_task.task_type,
      response_options=task_group_task.response_options,
  )
  return cycle_task_group_object_task


def create_old_style_cycle(cycle, task_group, cycle_task_group, current_user):
  """ This function preserves the old style of creating cycles, so each object
  gets its own task assigned to it.
  """
  related_objs = [
      obj for obj in task_group.related_objects()
      if not isinstance(obj, (all_models.TaskGroupTask, all_models.Workflow))
  ]
  if len(related_objs) == 0:
    for task_group_task in task_group.task_group_tasks:
      _create_cycle_task(
          task_group_task, cycle, cycle_task_group, current_user
      )

  for obj in related_objs:
    for task_group_task in task_group.task_group_tasks:
      cycle_task_group_object_task = _create_cycle_task(
          task_group_task, cycle, cycle_task_group, current_user
      )
      Relationship(source=cycle_task_group_object_task, destination=obj)


def build_cycle(workflow, cycle=None, current_user=None):
  """Build a cycle with it's child objects"""
  build_failed = False

  if not workflow.tasks:
    logger.error("Starting a cycle has failed on Workflow with "
                 "slug == '%s' and id == '%s', due to empty setup",
                 workflow.slug, workflow.id)
    build_failed = True

  # Use Admin role when this is called via the cron job.
  if not current_user:
    admins = workflow.get_persons_for_rolename("Admin")
    if admins:
      current_user = admins[0]
    else:
      logger.error("Cannot start cycle on Workflow with slug == '%s' and "
                   "id == '%s', cause it doesn't have Admins",
                   workflow.slug, workflow.id)
      build_failed = True

  if build_failed:
    pusher.update_or_create_notifications(workflow, date.today(),
                                          "cycle_start_failed")
    return

  # Determine the relevant Workflow
  cycle = cycle or models.Cycle()

  # Populate the top-level Cycle object
  cycle.workflow = workflow
  cycle.is_current = True
  cycle.context = workflow.context
  cycle.title = workflow.title
  cycle.description = workflow.description
  cycle.is_verification_needed = workflow.is_verification_needed
  cycle.status = models.Cycle.ASSIGNED

  # Populate CycleTaskGroups based on Workflow's TaskGroups
  for task_group in workflow.task_groups:
    cycle_task_group = models.CycleTaskGroup(
        context=cycle.context,
        cycle=cycle,
        task_group=task_group,
        title=task_group.title,
        description=task_group.description,
        end_date=cycle.end_date,
        modified_by=current_user,
        contact=task_group.contact,
        status=models.CycleTaskGroup.ASSIGNED,
    )

    # preserve the old cycle creation for old workflows, so each object
    # gets its own cycle task
    if workflow.is_old_workflow:
      create_old_style_cycle(cycle, task_group, cycle_task_group, current_user)
    else:
      for task_group_task in task_group.task_group_tasks:
        cycle_task_group_object_task = _create_cycle_task(
            task_group_task, cycle, cycle_task_group, current_user)
        related_objs = [obj for obj in task_group.related_objects()
                        if not isinstance(obj, (
                            all_models.TaskGroupTask, all_models.Workflow
                        ))]
        for obj in related_objs:
          Relationship(source=cycle_task_group_object_task,
                       destination=obj)

  update_cycle_dates(cycle)
  workflow.repeat_multiplier += 1
  workflow.next_cycle_start_date = workflow.calc_next_adjusted_date(
      workflow.min_task_start_date)
  return cycle


# 'Finished' and 'Verified' states are determined via these links
_cycle_task_children_attr = {
    models.CycleTaskGroup: ['cycle_task_group_tasks'],
    models.Cycle: ['cycle_task_groups']
}


def update_cycle_task_child_state(obj):
  """Update child attributes state of cycle task

  Args:
    obj: Cycle task instance
  """
  status_order = (None, 'Assigned', obj.IN_PROGRESS,
                  'Declined', 'Finished', 'Verified')
  status = obj.status
  children_attrs = _cycle_task_children_attr.get(type(obj), [])
  for children_attr in children_attrs:
    if children_attr:
      children = getattr(obj, children_attr, None)
      for child in children:
        if status == 'Declined' or \
           status_order.index(status) > status_order.index(child.status):
          if is_allowed_update(child.__class__.__name__,
                               child.id, child.context.id):
            old_status = child.status
            child.status = status
            Signals.status_change.send(
                child.__class__,
                objs=[
                    Signals.StatusChangeSignalObjectContext(
                        instance=child,
                        new_status=child.status,
                        old_status=old_status,
                    )
                ]
            )
          update_cycle_task_child_state(child)


def _update_parent_status(parent, child_statuses):
  """Util function, update status of sent parent, if it's allowed.

  New status based on sent object status and sent child_statuses"""
  old_status = parent.status
  if isinstance(parent, models.CycleTaskGroup):
    tasks = parent.cycle_task_group_tasks
  elif isinstance(parent, models.Cycle):
    tasks = parent.cycle_task_group_object_tasks
  else:
    logger.warning("Invalid parent object '%s'.", parent.__class__.__name__)
    return
  # Deprecated status is not counted
  child_statuses.discard("Deprecated")
  if not child_statuses:
    new_status = "Deprecated"
  elif len(child_statuses) == 1:
    new_status = child_statuses.pop()
    if (new_status == "Declined" or
            new_status == "Assigned" and
            any(t.status != "Assigned" for t in tasks)):
      new_status = parent.IN_PROGRESS
  elif {parent.IN_PROGRESS, "Declined", "Assigned"} & child_statuses:
    new_status = parent.IN_PROGRESS
  else:
    new_status = "Finished"
  if old_status != new_status:
    parent.status = new_status


def update_cycle_task_tree(objs):
  """Update cycle task group status for sent cycle task"""
  if not objs:
    return
  groups_dict = {i.cycle_task_group_id: i.cycle_task_group for i in objs}
  group_task_dict = collections.defaultdict(set)
  # load all tasks that are in the same groups there are tasks that be updated
  task_ids = [t.id for t in db.session.deleted
              if isinstance(t, models.CycleTaskGroupObjectTask)]
  for task in itertools.chain(db.session.dirty, db.session.new):
    if not isinstance(task, models.CycleTaskGroupObjectTask):
      continue
    group_task_dict[task.cycle_task_group].add(task)
    if task.id:
      task_ids.append(task.id)
  query = models.CycleTaskGroupObjectTask.query.filter(
      models.CycleTaskGroupObjectTask.cycle_task_group_id.in_(groups_dict)
  ).options(
      orm.undefer_group("CycleTaskGroupObjectTask_complete")
  )
  if task_ids:
    query = query.filter(models.CycleTaskGroupObjectTask.id.notin_(task_ids))
  tasks = query.distinct().with_for_update().all()
  for task in tasks:
    group_task_dict[groups_dict[task.cycle_task_group_id]].add(task)
  updated_groups = []
  for group in groups_dict.itervalues():
    old_state = [group.status, group.start_date, group.end_date,
                 group.next_due_date]
    _update_parent_status(group, {t.status for t in group_task_dict[group]})
    group.start_date, group.end_date = _get_date_range(group_task_dict[group])
    group.next_due_date = _get_min_end_date(group_task_dict[group])
    if old_state != [group.status, group.start_date, group.end_date,
                     group.next_due_date]:
      # if status updated then add it in list. require to update cycle state
      updated_groups.append(group)
  if updated_groups:
    update_cycle_task_group_parent_state(updated_groups)


def update_cycle_task_group_parent_state(objs):
  """Update cycle status for sent cycle task group"""
  if not objs:
    return
  cycles_dict = {}
  cycle_groups_dict = collections.defaultdict(set)
  group_ids = []
  for obj in objs:
    cycle_groups_dict[obj.cycle].add(obj)
    group_ids.append(obj.id)
    cycles_dict[obj.cycle.id] = obj.cycle
  # collect all groups that are in same cycles that group from sent list
  groups = models.CycleTaskGroup.query.filter(
      models.CycleTaskGroup.cycle_id.in_([c.id for c in cycle_groups_dict]),
  ).options(
      orm.undefer_group("CycleTaskGroup_complete")
  ).distinct().with_for_update().all()
  for group in groups:
    cycle_groups_dict[cycles_dict[group.cycle_id]].add(group)

  updated_cycles = []
  for cycle in cycles_dict.itervalues():
    old_status = cycle.status
    _update_parent_status(cycle, {g.status for g in cycle_groups_dict[cycle]})
    cycle.start_date, cycle.end_date = _get_date_range(
        cycle_groups_dict[cycle])
    cycle.next_due_date = _get_min_next_due_date(cycle_groups_dict[cycle])
    if old_status != cycle.status:
      updated_cycles.append(Signals.StatusChangeSignalObjectContext(
          instance=cycle, old_status=old_status, new_status=cycle.status))
  if updated_cycles:
    Signals.status_change.send(models.Cycle, objs=updated_cycles)


def start_end_date_validator(tgt):
  if tgt.start_date > tgt.end_date:
    raise ValueError('End date can not be behind Start date')

  if max(tgt.start_date.isoweekday(),
         tgt.end_date.isoweekday()) > all_models.Workflow.WORK_WEEK_LEN:
    workflow = tgt.task_group.workflow
    if workflow.unit == workflow.DAY_UNIT:
      raise ValueError("Daily tasks cannot be started or stopped on weekend")


def calculate_new_next_cycle_start_date(workflow):
  if not workflow.unit or not workflow.repeat_every:
    return
  if workflow.status != workflow.ACTIVE:
    return
  today = date.today()
  min_task_start_date = workflow.min_task_start_date
  workflow.repeat_multiplier = 0
  workflow.next_cycle_start_date = min_task_start_date
  if min_task_start_date is None:
    return
  while not workflow.next_cycle_start_date > today:
    workflow.repeat_multiplier += 1
    workflow.next_cycle_start_date = workflow.calc_next_adjusted_date(
        min_task_start_date)


@signals.Restful.model_put.connect_via(models.TaskGroupTask)
@signals.Restful.model_posted.connect_via(models.TaskGroupTask)
def handle_task_group_task_put_post(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  start_end_date_validator(obj)

  # If relative days were change we must update workflow next cycle start date
  if inspect(obj).attrs.start_date.history.has_changes():
    calculate_new_next_cycle_start_date(obj.task_group.workflow)


@signals.Restful.model_deleted.connect_via(models.TaskGroupTask)
def handle_task_group_task_delete(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  task_group = obj.task_group
  task_group.task_group_tasks = [t for t in task_group.task_group_tasks
                                 if t.id != obj.id]
  calculate_new_next_cycle_start_date(task_group.workflow)


@signals.Restful.model_posted.connect_via(models.TaskGroup)
def handle_task_group_post(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument

  # NOTE. To clone task group the following operations are performed:
  # 1) create new object, call json_create(), where attributes will be set
  #    with value validation
  # 2) This function is called which overrides some attributes,
  #    attribute validator for these attributes are called
  # So, validation for those attrs are called twice!
  # One corner case of this behavior is validation of field "title".
  # title cannot be None, and because title validation is performed before
  # this function, API request MUST contain non-empty title in dict,
  # however the value will be overridden and re-validated in this function!

  if src.get('clone'):
    source_task_group_id = src.get('clone')
    source_task_group = models.TaskGroup.query.filter_by(
        id=source_task_group_id
    ).first()
    source_task_group.copy(
        obj,
        clone_people=src.get('clone_people', False),
        clone_tasks=src.get('clone_tasks', False),
        clone_objects=src.get('clone_objects', False)
    )

    copied_task_groups = models.TaskGroup.query.filter_by(
        workflow_id=source_task_group.workflow_id,
        parent_id=source_task_group.id).values('title')
    used_titles = [t.title for t in copied_task_groups]
    obj.title = get_copy_title(source_task_group.title, used_titles)

  obj.ensure_assignee_is_workflow_member()
  calculate_new_next_cycle_start_date(obj.workflow)


@signals.Restful.model_deleted.connect_via(models.TaskGroup)
def handle_task_group_delete(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  workflow = obj.workflow
  workflow.task_groups = [t for t in obj.workflow.task_groups
                          if t.id != obj.id]
  calculate_new_next_cycle_start_date(workflow)


@signals.Restful.model_put.connect_via(models.TaskGroup)
def handle_task_group_put(sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  if inspect(obj).attrs.contact.history.has_changes():
    obj.ensure_assignee_is_workflow_member()
  calculate_new_next_cycle_start_date(obj.workflow)


@signals.Restful.model_put.connect_via(models.CycleTaskGroupObjectTask)
def handle_cycle_task_group_object_task_put(
        sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  if inspect(obj).attrs.status.history.has_changes():
    # TODO: check why update_cycle_object_parent_state destroys object history
    # when accepting the only task in a cycle. The listener below is a
    # workaround because of that.
    Signals.status_change.send(
        obj.__class__,
        objs=[
            Signals.StatusChangeSignalObjectContext(
                instance=obj,
                new_status=obj.status,
                old_status=inspect(obj).attrs.status.history.deleted[0],
            )
        ]
    )


@signals.Restful.model_posted.connect_via(
    models.CycleTaskGroupObjectTask)
@signals.Restful.model_put.connect_via(
    models.CycleTaskGroupObjectTask)
@signals.Restful.model_deleted.connect_via(
    models.CycleTaskGroupObjectTask)
# noqa pylint: disable=unused-argument
def handle_cycle_object_status(
        sender, obj=None, src=None, service=None, event=None,
        initial_state=None):
  """Calculate status of cycle and cycle task group"""
  with benchmark("calculate status of Cycle and CycleTaskGroup"):
    update_cycle_task_tree([obj])
    # db.session.commit()


@signals.Restful.model_put.connect_via(models.CycleTaskGroup)
def handle_cycle_task_group_put(
        sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  if inspect(obj).attrs.status.history.has_changes():
    update_cycle_task_child_state(obj)


def update_workflow_state(workflow):
  if workflow.status == workflow.DRAFT:
    return False
  if any(c.is_current for c in workflow.cycles):
    workflow.status = workflow.ACTIVE
  else:
    workflow.status = workflow.INACTIVE


@signals.Restful.model_put.connect_via(models.Cycle)
def handle_cycle_put(
        sender, obj=None, src=None, service=None):  # noqa pylint: disable=unused-argument
  if inspect(obj).attrs.is_current.history.has_changes():
    update_workflow_state(obj.workflow)

# Check if workflow should be Inactive after recurrence change


def _validate_put_workflow_fields(workflow):
  """Validates Workflow's fields update.

    Args:
        workflow: Workflow class instance.
    Raises:
        ValueError: An error occurred in case of failed validation.
    """
  if (inspect(workflow).attrs.unit.history.has_changes() or
          inspect(workflow).attrs.repeat_every.history.has_changes()):
    raise ValueError("'unit', 'repeat_every' fields are unchangeable")
  if (inspect(workflow).attrs.recurrences.history.has_changes() and
          workflow.recurrences and workflow.unit is None and
          workflow.repeat_every is None):
    raise ValueError("OneTime workflow cannot be recurrent")


# noqa pylint: disable=unused-argument  # noqa pylint: disable=unused-argument
@signals.Restful.model_put.connect_via(models.Workflow)
def handle_workflow_put(sender, obj=None, src=None, service=None):
  _validate_put_workflow_fields(obj)
  if (inspect(obj).attrs.recurrences.history.has_changes() and
          not obj.recurrences):
    update_workflow_state(obj)
    return
  if not inspect(obj).attrs.status.history.has_changes():
    return
  new = inspect(obj).attrs.status.history.added[0]
  old = inspect(obj).attrs.status.history.deleted[-1]
  # first activate wf
  if (old, new) == (obj.DRAFT, obj.ACTIVE):
    # allow only if it has at least one task_group with task configured
    if not obj.can_start_cycle:
      raise ValueError("Workflow with misconfigured "
                       "Task Groups can not be activated.")
    build_cycles(obj)


# noqa pylint: disable=unused-argument
@Signals.status_change.connect_via(models.Cycle)
def handle_cycle_status_change(sender, objs=None):
  """
  Cycle will be current if his new status is not `Deprecated`, `Finished`
  or `Verified`

  We assume that status `Finished` or `Verified` of the cycle make him `done`
  but `Deprecated` just change cycle status

  Args:
    sender: Cycle class instance
    objs: signal object as well as new and old statuses
  """

  objs = objs or []
  workflow_ids = set([])
  for obj in objs:
    if obj.old_status == obj.new_status:
      continue

    if obj.instance.is_done or obj.instance.status == obj.instance.DEPRECATED:
      obj.instance.is_current = False
    else:
      obj.instance.is_current = True

    if obj.instance.workflow.id not in workflow_ids:
      update_workflow_state(obj.instance.workflow)
    workflow_ids.add(obj.instance.workflow.id)


# noqa pylint: disable=unused-argument
@Signals.status_change.connect_via(models.CycleTaskGroupObjectTask)
def handle_cycle_task_status_change(sender, objs=None):
  with benchmark("handle CycleTask status change"):
    objs = objs or []
    for obj in objs:
      if obj.old_status == obj.new_status:
        continue
      if obj.new_status == obj.instance.VERIFIED:
        obj.instance.verified_date = datetime.utcnow().date()
        if obj.instance.finished_date is None:
          obj.instance.finished_date = obj.instance.verified_date
      elif obj.new_status == obj.instance.FINISHED:
        obj.instance.finished_date = (obj.instance.finished_date or
                                      datetime.utcnow().date())
        obj.instance.verified_date = None
      else:
        obj.instance.finished_date = None
        obj.instance.verified_date = None


def _validate_post_workflow_fields(workflow):
  """Validates Workflow's 'repeat_every' and 'unit' fields dependency.

  Validates that Workflow's 'repeat_every' and 'unit' fields can have NULL
  only simultaneously.

  Args:
      workflow: Workflow class instance.
  Raises:
      ValueError: An error occurred in case of failed dependency validation.
  """
  if ((workflow.repeat_every is None and workflow.unit is not None) or
          (workflow.repeat_every is not None and workflow.unit is None)):
    raise ValueError("Workflow 'repeat_every' and 'unit' fields "
                     "can be NULL only simultaneously")


# noqa pylint: disable=unused-argument
@signals.Restful.model_posted.connect_via(models.Workflow)
def handle_workflow_post(sender, obj=None, src=None, service=None):
  _validate_post_workflow_fields(obj)

  source_workflow = None

  if src.get('clone'):
    source_workflow_id = src.get('clone')
    source_workflow = models.Workflow.query.filter_by(
        id=source_workflow_id
    ).first()
    source_workflow.copy(obj, clone_people=src.get('clone_people', False))

    copied_workflows = models.Workflow.query.filter_by(
        parent_id=source_workflow.id).values('title')
    used_titles = [w.title for w in copied_workflows]
    obj.title = get_copy_title(source_workflow.title, used_titles)

  # get the personal context for this logged in user
  user = get_current_user(use_external_user=False)
  personal_context = user.get_or_create_object_context(context=1)
  workflow_context = obj.get_or_create_object_context(personal_context)
  obj.context = workflow_context

  if src.get('clone'):
    source_workflow.copy_task_groups(
        obj,
        clone_people=src.get('clone_people', False),
        clone_tasks=src.get('clone_tasks', False),
        clone_objects=src.get('clone_objects', False)
    )


def init_extra_views(app):
  from . import views
  views.init_extra_views(app)


def start_recurring_cycles():
  """Start recurring cycles by cron job."""
  with benchmark("contributed cron job start_recurring_cycles"):
    today = date.today()
    workflows = models.Workflow.query.filter(
        models.Workflow.next_cycle_start_date <= today,
        models.Workflow.recurrences == True  # noqa
    )
    event = None
    for workflow in workflows:
      # Follow same steps as in model_posted.connect_via(models.Cycle)
      while workflow.next_cycle_start_date <= date.today():
        cycle = build_cycle(workflow)
        if not cycle:
          break
        db.session.add(cycle)
        notification.handle_cycle_created(cycle, False)
        notification.handle_workflow_modify(None, workflow)
      # db.session.commit was moved into cycle intentionally.
      # 'Cycles' for each 'Workflow' should be committed separately
      # to free memory on each iteration. Single commit exeeded
      # maximum memory limit on AppEngine instance.
      event = log_event(db.session, event=event)
      db.session.commit()


class WorkflowRoleContributions(RoleContributions):
  contributions = {
      'ProgramCreator': {
          'read': ['Workflow'],
          'create': ['Workflow'],
      },
      'Creator': {
          'create': ['Workflow', 'CycleTaskGroupObjectTask']
      },
      'Editor': {
          'read': ['Workflow', 'CycleTaskGroupObjectTask'],
          'create': ['Workflow', 'CycleTaskGroupObjectTask'],
          'update': ['CycleTaskGroupObjectTask'],
          'edit': ['CycleTaskGroupObjectTask'],
      },
      'Reader': {
          'read': ['Workflow', 'CycleTaskGroupObjectTask'],
          'create': ['Workflow', 'CycleTaskGroupObjectTask'],
      },
      'ProgramEditor': {
          'read': ['Workflow'],
          'create': ['Workflow'],
      },
      'ProgramOwner': {
          'read': ['Workflow'],
          'create': ['Workflow'],
      },
  }


ROLE_CONTRIBUTIONS = WorkflowRoleContributions()

contributed_notifications = notification.contributed_notifications
contributed_importables = IMPORTABLE
contributed_exportables = EXPORTABLE
contributed_get_ids_related_to = relationship_helper.get_ids_related_to
NIGHTLY_CRON_JOBS = [start_recurring_cycles]
NOTIFICATION_LISTENERS = [notification.register_listeners]


_inject_workflow_mixins()
