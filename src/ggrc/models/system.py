# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

from sqlalchemy import orm

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


class System(mixins.CustomAttributable,
             WithReadOnlyAccess,
             Personable,
             synchronizable.RoleableSynchronizable,
             Relatable,
             PublicDocumentable,
             ScopedCommentable,
             synchronizable.Synchronizable,
             mixins.TestPlanned,
             mixins.LastDeprecatedTimeboxed,
             mixins.base.ContextRBAC,
             mixins.WithNetworkZone,
             mixins.ScopeObject,
             mixins.Folderable,
             db.Model,
             Indexed):

  # Override model_inflector
  _table_plural = 'systems'
  __tablename__ = 'systems'

  infrastructure = deferred(db.Column(db.Boolean), 'System')
  version = deferred(db.Column(db.String), 'System')

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'infrastructure',
      'version',
  )
  _fulltext_attrs = [
      'infrastructure',
      'version',
  ]
  _sanitize_html = ['version']
  _aliases = {
      "documents_file": None,
  }

  @classmethod
  def indexed_query(cls):
    query = super(System, cls).indexed_query()
    return query.options(
        orm.Load(cls).load_only(
            'infrastructure',
            'version'
        )
    )


class Process(mixins.CustomAttributable,
              Personable,
              synchronizable.RoleableSynchronizable,
              Relatable,
              PublicDocumentable,
              ScopedCommentable,
              synchronizable.Synchronizable,
              mixins.TestPlanned,
              mixins.LastDeprecatedTimeboxed,
              mixins.base.ContextRBAC,
              mixins.WithNetworkZone,
              mixins.ScopeObject,
              mixins.Folderable,
              db.Model,
              Indexed):

  # Override model_inflector
  _table_plural = 'processes'
  __tablename__ = 'processes'

  infrastructure = deferred(db.Column(db.Boolean), 'Process')
  version = deferred(db.Column(db.String), 'Process')

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'infrastructure',
      'version',
  )
  _fulltext_attrs = [
      'infrastructure',
      'version',
  ]
  _sanitize_html = ['version']
  _aliases = {
      "documents_file": None,
  }

  @classmethod
  def indexed_query(cls):
    query = super(Process, cls).indexed_query()
    return query.options(
        orm.Load(cls).load_only(
            'infrastructure',
            'version'
        )
    )
