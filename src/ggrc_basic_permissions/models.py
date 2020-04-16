# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import json
from logging import getLogger

from sqlalchemy.orm import backref

from ggrc import db
from ggrc.builder import simple_property
from ggrc.models import all_models
from ggrc.models.context import Context
from ggrc.models.person import Person
from ggrc.models.mixins import base
from ggrc.models.mixins import rest_handable
from ggrc.models.mixins import Base, Described
from ggrc.models import reflection
from ggrc import utils

from ggrc_basic_permissions.contributed_roles import (
    DECLARED_ROLE,
    get_declared_role,
)


# pylint: disable=invalid-name
logger = getLogger(__name__)


class Role(base.ContextRBAC, Base, Described, db.Model):
  """A user role. All roles have a unique name. This name could be a simple
  string, an email address, or some other form of string identifier.

  Example:

  ..  code-block:: python

      {
        'create': ['Program', 'Control'],
        'read': ['Program', 'Control'],
        'update': ['Program', 'Control'],
        'delete': ['Program'],
      }

  """
  __tablename__ = 'roles'

  name = db.Column(db.String(128), nullable=False)
  permissions_json = db.Column(db.Text(), nullable=False)
  scope = db.Column(db.String(64), nullable=True)
  role_order = db.Column(db.Integer(), nullable=True)

  @simple_property
  def permissions(self):
    if self.permissions_json == DECLARED_ROLE:
      declared_role = get_declared_role(self.name)
      permissions = declared_role.permissions
    else:
      permissions = json.loads(self.permissions_json) or {}
    # make sure not to omit actions
    for action in ['create', 'read', 'update', 'delete']:
      if action not in permissions:
        permissions[action] = []
    return permissions

  @permissions.setter
  def permissions(self, value):
    self.permissions_json = json.dumps(value)

  _api_attrs = reflection.ApiAttributes(
      'name',
      'permissions',
      'scope',
      'role_order',
  )

  def _display_name(self):
    return self.name


Person._api_attrs.add('user_roles')
# FIXME: Cannot use `include_links`, because Memcache expiry doesn't handle
#   sub-resources correctly
# Person._include_links.extend(['user_roles'])


# Override `Person.eager_query` to ensure `user_roles` is loaded efficiently
_orig_Person_eager_query = Person.eager_query


def _Person_eager_query(cls, **kwargs):
  from sqlalchemy import orm

  return _orig_Person_eager_query(**kwargs).options(
      orm.subqueryload('user_roles'),
      # orm.subqueryload('user_roles').undefer_group('UserRole_complete'),
      # orm.subqueryload('user_roles').joinedload('context'),
      # orm.subqueryload('user_roles').joinedload('role'),
  )


Person.eager_query = classmethod(_Person_eager_query)


Context._api_attrs.add('user_roles')
_orig_Context_eager_query = Context.eager_query


def _Context_eager_query(cls, **kwargs):
  from sqlalchemy import orm

  return _orig_Context_eager_query(**kwargs).options(
      orm.subqueryload('user_roles')
  )


Context.eager_query = classmethod(_Context_eager_query)


class UserRole(rest_handable.WithDeleteHandable,
               rest_handable.WithPostHandable,
               base.ContextRBAC,
               Base,
               db.Model):
  """`UserRole` model represents mapping between `User` and `Role` models."""

  __tablename__ = 'user_roles'

  # Override default from `ContextRBAC` to provide backref
  context = db.relationship('Context', backref='user_roles')

  role_id = db.Column(db.Integer(), db.ForeignKey('roles.id'), nullable=False)
  role = db.relationship(
      'Role', backref=backref('user_roles', cascade='all, delete-orphan'))
  person_id = db.Column(
      db.Integer(), db.ForeignKey('people.id'), nullable=False)
  person = db.relationship(
      'Person', backref=backref('user_roles', cascade='all, delete-orphan'))

  @staticmethod
  def _extra_table_args(model):
    return (db.UniqueConstraint('person_id',
                                name='uq_{}'.format(model.__tablename__)),
            db.Index('ix_user_roles_person', 'person_id')
            )

  _api_attrs = reflection.ApiAttributes('role', 'person')

  @classmethod
  def role_assignments_for(cls, context):
    context_id = context.id if type(context) is Context else context
    all_assignments = db.session.query(UserRole)\
        .filter(UserRole.context_id == context_id)
    assignments_by_user = {}
    for assignment in all_assignments:
        assignments_by_user.setdefault(assignment.person.email, [])\
            .append(assignment.role)
    return assignments_by_user

  @classmethod
  def eager_query(cls, **kwargs):
    from sqlalchemy import orm

    query = super(UserRole, cls).eager_query(**kwargs)
    return query.options(
        orm.joinedload('role'),
        orm.subqueryload('person'),
        orm.subqueryload('context'))

  def _display_name(self):
    if self.context and self.context.related_object_type and \
       self.context.related_object:
      context_related = ' in ' + self.context.related_object.display_name
    elif hasattr(self, '_display_related_title'):
      context_related = ' in ' + self._display_related_title
    elif self.context:
      logger.warning('Unable to identify context.related for UserRole')
      context_related = ''
    else:
      context_related = ''
    return u'{0} <-> {1}{2}'.format(
        self.person.display_name, self.role.display_name, context_related)

  def _recalculate_permissions_cache(self):
    """Recalculate permissions cache for user `UserRole` relates to."""
    with utils.benchmark("Invalidate permissions cache for user in UserRole"):
      from ggrc_basic_permissions import load_permissions_for
      load_permissions_for(self.person, expire_old=True)

  def handle_delete(self):
    """Handle `model_deleted` signals invoked on `UserRole` instance.

    HTTP DELTE method on `UserRole` model triggers following actions:
      - Recalculate permissions cache for user the `UserRole` object is
        related to.
    """
    self._recalculate_permissions_cache()

  def handle_post(self):
    """Handle `model_posted` signals invoked on `UserRole` instance.

    HTTP POST method on `UserRole` model triggers following actions:
      - Recalculate permissions cache for user the `UserRole` object is
        related to.
    """
    self._recalculate_permissions_cache()


all_models.register_model(Role)
all_models.register_model(UserRole)
