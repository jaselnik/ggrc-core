# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module containing Cycle tasks.
"""

from logging import getLogger
from sqlalchemy import orm
import sqlalchemy as sa
from sqlalchemy.ext import hybrid
from sqlalchemy.ext.declarative import declared_attr
from werkzeug.exceptions import BadRequest

from ggrc import builder
from ggrc import db
from ggrc import login
from ggrc.access_control import roleable
from ggrc.fulltext import attributes as ft_attributes
from ggrc.fulltext import mixin as ft_mixin
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models import types
from ggrc.models.mixins import base
from ggrc.models.mixins import with_last_comment

from ggrc_workflows.models.cycle import Cycle
from ggrc_workflows.models.workflow import Workflow
from ggrc_workflows.models.cycle_task_group import CycleTaskGroup
from ggrc_workflows.models import mixins as wf_mixins


LOGGER = getLogger(__name__)


class CycleTaskGroupObjectTask(roleable.Roleable,
                               with_last_comment.WithLastComment,
                               wf_mixins.CycleTaskStatusValidatedMixin,
                               wf_mixins.WorkflowCommentable,
                               mixins.WithLastDeprecatedDate,
                               mixins.Timeboxed,
                               relationship.Relatable,
                               mixins.Notifiable,
                               mixins.Described,
                               mixins.Titled,
                               mixins.Slugged,
                               mixins.Base,
                               base.ContextRBAC,
                               ft_mixin.Indexed,
                               db.Model):
  """Cycle task model
  """
  __tablename__ = 'cycle_task_group_object_tasks'

  readable_name_alias = 'cycle task'

  _title_uniqueness = False

  IMPORTABLE_FIELDS = (
      'slug', 'title', 'description',
      'start_date', 'end_date', 'comments', 'status',
      '__acl__:Task Assignees', '__acl__:Task Secondary Assignees',
  )

  @classmethod
  def generate_slug_prefix(cls):
    return "CYCLETASK"

  # Note: this statuses are used in utils/query_helpers to filter out the tasks
  # that should be visible on My Tasks pages.

  PROPERTY_TEMPLATE = u"task {}"

  _fulltext_attrs = [
      ft_attributes.DateFullTextAttr("end_date", 'end_date',),
      ft_attributes.FullTextAttr("group title",
                                 'cycle_task_group',
                                 ['title'],
                                 False),
      ft_attributes.FullTextAttr("object_approval",
                                 'object_approval',
                                 with_template=False),
      ft_attributes.FullTextAttr("cycle title", 'cycle', ['title'], False),
      ft_attributes.FullTextAttr("group assignee",
                                 lambda x: x.cycle_task_group.contact,
                                 ['email', 'name'],
                                 False),
      ft_attributes.FullTextAttr("cycle assignee",
                                 lambda x: x.cycle.contact,
                                 ['email', 'name'],
                                 False),
      ft_attributes.DateFullTextAttr(
          "group due date",
          lambda x: x.cycle_task_group.next_due_date,
          with_template=False),
      ft_attributes.DateFullTextAttr("cycle due date",
                                     lambda x: x.cycle.next_due_date,
                                     with_template=False),
      ft_attributes.BooleanFullTextAttr("needs verification",
                                        "is_verification_needed",
                                        with_template=False,
                                        true_value="Yes", false_value="No"),
      "folder",
  ]

  # The app should not pass to the json representation of
  # relationships to the internal models
  IGNORED_RELATED_TYPES = ["CalendarEvent"]

  _custom_publish = {
      "related_sources": lambda obj: [
          rel.log_json() for rel in obj.related_sources
          if rel.source_type not in obj.IGNORED_RELATED_TYPES
      ],
      "related_destinations": lambda obj: [
          rel.log_json() for rel in obj.related_destinations
          if rel.destination_type not in obj.IGNORED_RELATED_TYPES
      ]
  }

  cycle_id = db.Column(
      db.Integer,
      db.ForeignKey('cycles.id', ondelete="CASCADE"),
      nullable=False,
  )
  cycle_task_group_id = db.Column(
      db.Integer,
      db.ForeignKey('cycle_task_groups.id', ondelete="CASCADE"),
      nullable=False,
  )
  task_group_task_id = db.Column(
      db.Integer, db.ForeignKey('task_group_tasks.id'), nullable=True)
  task_group_task = db.relationship(
      "TaskGroupTask",
      foreign_keys="CycleTaskGroupObjectTask.task_group_task_id"
  )
  task_type = db.Column(db.String(length=250), nullable=False)
  response_options = db.Column(types.JsonType(), nullable=False, default=[])
  selected_response_options = db.Column(types.JsonType(),
                                        nullable=False,
                                        default=[])

  finished_date = db.Column(db.Date)
  verified_date = db.Column(db.Date)

  # This parameter is overridden by cycle task group backref, but is here to
  # ensure pylint does not complain
  _cycle_task_group = None

  @hybrid.hybrid_property
  def cycle_task_group(self):
    """Getter for cycle task group foreign key."""
    return self._cycle_task_group

  @cycle_task_group.setter
  def cycle_task_group(self, cycle_task_group):
    """Setter for cycle task group foreign key."""
    if not self._cycle_task_group and cycle_task_group:
      relationship.Relationship(source=cycle_task_group, destination=self)
    self._cycle_task_group = cycle_task_group

  @hybrid.hybrid_property
  def object_approval(self):
    return self.cycle.workflow.object_approval

  @object_approval.expression
  def object_approval(cls):  # pylint: disable=no-self-argument
    return sa.select([
        Workflow.object_approval,
    ]).where(
        sa.and_((Cycle.id == cls.cycle_id), (Cycle.workflow_id == Workflow.id))
    ).label(
        'object_approval'
    )

  @builder.simple_property
  def folder(self):
    """Simple property for cycle folder."""
    if self.cycle:
      return self.cycle.folder
    return ""

  @builder.simple_property
  def is_in_history(self):
    """Used on UI to disable editing finished CycleTask which is in history"""
    return not self.cycle.is_current

  @property
  def cycle_task_objects_for_cache(self):
    """Get all related objects for this CycleTaskGroupObjectTask

    Returns:
      List of tuples with (related_object_type, related_object_id)
    """
    return [(object_.__class__.__name__, object_.id) for object_ in
            self.related_objects()]

  _api_attrs = reflection.ApiAttributes(
      'cycle',
      'cycle_task_group',
      'task_group_task',
      'task_type',
      'response_options',
      'selected_response_options',
      reflection.Attribute('related_sources', create=False, update=False),
      reflection.Attribute('related_destinations', create=False, update=False),
      reflection.Attribute('object_approval', create=False, update=False),
      reflection.Attribute('finished_date', create=False, update=False),
      reflection.Attribute('verified_date', create=False, update=False),
      reflection.Attribute('allow_change_state', create=False, update=False),
      reflection.Attribute('folder', create=False, update=False),
      reflection.Attribute('workflow', create=False, update=False),
      reflection.Attribute('workflow_title', create=False, update=False),
      reflection.Attribute('cycle_task_group_title', create=False,
                           update=False),
      reflection.Attribute('is_in_history', create=False, update=False),

  )

  default_description = "<ol>"\
                        + "<li>Expand the object review task.</li>"\
                        + "<li>Click on the Object to be reviewed.</li>"\
                        + "<li>Review the object in the Info tab.</li>"\
                        + "<li>Click \"Approve\" to approve the object.</li>"\
                        + "<li>Click \"Decline\" to decline the object.</li>"\
                        + "</ol>"

  _aliases = {
      "title": "Summary",
      "description": "Task Description",
      "finished_date": {
          "display_name": "Actual Finish Date",
      },
      "verified_date": {
          "display_name": "Actual Verified Date",
      },
      "cycle": {
          "display_name": "Cycle",
          "filter_by": "_filter_by_cycle",
      },
      "cycle_task_group": {
          "display_name": "Task Group",
          "mandatory": True,
          "filter_by": "_filter_by_cycle_task_group",
      },
      "task_type": {
          "display_name": "Task Type",
          "mandatory": True,
      },
      "end_date": "Due Date",
      "start_date": "Start Date",
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for CycleTaskGroupObjectTask obj"""
    from ggrc_workflows.converters import handlers
    return {
        "cycle": handlers.CycleColumnHandler,
        "cycle_task_group": handlers.CycleTaskGroupColumnHandler,
        "task_type": handlers.TaskTypeColumnHandler,
    }

  @builder.simple_property
  def cycle_task_group_title(self):
    """Property. Returns parent CycleTaskGroup title."""
    return self.cycle_task_group.title

  @builder.simple_property
  def workflow_title(self):
    """Property. Returns parent Workflow's title."""
    return self.workflow.title

  @builder.simple_property
  def workflow(self):
    """Property which returns parent workflow object."""
    return self.cycle.workflow

  @builder.simple_property
  def allow_change_state(self):
    return self.cycle.is_current and self.current_user_wfa_or_assignee()

  def current_user_wfa_or_assignee(self):
    """Current user is WF Admin, Assignee or Secondary Assignee for self."""
    wfa_ids = self.workflow.get_person_ids_for_rolename("Admin")
    ta_ids = self.get_person_ids_for_rolename("Task Assignees")
    tsa_ids = self.get_person_ids_for_rolename("Task Secondary Assignees")
    return login.get_current_user_id() in set().union(wfa_ids, ta_ids, tsa_ids)

  @classmethod
  def _filter_by_cycle(cls, predicate):
    """Get query that filters cycle tasks by related cycles.

    Args:
      predicate: lambda function that excepts a single parameter and returns
      true of false.

    Returns:
      An sqlalchemy query that evaluates to true or false and can be used in
      filtering cycle tasks by related cycles.
    """
    return Cycle.query.filter(
        (Cycle.id == cls.cycle_id) &
        (predicate(Cycle.slug) | predicate(Cycle.title))
    ).exists()

  @classmethod
  def _filter_by_cycle_task_group(cls, predicate):
    """Get query that filters cycle tasks by related cycle task groups.

    Args:
      predicate: lambda function that excepts a single parameter and returns
      true of false.

    Returns:
      An sqlalchemy query that evaluates to true or false and can be used in
      filtering cycle tasks by related cycle task groups.
    """
    return CycleTaskGroup.query.filter(
        (CycleTaskGroup.id == cls.cycle_id) &
        (predicate(CycleTaskGroup.slug) | predicate(CycleTaskGroup.title))
    ).exists()

  @classmethod
  def eager_query(cls, **kwargs):
    """
    Add related objects to eager query.

    This function makes sure that with one query we fetch all cycle task
    related data needed for generating cycle task json for a response.
    """

    # Ensure that related_destinations and related_sources will be loaded
    # in subquery. It allows reduce a number of requests to DB when these attrs
    # are used
    LOGGER.debug("%s.eager_query(): setting flag to load related_sources "
                 " and related_destinations", cls.__name__)
    kwargs['load_related'] = True

    query = super(CycleTaskGroupObjectTask, cls).eager_query(**kwargs)
    return query.options(
        orm.joinedload('cycle')
           .undefer_group('Cycle_complete'),
        orm.joinedload('cycle')
           .joinedload('workflow')
           .undefer_group('Workflow_complete'),
        orm.joinedload('cycle')
           .joinedload('workflow')
           .joinedload('_access_control_list'),
        orm.joinedload('cycle_task_group')
           .undefer_group('CycleTaskGroup_complete'),
    )

  @classmethod
  def indexed_query(cls):
    return super(CycleTaskGroupObjectTask, cls).indexed_query().options(
        orm.Load(cls).load_only(
            "end_date",
            "start_date",
            "created_at",
            "updated_at"
        ),
        orm.Load(cls).joinedload("cycle_task_group").load_only(
            "id",
            "title",
            "end_date",
            "next_due_date",
        ),
        orm.Load(cls).joinedload("cycle").load_only(
            "id",
            "title",
            "next_due_date",
            "is_verification_needed",
        ),
        orm.Load(cls).joinedload("cycle_task_group").joinedload(
            "contact"
        ).load_only(
            "email",
            "name",
            "id"
        ),
        orm.Load(cls).joinedload("cycle").joinedload(
            "contact"
        ).load_only(
            "email",
            "name",
            "id"
        ),
        orm.Load(cls).joinedload("cycle").joinedload("workflow").undefer_group(
            "Workflow_complete"
        ),
    )

  def log_json(self):
    out_json = super(CycleTaskGroupObjectTask, self).log_json()
    out_json["folder"] = self.folder
    return out_json

  @classmethod
  def bulk_update(cls, src):
    """Update statuses for bunch of tasks in a bulk.

    Args:
        src: input json with next structure:
          [{"status": "Assigned", "id": 1}, {"status": "In Progress", "id": 2}]

    Returns:
        list of updated_instances
    """
    new_prv_state_map = {
        cls.DEPRECATED: (cls.ASSIGNED, cls.IN_PROGRESS, cls.FINISHED,
                         cls.VERIFIED, cls.DECLINED),
        cls.IN_PROGRESS: (cls.ASSIGNED, ),
        cls.FINISHED: (cls.IN_PROGRESS, cls.DECLINED),
        cls.VERIFIED: (cls.FINISHED, ),
        cls.DECLINED: (cls.FINISHED, ),
        cls.ASSIGNED: (),
    }
    uniq_states = set([item['state'] for item in src])
    if len(list(uniq_states)) != 1:
      raise BadRequest("Request's JSON contains multiple statuses for "
                       "CycleTasks")
    new_state = uniq_states.pop()
    LOGGER.info("Do bulk update CycleTasks with '%s' status", new_state)
    if new_state not in cls.VALID_STATES:
      raise BadRequest("Request's JSON contains invalid statuses for "
                       "CycleTasks")
    prv_states = new_prv_state_map[new_state]
    all_ids = {item['id'] for item in src}
    # Eagerly loading is needed to get user permissions for CycleTask faster
    updatable_objects = cls.eager_query().filter(
        cls.id.in_(list(all_ids)),
        cls.status.in_(prv_states))
    if new_state in (cls.VERIFIED, cls.DECLINED):
      updatable_objects = [obj for obj in updatable_objects
                           if obj.cycle.is_verification_needed]
    # Bulk update works only on MyTasks page. Don't need to check for
    # WorkflowMembers' permissions here. User should update only his own tasks.
    updatable_objects = [obj for obj in updatable_objects
                         if obj.current_user_wfa_or_assignee()]
    # Queries count is constant because we are using eager query for objects.
    for obj in updatable_objects:
      obj.status = new_state
      obj.modified_by_id = login.get_current_user_id()
    return updatable_objects


class CycleTaskable(object):
  """CycleTaskable mixin"""

  # The following attribute will be used to add sqlalchemy properties
  # to mapper after Mixin is injected to existing Model class.
  # Do not forget add new sqlalchemy attrs to the list. These aatrs will be
  # added to mapper after mixin injection
  _mapper_inject_properties = [
      'cycle_task_group_object_tasks',
  ]

  @declared_attr
  def cycle_task_group_object_tasks(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        CycleTaskGroupObjectTask,
        primaryjoin=lambda: sa.or_(
            sa.and_(
                cls.id == relationship.Relationship.source_id,
                relationship.Relationship.source_type == cls.__name__,
                relationship.Relationship.destination_type ==
                "CycleTaskGroupObjectTask",
            ),
            sa.and_(
                cls.id == relationship.Relationship.destination_id,
                relationship.Relationship.destination_type == cls.__name__,
                relationship.Relationship.source_type ==
                "CycleTaskGroupObjectTask",
            )
        ),
        secondary=relationship.Relationship.__table__,
        secondaryjoin=lambda: CycleTaskGroupObjectTask.id == sa.case(
            [(relationship.Relationship.source_type == cls.__name__,
              relationship.Relationship.destination_id)],
            else_=relationship.Relationship.source_id
        ),
        viewonly=True
    )

  @classmethod
  def eager_query(cls, **kwargs):
    """Eager query for objects with cycle tasks."""
    query = super(CycleTaskable, cls).eager_query(**kwargs)
    return query.options(orm.subqueryload('cycle_task_group_object_tasks'))
