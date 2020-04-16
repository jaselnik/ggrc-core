# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

from sqlalchemy import orm

from ggrc import db
from ggrc.fulltext import mixin as fulltext_mixin
from ggrc.models.comment import ScopedCommentable
from ggrc.models.deferred import deferred
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import reflection
from ggrc.models import relationship


class KeyReport(synchronizable.Synchronizable,
                mixins.CustomAttributable,
                object_person.Personable,
                synchronizable.RoleableSynchronizable,
                relationship.Relatable,
                object_document.PublicDocumentable,
                ScopedCommentable,
                mixins.TestPlanned,
                mixins.LastDeprecatedTimeboxed,
                mixins.base.ContextRBAC,
                mixins.ScopeObject,
                mixins.Folderable,
                mixins.WithWorkflowState,
                fulltext_mixin.Indexed,
                db.Model,
                ):

  __tablename__ = "key_reports"

  infrastructure = deferred(db.Column(db.Boolean), "KeyReport")
  version = deferred(db.Column(db.String), "KeyReport")

  _api_attrs = reflection.ApiAttributes(
      "infrastructure",
      "version",
  )
  _fulltext_attrs = [
      "infrastructure",
      "version",
  ]
  _sanitize_html = ["version"]
  _aliases = {
      "documents_file": None,
  }

  @classmethod
  def indexed_query(cls):
    query = super(KeyReport, cls).indexed_query()
    return query.options(
        orm.Load(cls).load_only(
            'infrastructure',
            'version'
        )
    )
