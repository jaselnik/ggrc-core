# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with Requirement model."""

from sqlalchemy import orm

from ggrc import db
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import Commentable
from ggrc.models.directive import Directive
from ggrc.models.deferred import deferred
from ggrc.models import mixins, review
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models import reflection
from ggrc.models.relationship import Relatable
from ggrc.models.relationship import Relationship


class Requirement(Roleable,
                  review.Reviewable,
                  mixins.CustomAttributable,
                  mixins.WithStartDate,
                  mixins.WithLastDeprecatedDate,
                  Personable,
                  Relatable,
                  Commentable,
                  mixins.TestPlanned,
                  PublicDocumentable,
                  mixins.base.ContextRBAC,
                  mixins.BusinessObject,
                  mixins.Folderable,
                  mixins.WithWorkflowState,
                  Indexed,
                  db.Model):
  """Requirement model."""

  __tablename__ = 'requirements'
  _table_plural = 'requirements'
  _aliases = {
      "documents_file": None,
      "description": "Description",
      "directive": {
          "display_name": "Policy / Regulation / Standard / Contract",
          "type": reflection.AttributeInfo.Type.MAPPING,
          "filter_by": "_filter_by_directive",
      }
  }

  notes = deferred(db.Column(db.Text, nullable=False, default=u""),
                   'Requirements')

  _api_attrs = reflection.ApiAttributes('notes')
  _sanitize_html = ['notes']
  _include_links = []

  @classmethod
  def eager_query(cls, **kwargs):
    """Define fields to be loaded eagerly to lower the count of DB queries."""
    query = super(Requirement, cls).eager_query(**kwargs)
    return query.options(orm.undefer('notes'))

  @classmethod
  def _filter_by_directive(cls, predicate):
    """Apply predicate to the object referenced by directive field."""
    types = ["Policy", "Regulation", "Standard", "Contract"]
    dst = Relationship.query \
        .filter(
            (Relationship.source_id == cls.id) &
            (Relationship.source_type == cls.__name__) &
            (Relationship.destination_type.in_(types))) \
        .join(Directive, Directive.id == Relationship.destination_id) \
        .filter(predicate(Directive.slug) | predicate(Directive.title)) \
        .exists()
    src = Relationship.query \
        .filter(
            (Relationship.destination_id == cls.id) &
            (Relationship.destination_type == cls.__name__) &
            (Relationship.source_type.in_(types))) \
        .join(Directive, Directive.id == Relationship.source_id) \
        .filter(predicate(Directive.slug) | predicate(Directive.title)) \
        .exists()
    return dst | src
