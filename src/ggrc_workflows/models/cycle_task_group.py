# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for cycle task group model.
"""
import itertools

from sqlalchemy import orm, inspect
from sqlalchemy.ext import hybrid

from ggrc import db
from ggrc.access_control import roleable
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models.mixins import base
from ggrc.fulltext import mixin as index_mixin
from ggrc.fulltext import attributes

from ggrc_workflows.models.cycle import Cycle
from ggrc_workflows.models import mixins as wf_mixins


def _query_filtered_by_contact(person):
  """Returns cycle task groups required to reindex for sent persons."""
  attrs = inspect(person).attrs
  if any([attrs["email"].history.has_changes(),
          attrs["name"].history.has_changes()]):
    return CycleTaskGroup.query.filter(CycleTaskGroup.contact_id == person.id)
  return []


class CycleTaskGroup(roleable.Roleable,
                     relationship.Relatable,
                     mixins.WithContact,
                     wf_mixins.CycleTaskGroupRelatedStatusValidatedMixin,
                     mixins.Slugged,
                     mixins.Timeboxed,
                     mixins.Described,
                     mixins.Titled,
                     base.ContextRBAC,
                     mixins.Base,
                     index_mixin.Indexed,
                     db.Model):
  """Cycle Task Group model.
  """
  __tablename__ = 'cycle_task_groups'
  _title_uniqueness = False

  @classmethod
  def generate_slug_prefix(cls):  # pylint: disable=unused-argument
    return "CYCLEGROUP"

  cycle_id = db.Column(
      db.Integer,
      db.ForeignKey('cycles.id', ondelete="CASCADE"),
      nullable=False,
  )
  task_group_id = db.Column(
      db.Integer, db.ForeignKey('task_groups.id'), nullable=True)
  cycle_task_group_tasks = db.relationship(
      'CycleTaskGroupObjectTask',
      backref='_cycle_task_group',
      cascade='all, delete-orphan'
  )
  next_due_date = db.Column(db.Date)

  _api_attrs = reflection.ApiAttributes(
      'cycle',
      'task_group',
      'cycle_task_group_tasks',
      'next_due_date'
  )

  _aliases = {
      "cycle": {
          "display_name": "Cycle",
          "filter_by": "_filter_by_cycle",
      },
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for cycle task group obj"""
    from ggrc_workflows.converters import handlers
    return {
        "cycle": handlers.CycleColumnHandler,
    }

  PROPERTY_TEMPLATE = u"group {}"

  _fulltext_attrs = [
      attributes.DateFullTextAttr("due date", 'next_due_date',),
      attributes.FullTextAttr("assignee", "contact", ['email', 'name']),
      attributes.FullTextAttr("cycle title", 'cycle', ['title'], False),
      attributes.FullTextAttr(
          "cycle assignee",
          lambda x: x.cycle.contact,
          ['email', 'name'],
          False),
      attributes.DateFullTextAttr(
          "cycle due date",
          lambda x: x.cycle.next_due_date,
          with_template=False),
      attributes.MultipleSubpropertyFullTextAttr(
          "task title",
          "cycle_task_group_tasks",
          ["title"],
          False),
      attributes.MultipleSubpropertyFullTextAttr(
          "task assignees",
          "_task_assignees",
          ["email", "name"],
          False),
      attributes.MultipleSubpropertyFullTextAttr(
          "task state",
          "cycle_task_group_tasks",
          ["status"],
          False),
      attributes.MultipleSubpropertyFullTextAttr(
          "task secondary assignees",
          "_task_secondary_assignees",
          ["email", "name"],
          False),
      attributes.DateMultipleSubpropertyFullTextAttr(
          "task due date",
          "cycle_task_group_tasks",
          ["end_date"],
          False),
      attributes.MultipleSubpropertyFullTextAttr(
          "task comment",
          lambda instance: itertools.chain(*[
              t.comments for t in instance.cycle_task_group_tasks
          ]),
          ["description"],
          False),
  ]

  # This parameter is overridden by cycle backref, but is here to ensure
  # pylint does not complain
  _cycle = None

  @hybrid.hybrid_property
  def cycle(self):
    """Getter for cycle foreign key."""
    return self._cycle

  @cycle.setter
  def cycle(self, cycle):
    """Set cycle foreign key and relationship."""
    if not self._cycle and cycle:
      relationship.Relationship(source=cycle, destination=self)
    self._cycle = cycle

  @property
  def workflow(self):
    """Property which returns parent workflow object."""
    return self.cycle.workflow

  @property
  def _task_assignees(self):
    """Property. Return the list of persons as assignee of related tasks."""
    people = set()
    for ctask in self.cycle_task_group_tasks:
      people.update(ctask.get_persons_for_rolename("Task Assignees"))
    return list(people)

  @property
  def _task_secondary_assignees(self):
    """Property. Returns people list as Secondary Assignee of related tasks."""
    people = set()
    for ctask in self.cycle_task_group_tasks:
      people.update(ctask.get_persons_for_rolename("Task Secondary Assignees"))
    return list(people)

  AUTO_REINDEX_RULES = [
      index_mixin.ReindexRule(
          "CycleTaskGroupObjectTask",
          lambda x: x.cycle_task_group
      ),
      index_mixin.ReindexRule(
          "Person",
          _query_filtered_by_contact
      ),
      index_mixin.ReindexRule(
          "Person",
          lambda x: [i.cycle for i in _query_filtered_by_contact(x)]
      ),
  ]

  @classmethod
  def _filter_by_cycle(cls, predicate):
    """Get query that filters cycle task groups.

    Args:
      predicate: lambda function that excepts a single parameter and returns
      true of false.

    Returns:
      An sqlalchemy query that evaluates to true or false and can be used in
      filtering cycle task groups by related cycle.
    """
    return Cycle.query.filter(
        (Cycle.id == cls.cycle_id) &
        (predicate(Cycle.slug) | predicate(Cycle.title))
    ).exists()

  @classmethod
  def indexed_query(cls):
    return super(CycleTaskGroup, cls).indexed_query().options(
        orm.Load(cls).load_only(
            "next_due_date",
        ),
        orm.Load(cls).subqueryload("cycle_task_group_tasks").load_only(
            "id",
            "title",
            "end_date",
            "status",
        ),
        orm.Load(cls).subqueryload("cycle_task_group_tasks").subqueryload(
            "_access_control_list",
        ).load_only(
            "ac_role_id",
        ).subqueryload(
            "access_control_people",
        ).load_only(
            "person_id",
        ),
        orm.Load(cls).subqueryload("cycle_task_group_tasks"),
        orm.Load(cls).joinedload("cycle").load_only(
            "id",
            "title",
            "next_due_date",
        ),
        orm.Load(cls).joinedload("cycle").joinedload(
            "contact"
        ).load_only(
            "name",
            "email",
            "id",
        ),
        orm.Load(cls).joinedload("contact").load_only(
            "name",
            "email",
            "id",
        ),
    )

  @classmethod
  def eager_query(cls, **kwargs):
    """Add cycle tasks and objects to cycle task group eager query.

    Make sure we load all cycle task group relevant data in a single query.

    Returns:
      a query object with cycle_task_group_tasks added to joined load options.
    """
    query = super(CycleTaskGroup, cls).eager_query(**kwargs)
    return query.options(
        orm.subqueryload("cycle_task_group_tasks"),
        orm.joinedload("cycle").undefer_group("Cycle_complete"),
        orm.joinedload("cycle").joinedload("contact")
    )
