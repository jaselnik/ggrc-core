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
from ggrc.models.hooks import common
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

  parent_id = db.Column(
      db.Integer,
      db.ForeignKey('task_groups.id', ondelete="SET NULL"),
      nullable=True,
  )
  workflow_id = db.Column(
      db.Integer,
      db.ForeignKey('workflows.id', ondelete="CASCADE"),
      nullable=False,
  )

  task_group_tasks = db.relationship(
      'TaskGroupTask', backref='_task_group', cascade='all, delete-orphan')

  cycle_task_groups = db.relationship(
      'CycleTaskGroup', backref='task_group')

  _api_attrs = reflection.ApiAttributes(
      'workflow',
      'task_group_tasks',
      # Intentionally do not include `cycle_task_groups`
      # 'cycle_task_groups',
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

  @staticmethod
  def specific_column_handlers():
    """Column handlers for task group obj"""
    from ggrc_workflows.converters import handlers
    return {
        "workflow": handlers.WorkflowColumnHandler,
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
        'title', 'description', 'parent_id', 'workflow', 'modified_by',
        'context'
    ]
    kwargs['parent_id'] = self.id

    if kwargs.get('clone_people', False) and getattr(self, "contact"):
      columns.append("contact")
    else:
      kwargs["contact"] = get_current_user()

    target = self.copy_into(_other, columns, **kwargs)

    target.ensure_assignee_is_workflow_member()

    if kwargs.get('clone_objects', False):
      self.copy_objects(target, **kwargs)

    if kwargs.get('clone_tasks', False):
      self.copy_tasks(target, **kwargs)

    return target

  def copy_objects(self, target, **kwargs):
    # pylint: disable=unused-argument
    for rel in self.related_destinations:
      if rel.destination_type != 'TaskGroupTask':
        common.map_objects(target, {
            "id": rel.destination_id,
            "type": rel.destination_type
        })

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
