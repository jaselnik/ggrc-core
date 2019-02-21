# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A module containing the workflow TaskGroup model."""


from sqlalchemy import orm
from sqlalchemy.ext import hybrid

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.login import get_current_user
from ggrc.access_control import roleable
from ggrc.models.mixins import (
    Titled, Slugged, Described, Timeboxed, WithContact
)
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models import all_models
from ggrc.models.mixins import base


class TaskGroup(roleable.Roleable,
                relationship.Relatable,
                WithContact,
                Timeboxed,
                Described,
                Titled,
                base.ContextRBAC,
                Slugged,
                Indexed,
                db.Model):
  """Workflow TaskGroup model."""

  __tablename__ = 'task_groups'
  _title_uniqueness = False

  workflow_id = db.Column(
      db.Integer,
      db.ForeignKey('workflows.id', ondelete="CASCADE"),
      nullable=False,
  )

  task_group_tasks = db.relationship(
      'TaskGroupTask', backref='_task_group', cascade='all, delete-orphan')

  cycle_task_groups = db.relationship(
      'CycleTaskGroup', backref='task_group')

  sort_index = db.Column(
      db.String(length=250), default="", nullable=False)

  _api_attrs = reflection.ApiAttributes(
      'workflow',
      'task_group_tasks',
      'sort_index',
  )

  _aliases = {
      "description": "Details",
      "contact": {
          "display_name": "Assignee",
          "mandatory": True,
          "description": ("One person could be added "
                          "as a Task Group assignee")
      },
      "secondary_contact": None,
      "start_date": None,
      "end_date": None,
      "workflow": {
          "display_name": "Workflow",
          "mandatory": True,
          "filter_by": "_filter_by_workflow",
      },
  }

  # This parameter is overridden by workflow backref, but is here to ensure
  # pylint does not complain
  _workflow = None

  @hybrid.hybrid_property
  def workflow(self):
    """Getter for workflow foreign key."""
    return self._workflow

  @workflow.setter
  def workflow(self, workflow):
    """Setter for workflow foreign key."""
    if not self._workflow and workflow:
      all_models.Relationship(source=workflow, destination=self)
    self._workflow = workflow

  def ensure_assignee_is_workflow_member(self):  # pylint: disable=invalid-name
    """Add Workflow Member role to user without role in scope of Workflow."""
    people_with_role_ids = (
        self.workflow.get_person_ids_for_rolename("Admin") +
        self.workflow.get_person_ids_for_rolename("Workflow Member"))
    if self.contact.id in people_with_role_ids:
      return
    self.workflow.add_person_with_role_name(self.contact, "Workflow Member")

  def copy(self, _other=None, **kwargs):
    columns = [
        'title', 'description', 'workflow', 'sort_index', 'modified_by',
        'context'
    ]

    if kwargs.get('clone_people', False) and getattr(self, "contact"):
      columns.append("contact")
    else:
      kwargs["contact"] = get_current_user()

    target = self.copy_into(_other, columns, **kwargs)

    target.ensure_assignee_is_workflow_member()

    if kwargs.get('clone_tasks', False):
      self.copy_tasks(target, **kwargs)

    return target

  def copy_tasks(self, target, **kwargs):
    for task_group_task in self.task_group_tasks:
      target.task_group_tasks.append(task_group_task.copy(
          None,
          task_group=target,
          context=target.context,
          clone_people=kwargs.get("clone_people", False),
      ))

    return target

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(TaskGroup, cls).eager_query(**kwargs)
    return query.options(
        orm.Load(cls).subqueryload('task_group_tasks')
    )

  @classmethod
  def _filter_by_workflow(cls, predicate):
    from ggrc_workflows.models import Workflow
    return Workflow.query.filter(
        (Workflow.id == cls.workflow_id) &
        (predicate(Workflow.slug) | predicate(Workflow.title))
    ).exists()


class TaskGroupable(object):
  """ Requires the Relatable mixin, otherwise task_groups
  fail to fetch related objects
  """

  @classmethod
  def eager_query(cls):
    """Eager query for objects with task groups."""
    query = super(TaskGroupable, cls).eager_query()
    return query.options(
        orm.subqueryload('related_sources')
           .joinedload('TaskGroup_source'),
        orm.subqueryload('related_destinations')
           .joinedload('TaskGroup_destination')
    )
