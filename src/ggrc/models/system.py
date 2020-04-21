# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

from sqlalchemy import orm
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import ScopedCommentable
from ggrc.models.deferred import deferred
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins.with_readonly_access import WithReadOnlyAccess
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.models import reflection


# NOTE: The PublicDocumentable mixin is not applied directly to the
# SystemOrProcess base class, but instead to all of its specialized subclasses.
# The reason for this is the PublicDocumentable's declared attribute
# `documents` that builds a dynamic DB relationship based on the class name,
# and thus the attribute needs to be run in the context of each particular
# subclass.
# (of course, if there is a nice way of overriding/customizing declared
# attributes in subclasses, we might want to use that approach)
class SystemOrProcess(ScopedCommentable,
                      synchronizable.Synchronizable,
                      mixins.TestPlanned,
                      mixins.LastDeprecatedTimeboxed,
                      mixins.base.ContextRBAC,
                      mixins.WithNetworkZone,
                      mixins.ScopeObject,
                      mixins.Folderable,
                      db.Model):
  # Override model_inflector
  _table_plural = 'systems_or_processes'
  __tablename__ = 'systems'

  infrastructure = deferred(db.Column(db.Boolean), 'SystemOrProcess')
  is_biz_process = db.Column(db.Boolean, default=False)
  version = deferred(db.Column(db.String), 'SystemOrProcess')

  __mapper_args__ = {
      'polymorphic_on': is_biz_process
  }

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'infrastructure',
      'version',
      reflection.Attribute('is_biz_process', create=False, update=False),
  )
  _fulltext_attrs = [
      'infrastructure',
      'version',
  ]
  _sanitize_html = ['version']
  _aliases = {
      "documents_file": None,
  }

  @staticmethod
  def _extra_table_args(cls):
    return (
        db.Index('ix_{}_is_biz_process'.format(cls.__tablename__),
                 'is_biz_process'),
    )

  @classmethod
  def indexed_query(cls):
    query = super(SystemOrProcess, cls).indexed_query()
    return query.options(
        orm.Load(cls).load_only(
            'infrastructure',
            'version'
        )
    )


class System(WithReadOnlyAccess,
             Personable,
             synchronizable.RoleableSynchronizable,
             Relatable,
             PublicDocumentable,
             SystemOrProcess,
             Indexed):
  __mapper_args__ = {
      'polymorphic_identity': False
  }
  _table_plural = 'systems'

  _aliases = {
      "documents_file": None,
  }

  @validates('is_biz_process')
  def validates_is_biz_process(self, key, value):
    return False


class Process(mixins.CustomAttributable,
              Personable,
              synchronizable.RoleableSynchronizable,
              Relatable,
              PublicDocumentable,
              SystemOrProcess,
              Indexed):
  __mapper_args__ = {
      'polymorphic_identity': True
  }
  _table_plural = 'processes'

  _aliases = {
      "documents_file": None,
  }

  @validates('is_biz_process')
  def validates_is_biz_process(self, key, value):
    return True
