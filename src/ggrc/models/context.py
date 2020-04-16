# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Context model definition."""

import datetime

from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr

from ggrc import db
from ggrc.models.deferred import deferred
from ggrc.models.mixins import base
from ggrc.models.mixins import Base
from ggrc.models import reflection


class Context(base.ContextRBAC, Base, db.Model):
  """Context class. Sign permissions object for specific user."""
  __tablename__ = 'contexts'

  # This block and the 'description' attrs are taken from the Described mixin
  #  which we do not use for Context because indexing Context descriptions
  #  for fulltext search leads to undesirable results
  @declared_attr
  def description(cls):  # pylint: disable=no-self-argument
    return deferred(db.Column(db.Text, nullable=False, default=u""),
                    cls.__name__)

  name = deferred(db.Column(db.String(128), nullable=True), 'Context')
  related_object_id = deferred(
      db.Column(db.Integer(), nullable=True), 'Context')
  related_object_type = deferred(
      db.Column(db.String(128), nullable=True), 'Context')

  @property
  def related_object_attr(self):
    return '{0}_related_object'.format(self.related_object_type)

  @property
  def related_object(self):
    return getattr(self, self.related_object_attr)

  @related_object.setter
  def related_object(self, value):
    self.related_object_id = value.id if value is not None else None
    self.related_object_type = value.__class__.__name__ if value is not None \
        else None
    return setattr(self, self.related_object_attr, value)

  @staticmethod
  def _extra_table_args(_):
    return (
        db.Index(
            'ix_context_related_object',
            'related_object_type', 'related_object_id'),
    )

  _api_attrs = reflection.ApiAttributes('name',
                                        'related_object',
                                        'description')

  _sanitize_html = ['name', 'description']
  _include_links = []


class HasOwnContext(object):
  """Mixin for models which may have their own context
  """

  @declared_attr
  def contexts(cls):  # pylint: disable=no-self-argument
    """Context relation declaration."""
    joinstr = 'and_(foreign(Context.related_object_id) == {type}.id, '\
              'foreign(Context.related_object_type) == "{type}")'
    joinstr = joinstr.format(type=cls.__name__)
    return db.relationship(
        'Context',
        primaryjoin=joinstr,
        # foreign_keys='Context.related_object_id',
        # cascade='all, delete-orphan',
        backref='{0}_related_object'.format(cls.__name__),
        order_by='Context.id',
        post_update=True)

  def build_object_context(self, context, name=None, description=None):
    """Build object content."""
    if name is None:
      name = '{object_type} Context {timestamp}'.format(
          object_type=self.__class__.__name__,
          timestamp=datetime.datetime.utcnow())
    if description is None:
      description = ''
    new_context = Context(
        name=name,
        description=description,
        related_object=self)
    if isinstance(context, Context):
      new_context.context = context
    else:
      new_context.context_id = context
    return new_context

  def get_or_create_object_context(self, *args, **kwargs):
    """Get or create object context instance."""
    if len(self.contexts) == 0:
      new_context = self.build_object_context(*args, **kwargs)
      self.contexts.append(new_context)
    return self.contexts[0]

  @classmethod
  def _filter_by_role(cls, role, predicate):
    from ggrc_basic_permissions.models import Role, UserRole
    from ggrc.models.person import Person
    return Person.query.join(UserRole, Role).filter(
        (UserRole.context_id == cls.context_id) &
        (Role.name == role) &
        (predicate(Person.name) | predicate(Person.email))
    ).exists()

  @classmethod
  def eager_query(cls, **kwargs):
    return super(HasOwnContext, cls).eager_query(**kwargs).options(
        orm.Load(cls).subqueryload(
            "contexts"
        ).undefer_group(
            "Context_complete"
        ),
    )
